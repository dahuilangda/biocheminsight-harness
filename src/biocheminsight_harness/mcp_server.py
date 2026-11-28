"""MCP server: BioChemInsight tools for coding agents."""
from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path
from typing import Any

import httpx

from . import chemistry
from . import coordination as coord
from . import decisions as decisions_mod
from . import ocr as ocr_mod
from . import pages as pages_mod
from . import report
from . import sar as sar_mod
from .config import biocheminsight_url, harness_url
from . import frontend
from . import identity

_IDLE_NOTES = {
    "awaiting_perception": "All answers are in and the task is being resumed. Keep polling.",
    "pending": "The task is queued or starting; its next requests appear here. Keep polling.",
}


def _write_measurement_prompt(session_id: str, out_dir: str, prompt: dict) -> Path:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    prefix = f"review_{session_id[:8]}_"
    indices = (
        int(match.group(1))
        for path in directory.glob(f"{prefix}*.txt")
        if (match := re.fullmatch(rf"{re.escape(prefix)}(\d+)\.txt", path.name))
    )
    index = max(indices, default=-1) + 1
    path = directory / f"{prefix}{index}.txt"
    path.write_text(json.dumps(prompt, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _task_state(task_id: str) -> dict:
    from .config import biocheminsight_url
    response = httpx.get(f"{biocheminsight_url().rstrip('/')}/api/tasks/{task_id}",
                         timeout=30.0, verify=False)
    response.raise_for_status()
    return response.json()


# Observed pace of each task, so task_status can estimate the remaining
# time. Seconds count only while a task runs: the wait for perception
# answers can last hours and says nothing about that pace.
_ETA_SAMPLES: dict[str, dict] = {}
_ETA_SAMPLE_LIMIT = 64
_ETA_SAMPLE_TTL = 3600.0


def _observe_task(task_id: str, status: str, progress: float) -> dict | None:
    now = time.monotonic()
    sample = _ETA_SAMPLES.get(task_id)
    if sample is None:
        if status in ("running", "awaiting_perception"):
            sample = {"first_seen": now, "first_progress": progress,
                      "active": 0.0, "last": now, "last_status": status}
            _ETA_SAMPLES[task_id] = sample
            while len(_ETA_SAMPLES) > _ETA_SAMPLE_LIMIT:
                oldest = min(_ETA_SAMPLES, key=lambda key: _ETA_SAMPLES[key]["last"])
                del _ETA_SAMPLES[oldest]
        return sample
    if now - sample["last"] > _ETA_SAMPLE_TTL:
        _ETA_SAMPLES.pop(task_id, None)
        return _observe_task(task_id, status, progress)
    if sample["last_status"] == "running":
        sample["active"] += now - sample["last"]
    sample["last"], sample["last_status"] = now, status
    return sample


def _eta_seconds(sample, status: str, progress: float) -> int | None:
    """Remaining seconds from the pace observed while the task ran. None
    while there is no pace to extrapolate."""
    if sample is None or status != "running":
        return None
    gained = progress - sample["first_progress"]
    if gained <= 0.0 or sample["active"] <= 0.0:
        return None
    remaining = round((1.0 - progress) * sample["active"] / gained)
    return remaining or None


def _result_links(task_id: str, task_type: str) -> dict:
    """Download links for a finished run."""
    from .config import biocheminsight_url
    base = biocheminsight_url().rstrip("/")
    return {"download_url": f"{base}/api/tasks/{task_id}/download",
            "tables": frontend.task_table_urls(task_id, task_type)}


def _pending_perception(task_id: str) -> tuple[list[dict], int]:
    """Next bounded batch of the task's unanswered requests, and the true
    number still pending. A request about an image carries a `sheet_url`;
    one without it is a text question whose `prompt` is the whole request.
    The server's own file path is dropped because it is only meaningful
    on the server."""
    from .config import biocheminsight_url
    from .perception import batch_requests
    base = biocheminsight_url().rstrip("/")
    response = httpx.get(
        f"{base}/api/tasks/{task_id}/perception/requests", timeout=30.0, verify=False)
    response.raise_for_status()
    payload = response.json()
    requests = batch_requests(payload.get("requests", []))
    for request in requests:
        if request.pop("sheet", None):
            request["sheet_url"] = (
                f"{base}/api/tasks/{task_id}/perception/requests/"
                f"{request['request_id']}/sheet")
    return requests, int(payload.get("pending", 0) or 0)

def create_server():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("biocheminsight-harness")

    @mcp.tool()
    def configure_deployment(url: str, ocr_url: str = "",
                             harness_url_override: str = "") -> dict:
        """Save the deployment URLs used by subsequent tool calls."""
        from .config import save_deployment
        cfg = save_deployment(url, ocr_url or None,
                              harness_url_override or None)
        return {"configured": True,
                "biocheminsight_url": cfg.get("biocheminsight_url", url),
                "ocr_url": cfg.get("ocr_url", "")}

    @mcp.tool()
    def deployment_status() -> dict:
        """Check connectivity to every configured BioChemInsight endpoint:
        pipeline API, harness chemistry, OCR service. Reports each probe's
        round-trip time and warns when the deployment answers slowly, which
        makes uploads and the many small calls of a parse run take minutes."""
        def probe(url: str) -> tuple[bool, float]:
            started = time.monotonic()
            try:
                ok = httpx.get(url, timeout=5, verify=False).is_success
            except Exception:
                ok = False
            return ok, round((time.monotonic() - started) * 1000)

        base = biocheminsight_url().rstrip("/")
        pipeline_ok, pipeline_ms = probe(f"{base}/api/tasks")
        try:
            from .config import harness_url, ocr_url
            harness_ok, harness_ms = probe(f"{harness_url().rstrip('/')}/healthz")
            ocr_ok, ocr_ms = probe(f"{ocr_url().rstrip('/')}/healthz")
        except Exception:
            harness_ok, ocr_ok = False, False
            harness_ms = ocr_ms = 0
        out = {"biocheminsight_url": base,
               "pipeline": pipeline_ok,
               "harness_chemistry": harness_ok,
               "ocr_service": ocr_ok,
               "connected": pipeline_ok,
               "roundtrip_ms": {"pipeline": pipeline_ms,
                                "harness_chemistry": harness_ms,
                                "ocr_service": ocr_ms}}
        slow = [ms for ok, ms in ((pipeline_ok, pipeline_ms), (harness_ok, harness_ms))
                if ok and ms > 1000]
        if slow:
            out["note"] = ("The deployment answers in over a second per call. A parse "
                           "makes many small calls and uploads the PDF, so this adds up. "
                           "If the harness runs on the deployment's own host, set "
                           "BIOCHEMINSIGHT_URL to a local address.")
        return out

    @mcp.tool()
    def render_pages(pdf_path: str, page_numbers: list[int], out_path: str,
                     columns: int = 4, thumb_width: int = 320) -> str:
        """Render pages into one contact sheet, each panel captioned with
        its page number. Panels are small: enough to classify a page, not
        to read it. Pass page numbers in the order you want them laid out,
        left to right, top to bottom."""
        return str(pages_mod.render_contact_sheet(
            pdf_path, page_numbers, out_path, columns, thumb_width))

    @mcp.tool()
    def render_page(pdf_path: str, page: int, out_path: str,
                    dpi: int = 150) -> str:
        return str(pages_mod.render_page(pdf_path, page, out_path, dpi))

    @mcp.tool()
    def extract_page_images(pdf_path: str, pages: list[int],
                            out_dir: str) -> list[str]:
        """Extract embedded chart crops / structure plates at native
        resolution so you can read them with your own vision."""
        return [str(path) for path in pages_mod.extract_page_images(
            pdf_path, pages, out_dir)]

    @mcp.tool()
    def read_compound_labels(
        pdf_path: str, page: int, boxes: list[tuple[float, float, float, float]],
    ) -> dict:
        """Read numbered labels for structure boxes from the PDF text layer.

        Page numbers are one-based. Boxes use normalized left, top, right,
        bottom coordinates on the rendered page. Labels follow box order.
        """
        return identity.read_compound_labels(pdf_path, page, boxes)

    @mcp.tool()
    def record_structure_detection(out_path: str,
                                   decisions: list[dict]) -> dict:
        model = decisions_mod.record_structure_detection(
            out_path, {"decisions": decisions})
        return {"detected_pages": model.detected_pages(),
                "pages": len(model.decisions)}

    @mcp.tool()
    def record_measurement_discovery(out_path: str,
                                     decisions: list[dict]) -> dict:
        model = decisions_mod.record_measurement_discovery(
            out_path, {"decisions": decisions})
        return {"selected_pages": model.selected_pages(),
                "failed_pages": model.failed_pages(),
                "assay_names": model.assay_names()}

    @mcp.tool()
    def record_assay_reconciliation(out_path: str,
                                    decisions: list[dict]) -> dict:
        model = decisions_mod.record_assay_reconciliation(
            out_path, {"decisions": decisions})
        return {"decisions": len(model.decisions)}

    @mcp.tool()
    def pipeline_perception_requests(task_id: str) -> list[dict]:
        """Next bounded batch of the vision requests this task awaits
        (perception_batch_size, default 8). `task_status` already returns the
        same batch on every poll; call this only to pull the next batch
        without a status poll."""
        return _pending_perception(task_id)[0]

    @mcp.tool()
    def fetch_perception_sheet(task_id: str, request_id: str,
                               out_path: str) -> str:
        """Download the rendered sheet image for one pending perception
        request so you can read it with your vision."""
        from .config import biocheminsight_url
        url = (f"{biocheminsight_url().rstrip('/')}"
               f"/api/tasks/{task_id}/perception/requests/{request_id}/sheet")
        r = httpx.get(url, timeout=60.0, verify=False)
        r.raise_for_status()
        from pathlib import Path
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(r.content)
        return str(out)

    @mcp.tool()
    def pipeline_perception_answer(task_id: str, request_id: str,
                                   answer: str) -> dict:
        """Submit your answer for one pending pipeline perception request.
        The answer must satisfy the request's own output contract (return
        the JSON the prompt asks for, verbatim). The task resumes on its
        own after the last pending request is answered."""
        from .config import biocheminsight_url
        r = httpx.post(
            f"{biocheminsight_url().rstrip('/')}/api/tasks/{task_id}/perception/{request_id}/answer",
            json={"answer": answer}, timeout=30.0, verify=False)
        r.raise_for_status()
        return r.json()

    @mcp.tool()
    def record_monomer_dictionary(task_session_id: str, entries: list[dict],
                                  output_dir: str = "") -> dict:
        """Feed the document's own monomer definitions (code -> SMILES
        transcribed from its definition pages) into the session's
        codebook. Document-scoped: nothing crosses to another document;
        entries stay candidates until mass arbitration confirms them.
        Harvest this BEFORE run-chemistry whenever the document defines
        custom residues."""
        payload = {"entries": entries}
        if output_dir:
            payload["output_dir"] = output_dir
        from .config import harness_url
        r = httpx.post(
            f"{harness_url().rstrip('/')}/v1/agent-mode/{task_session_id}/monomer-dictionary",
            json=payload, timeout=60.0, verify=False)
        r.raise_for_status()
        return r.json()

    @mcp.tool()
    def route_pages(pdf_path: str, pages: list[int],
                    page_types: dict[str, str] | None = None) -> dict:
        """Route pages to the deployment's OCR service or to your own
        vision, based on page type. Types in {rotated_table,
        compound_table, dense_layout} go to vision; the rest go to OCR
        with quality escalation back to you."""
        from .perception import PerceptionRouter
        types = {}
        for key, value in (page_types or {}).items():
            try:
                types[int(key)] = value
            except (TypeError, ValueError):
                raise ValueError(
                    f"page_types key {key!r} is not a page number") from None
        result = PerceptionRouter().route_pages(pdf_path, pages, types)
        return {"markdowns": {str(k): v for k, v in result["markdowns"].items()},
                "agent_pages": result["agent_pages"]}

    @mcp.tool()
    def ocr_pages(pdf_path: str, pages: list[int], out_path: str,
                  lang: str = "en") -> str:
        client = ocr_mod.OcrClient()
        markdowns = client.pages_markdown(pdf_path, pages, lang)
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(markdowns, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        return str(out)

    @mcp.tool()
    def parse_peptide_notation(notation: str) -> dict:
        return chemistry.parse_notation(notation)

    @mcp.tool()
    def resolve_peptide_notation(notation: str,
                                 declared_mass: float | None = None,
                                 form: str = "", seq_id: str = "",
                                 smiles_reading: str = "",
                                 ion_mz: float | None = None,
                                 ion_charge: int | None = None) -> dict:
        return chemistry.resolve_notation(notation, declared_mass, form,
                                          seq_id, smiles_reading,
                                          ion_mz=ion_mz,
                                          ion_charge=ion_charge)

    @mcp.tool()
    def peptide_fragment_forms(smiles: str) -> dict:
        return chemistry.fragment_forms(smiles)

    @mcp.tool()
    def mass_arbitration(smiles: str, declared_mass: float | None = None,
                         tolerance: float = 0.8,
                         ion_mz: float | None = None,
                         ion_charge: int | None = None) -> dict:
        return chemistry.mass_arbitration(smiles, declared_mass, tolerance,
                                          ion_mz=ion_mz, ion_charge=ion_charge)

    @mcp.tool()
    def upload_pdf(path: str) -> str:
        from .client import BioChemInsightClient
        return BioChemInsightClient().upload_pdf(path)

    @mcp.tool()
    def start_full_pipeline(pdf_id: str, strictness: str = "strict",
                            assemble_markush: bool = True) -> str:
        """Run extraction with the calling agent answering image and text perception requests."""
        from .client import BioChemInsightClient
        client = BioChemInsightClient()
        with client.http:
            return client.start_full_pipeline(
                pdf_id, structure_filter_strictness=strictness, assemble_markush=assemble_markush,
                perception_provider="agent",
            )

    @mcp.tool()
    def start_sar_recovery(task_id: str, max_actions: int = 8) -> str:
        """Start evidence recovery with the calling agent answering perception requests."""
        from .client import BioChemInsightClient
        client = BioChemInsightClient()
        with client.http:
            return client.start_sar_recovery(task_id, max_actions)

    @mcp.tool()
    def task_status(task_id: str) -> dict:
        """Poll a pipeline task. Whenever the task has unanswered requests,
        a bounded batch of them (perception_batch_size, default 8) rides in
        the response with `pending` as the true total. Answer them with
        perception_batch and perception_answers; the single-request tools
        work too, each request carrying a `sheet_url` for its image, or
        none when it is a text question whose `prompt` is the whole
        request. The task goes on by itself after the last answer; while
        it waits or starts with nothing to answer, `note` says so. While
        the task runs, `elapsed_seconds` says how long it has taken and
        `eta_seconds` how long it is expected to still need (None until
        its pace is known); once completed, `result` holds the download
        URL and the per-table URLs. download_task_result saves the zip."""
        task = _task_state(task_id)
        status = task.get("status")
        progress = float(task.get("progress") or 0.0)
        sample = _observe_task(task_id, status, progress)
        out = {"status": status, "progress": progress,
               "message": task.get("message"), "error": task.get("error"),
               "created_at": task.get("created_at"), "updated_at": task.get("updated_at")}
        if task.get("queue_position") is not None:
            out["queue_position"] = task.get("queue_position")
        if sample is not None:
            out["elapsed_seconds"] = round(time.monotonic() - sample["first_seen"])
        eta = _eta_seconds(sample, status, progress)
        if eta is not None:
            out["eta_seconds"] = eta
        if status == "completed":
            out["result"] = _result_links(task_id, task.get("type", ""))
        requests, pending = _pending_perception(task_id)
        if requests or pending:
            out["awaiting_perception"] = {"pending": pending, "requests": requests}
        elif status in _IDLE_NOTES:
            out["note"] = _IDLE_NOTES[status]
        return out

    @mcp.tool()
    def task_list(status: str = "") -> dict:
        """Recent pipeline tasks of the deployment, latest first: each with
        id, type, status, progress, message, updated_at. `status` narrows
        to one status (running, awaiting_perception, completed, failed).
        This is the deployment's whole queue, not only the tasks you
        started."""
        from .config import biocheminsight_url
        r = httpx.get(
            f"{biocheminsight_url().rstrip('/')}/api/tasks",
            params={"status": status or "all", "sort_by": "updated_at",
                    "sort_dir": "desc", "page_size": 20},
            timeout=30.0, verify=False)
        r.raise_for_status()
        return {"tasks": [{key: task.get(key) for key in ("task_id", "type", "status",
                                                          "progress", "message", "updated_at")}
                          for task in r.json().get("tasks") or []]}

    @mcp.tool()
    def perception_batch(task_id: str, limit: int = 0) -> list:
        """Next batch of the task's unanswered requests, ready to answer: for
        each request a text block with its id, task name, prompt and any
        earlier answer of yours that was rejected, followed by its sheet image
        when it has one. A sheet that shows several numbered images takes
        one object keyed by the number. Read
        every block, answer the whole batch with perception_answers, then call
        again until nothing is pending. Pass a smaller `limit` when the sheets
        are large."""
        from mcp.types import ImageContent, TextContent
        requests, pending = _pending_perception(task_id)
        if limit > 0:
            requests = requests[:limit]
        blocks = []
        for index, request in enumerate(requests, 1):
            sheet_url = request.pop("sheet_url", None)
            blocks.append(TextContent(
                type="text",
                text=json.dumps({**request, "index": index, "batch": len(requests), "pending": pending},
                                ensure_ascii=False)))
            if sheet_url:
                response = httpx.get(sheet_url, timeout=60.0, verify=False)
                response.raise_for_status()
                blocks.append(ImageContent(
                    type="image", mimeType="image/png",
                    data=base64.b64encode(response.content).decode("ascii")))
        if blocks:
            return blocks
        status = _task_state(task_id)
        return [TextContent(type="text", text=json.dumps({
            "pending": 0, "status": status.get("status"), "progress": status.get("progress"),
            "message": status.get("message"),
            "note": _IDLE_NOTES.get(status.get("status"), "Nothing to answer right now. Poll again."),
        }))]

    @mcp.tool()
    def perception_answers(task_id: str, answers: str) -> dict:
        """Submit a batch answered from perception_batch. `answers` is a JSON
        list of {"request_id": ..., "answer": ...}, where an answer is the
        JSON the request's prompt asks for, as an object or as its text.
        Returns each request's outcome and how many requests remain."""
        from .config import biocheminsight_url
        base = biocheminsight_url().rstrip("/")
        items = json.loads(answers)
        if not isinstance(items, list):
            raise ValueError("answers must be a JSON list of {request_id, answer} objects")
        results = []
        for item in items:
            request_id = str(item.get("request_id") or "")
            answer = item.get("answer")
            text = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
            response = httpx.post(
                f"{base}/api/tasks/{task_id}/perception/{request_id}/answer",
                json={"answer": text}, timeout=30.0, verify=False)
            outcome = (response.json() if response.headers.get("content-type", "").startswith("application/json")
                       else {"error": response.text[:200]})
            results.append({"request_id": request_id[:8], "ok": response.is_success, **outcome})
        return {"results": results, "pending": _pending_perception(task_id)[1]}

    @mcp.tool()
    def download_task_result(task_id: str, dest_dir: str) -> str:
        from .client import BioChemInsightClient
        dest = BioChemInsightClient().download_result(
            task_id, Path(dest_dir) / f"{task_id}.zip")
        return str(dest)

    @mcp.tool()
    def local_task_stats(root: str = ".") -> dict:
        """Inventory local tasks and result archives under the supplied workspace path."""
        from .task_stats import scan_tasks
        return scan_tasks(root)

    @mcp.tool()
    def build_extraction_report(task_dir: str, out_path: str,
                                title: str = "") -> str:
        return str(report.build_report(task_dir, out_path, title))

    @mcp.tool()
    def task_tables(task_id: str, table: str = "structures") -> list[dict]:
        """Read structure, assay, joined, or SAR records from a finished task."""
        import httpx as _httpx
        from .config import biocheminsight_url
        allowed = {"structures", "assays", "merged", "sar"}
        if table not in allowed:
            raise ValueError(f"table must be one of {sorted(allowed)}")
        r = _httpx.get(
            f"{biocheminsight_url().rstrip('/')}/api/tasks/{task_id}/{table}",
            timeout=60.0, verify=False)
        r.raise_for_status()
        payload = r.json()
        for key in ("records", "rows", "units" if table == "sar" else table, "results"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return rows
        raise ValueError(f"Unexpected {table} response: missing records")

    @mcp.tool()
    def cancel_task(task_id: str) -> dict:
        """Cancel a running pipeline task."""
        import httpx as _httpx
        from .config import biocheminsight_url
        r = _httpx.post(
            f"{biocheminsight_url().rstrip('/')}/api/tasks/{task_id}/cancel",
            timeout=30.0, verify=False)
        r.raise_for_status()
        t = r.json()
        return {"task_id": task_id, "status": t.get("status")}

    @mcp.tool()
    def detect_structures_on_page(page_image_path: str,
                                  conf: float = 0.25,
                                  include_crops: bool = False,
                                  out_dir: str = "") -> dict:
        """Detect chemical structure bounding boxes on a rendered page
        image. Returns box coordinates and scores; optionally include the
        cropped images for verification."""
        from .config import harness_url
        with open(page_image_path, "rb") as handle:
            r = httpx.post(
                f"{harness_url().rstrip('/')}/v1/structures/detect",
                params={"conf": conf, "include_crops": include_crops},
                files={"file": handle}, timeout=120.0)
        r.raise_for_status()
        result = r.json()
        if out_dir and include_crops:
            from pathlib import Path
            import base64 as _b64
            out = Path(out_dir)
            out.mkdir(parents=True, exist_ok=True)
            for index, structure in enumerate(result.get("structures", [])):
                crop = structure.get("crop_png_b64") or structure.get("crop")
                if crop:
                    (out / f"box_{index}.png").write_bytes(
                        _b64.b64decode(crop))
        return result

    @mcp.tool()
    def recognize_region(page_image_path: str,
                         x: int, y: int, w: int, h: int) -> dict:
        """Decode one boxed region (pixel coordinates) of a rendered page
        into SMILES. Crops the region before recognition."""
        from PIL import Image
        import io as _io
        img = Image.open(page_image_path)
        region = img.crop((x, y, x + w, y + h))
        buf = _io.BytesIO()
        region.save(buf, format="PNG")
        buf.seek(0)
        from .config import harness_url
        r = httpx.post(
            f"{harness_url().rstrip('/')}/v1/structures/recognize",
            files={"file": ("region.png", buf, "image/png")}, timeout=180.0)
        r.raise_for_status()
        return r.json()

    @mcp.tool()
    def parse_sequence(document_id: str, notation: str) -> dict:
        """Document-aware sequence parse: routes antibody/enzyme chains to
        the numbering skill and HGVS strings to the variant-site skill,
        filed under the document ledger."""
        from .config import harness_url
        r = httpx.post(f"{harness_url().rstrip('/')}/v1/harness/parse-sequence",
                       json={"document_id": document_id, "notation": notation},
                       timeout=120.0, verify=False)
        if r.status_code == 422:
            return {"error": (r.json().get("detail") or r.text[:200])}
        r.raise_for_status()
        return r.json()

    @mcp.tool()
    def smiles_to_sequence(smiles: str) -> dict:
        """Deterministic cyclic-peptide SMILES to ordered residue list via
        the deployment vocabulary (incl. 4Pal, Trp7Cl, aMeS, ACPC, Nle,
        PipOH, Hyp, NMeG, 7azaTrp, Sbridge, pseudoproline)."""
        from .config import harness_url
        r = httpx.post(
            f"{harness_url().rstrip('/')}/v1/peptides/smiles-to-sequence",
            files={"file": ("smiles.txt", smiles.encode())}, timeout=120.0, verify=False)
        r.raise_for_status()
        return r.json()

    @mcp.tool()
    def verify_structure(smiles: str, image_path: str) -> dict:
        """Cross-check a decoded SMILES against its source crop with the
        deployment's visual verifier."""
        from .config import harness_url
        with open(image_path, "rb") as handle:
            r = httpx.post(
                f"{harness_url().rstrip('/')}/v1/harness/verify-structure",
                files={"file": handle},
                data={"smiles": smiles}, timeout=180.0, verify=False)
        r.raise_for_status()
        return r.json()

    @mcp.tool()
    def open_review_workspace(task_id: str) -> dict:
        task = _task_state(task_id)
        return {"url": frontend.review_workspace_url(task_id, task.get("pdf_id", ""), task.get("type", "")),
                "task_id": task_id}

    @mcp.tool()
    def task_artifact_urls(task_id: str) -> dict:
        """Browser URLs for the tables provided by this task."""
        task = _task_state(task_id)
        return {"task_id": task_id, **frontend.task_table_urls(task_id, task.get("type", ""))}

    @mcp.tool()
    def batch_partition(run_dir: str, total_pages: int,
                        pages_per_batch: int = 12) -> dict:
        ledger = coord.BatchLedger.partition(run_dir, total_pages,
                                             pages_per_batch)
        return {"batches": len(ledger.batches)}

    @mcp.tool()
    def batch_claim(run_dir: str, worker: str, count: int = 1) -> list[dict]:
        ledger = coord.BatchLedger(run_dir)
        return ledger.claim(worker, count)

    @mcp.tool()
    def batch_complete(run_dir: str, worker: str, batch_id: str,
                       result_path: str) -> None:
        ledger = coord.BatchLedger(run_dir)
        ledger.complete(worker, batch_id, result_path)

    @mcp.tool()
    def batch_fail(run_dir: str, worker: str, batch_id: str,
                   reason: str) -> None:
        """Record the failure and release the claim so another worker can
        take the batch."""
        ledger = coord.BatchLedger(run_dir)
        ledger.fail(worker, batch_id, reason)

    @mcp.tool()
    def batch_merge(results_dir: str) -> dict:
        return coord.merge_decision_files(results_dir)

    @mcp.tool()
    def sar_build(structures: list[dict],
                  measurements: list[dict]) -> dict:
        return sar_mod.build_sar_table(structures, measurements)

    @mcp.tool()
    def sar_analysis(sar_rows: list[dict],
                     higher_is_better: dict[str, bool] | None = None) -> dict:
        return sar_mod.sar_summary(sar_rows, higher_is_better)

    @mcp.tool()
    def verify_extraction(readings: list[dict],
                          key_fields: list[str]) -> dict:
        """Cross-check independent readings of the same source (OCR vs
        your own vision vs chart transcription) on key fields."""
        from .verification import cross_check
        return cross_check(readings, key_fields)

    @mcp.tool()
    def verify_dual_source(notation_smiles: str, ocsr_smiles: str) -> dict:
        """Second-source acceptance for a structure: the notation-derived
        SMILES and the OCSR crop SMILES must agree on InChIKey."""
        from .verification import dual_source_consistency
        return dual_source_consistency(notation_smiles, ocsr_smiles)

    @mcp.tool()
    def measurement_review_start(source: str, out_dir: str,
                                 max_revisions: int = 1) -> dict:
        """Start a measurement review session. Returns the first prompt.
        Answer it as the model would, then submit via
        measurement_review_submit."""
        base = f"{harness_url().rstrip('/')}/v1/harness/measurement-review"
        response = httpx.post(f"{base}/start",
                              json={"source": source,
                                    "max_revisions": max_revisions},
                              timeout=60.0, verify=False)
        response.raise_for_status()
        payload = response.json()
        session_id = payload["session_id"]
        if payload["done"]:
            return {"session_id": session_id, "done": True, "result": payload.get("result")}
        path = _write_measurement_prompt(session_id, out_dir, payload["prompt"])
        return {"session_id": session_id, "done": False, "prompt_file": str(path)}

    @mcp.tool()
    def measurement_review_submit(session_id: str, answer_file: str,
                                  out_dir: str) -> dict:
        """Submit an answered prompt file. Returns the next prompt or the
        final result."""
        answer = Path(answer_file).read_text(encoding="utf-8")
        base = f"{harness_url().rstrip('/')}/v1/harness/measurement-review"
        response = httpx.post(f"{base}/{session_id}/submit",
                              json={"answer": answer}, timeout=120.0, verify=False)
        response.raise_for_status()
        payload = response.json()
        if payload["done"]:
            return {"session_id": session_id, "done": True, "result": payload.get("result")}
        path = _write_measurement_prompt(session_id, out_dir, payload["prompt"])
        return {"session_id": session_id, "done": False, "next_prompt_file": str(path)}

    return mcp

def main():
    create_server().run()

if __name__ == "__main__":
    main()
