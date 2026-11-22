"""MCP server: BioChemInsight tools for coding agents."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from .config import auth_credentials

from . import chemistry
from . import coordination as coord
from . import decisions as decisions_mod
from . import ocr as ocr_mod
from . import pages as pages_mod
from . import report
from . import sar as sar_mod
from .config import biocheminsight_url, harness_url, paddleocr_url
from . import frontend

def _authed():
    creds = auth_credentials()
    kwargs = {}
    if creds:
        kwargs["auth"] = creds
    kwargs["verify"] = False
    return kwargs

def create_server():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("biocheminsight-harness")

    @mcp.tool()
    def configure_deployment(url: str, ocr_url: str = "",
                             harness_url_override: str = "",
                             user: str = "", password: str = "") -> dict:
        """Connect the harness to a BioChemInsight deployment. Saves the
        URLs and optional basic-auth credentials so subsequent tool calls
        use this deployment."""
        from .config import save_deployment, save_auth
        cfg = save_deployment(url, ocr_url or None,
                              harness_url_override or None)
        if user and password:
            save_auth(user, password)
        return {"configured": True,
                "biocheminsight_url": cfg.get("biocheminsight_url", url),
                "ocr_url": cfg.get("ocr_url", "")}

    @mcp.tool()
    def deployment_status() -> dict:
        """Check connectivity to every configured BioChemInsight endpoint:
        pipeline API, harness chemistry, OCR service."""
        def probe(url: str) -> bool:
            try:
                return httpx.get(url, timeout=5, **_authed()).is_success
            except Exception:
                return False

        base = biocheminsight_url().rstrip("/")
        pipeline_ok = probe(f"{base}/api/tasks")
        try:
            from .config import harness_url
            harness_ok = probe(f"{harness_url().rstrip('/')}/healthz")
        except Exception:
            harness_ok = False
        try:
            from .config import ocr_url
            paddle_ok = probe(f"{ocr_url().rstrip('/')}/healthz")
        except Exception:
            paddle_ok = False
        return {"biocheminsight_url": base,
                "pipeline": pipeline_ok,
                "harness_chemistry": harness_ok,
                "ocr_service": paddle_ok,
                "connected": pipeline_ok}

    @mcp.tool()
    def render_pages(pdf_path: str, page_numbers: list[int], out_path: str,
                     columns: int = 4, thumb_width: int = 320) -> str:
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
        """Vision calls the server pipeline awaits for this task: read each
        rendered sheet with your own vision and answer via
        pipeline_perception_answer."""
        from .config import biocheminsight_url
        r = httpx.get(
            f"{biocheminsight_url().rstrip('/')}/api/tasks/{task_id}/perception/requests",
            timeout=30.0, **_authed())
        r.raise_for_status()
        requests = r.json().get("requests", [])
        for request in requests:
            request["sheet_url"] = (f"{biocheminsight_url().rstrip('/')}"
                                    f"/api/tasks/{task_id}/perception/requests/"
                                    f"{request['request_id']}/sheet")
        return requests

    @mcp.tool()
    def fetch_perception_sheet(task_id: str, request_id: str,
                               out_path: str) -> str:
        """Download the rendered sheet image for one pending perception
        request so you can read it with your vision."""
        from .config import biocheminsight_url
        url = (f"{biocheminsight_url().rstrip('/')}"
               f"/api/tasks/{task_id}/perception/requests/{request_id}/sheet")
        r = httpx.get(url, timeout=60.0, **_authed())
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
            json={"answer": answer}, timeout=30.0, **_authed())
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
            json=payload, timeout=60.0, **_authed())
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
                                 smiles_reading: str = "") -> dict:
        return chemistry.resolve_notation(notation, declared_mass, form,
                                          seq_id, smiles_reading)

    @mcp.tool()
    def peptide_fragment_forms(smiles: str) -> dict:
        return chemistry.fragment_forms(smiles)

    @mcp.tool()
    def mass_arbitration(smiles: str, declared_mass: float,
                         tolerance: float = 0.8) -> dict:
        return chemistry.mass_arbitration(smiles, declared_mass, tolerance)

    @mcp.tool()
    def upload_pdf(path: str) -> str:
        from .client import BioChemInsightClient
        return BioChemInsightClient().upload_pdf(path)

    @mcp.tool()
    def start_full_pipeline(pdf_id: str, strictness: str = "strict",
                            assemble_markush: bool = True) -> str:
        """Start the extraction pipeline in agent-perception mode: the
        connected coding agent (you) answers every vision call. The task
        pauses at awaiting_perception when requests are pending and
        resumes automatically once you answer them."""
        import httpx as _httpx
        from .config import biocheminsight_url
        r = _httpx.post(f"{biocheminsight_url().rstrip('/')}/api/tasks/full-pipeline",
                        json={"pdf_id": pdf_id,
                              "structure_filter_strictness": strictness,
                              "assemble_markush": assemble_markush,
                              "perception_provider": "agent"}, timeout=60.0, **_authed())
        r.raise_for_status()
        return r.json().get("task_id")

    @mcp.tool()
    def task_status(task_id: str) -> dict:
        """Poll a pipeline task. When status is awaiting_perception the
        pending vision requests ride in the response: read each sheet
        with your vision and answer via pipeline_perception_answer; the
        task resumes on its own after the last answer."""
        import httpx as _httpx
        from .config import biocheminsight_url
        base = biocheminsight_url().rstrip("/")
        r = _httpx.get(f"{base}/api/tasks/{task_id}", timeout=30.0, **_authed())
        r.raise_for_status()
        task = r.json()
        out = {"status": task.get("status"), "progress": task.get("progress"),
               "message": task.get("message"), "error": task.get("error")}
        if task.get("status") == "awaiting_perception":
            pr = _httpx.get(f"{base}/api/tasks/{task_id}/perception/requests",
                            timeout=30.0, **_authed()).json()
            requests = pr.get("requests", [])
            for request in requests:
                request["sheet_url"] = (
                    f"{base}/api/tasks/{task_id}/perception/requests/"
                    f"{request['request_id']}/sheet")
            out["awaiting_perception"] = {
                "pending": pr.get("pending", 0),
                "requests": requests,
            }
        return out

    @mcp.tool()
    def download_task_result(task_id: str, dest_dir: str) -> str:
        from .client import BioChemInsightClient
        dest = BioChemInsightClient().download_result(
            task_id, Path(dest_dir) / f"{task_id}.zip")
        return str(dest)

    @mcp.tool()
    def build_extraction_report(task_dir: str, out_path: str,
                                title: str = "") -> str:
        return str(report.build_report(task_dir, out_path, title))

    @mcp.tool()
    def task_tables(task_id: str, table: str = "structures") -> list[dict]:
        """Read a finished run's table inline: structures, assays, merged
        or sar. Returns the CSV rows as objects — no file download
        needed for quick inspection."""
        import httpx as _httpx
        from .config import biocheminsight_url
        allowed = {"structures", "assays", "merged", "sar"}
        if table not in allowed:
            raise ValueError(f"table must be one of {sorted(allowed)}")
        r = _httpx.get(
            f"{biocheminsight_url().rstrip('/')}/api/tasks/{task_id}/{table}",
            timeout=60.0, **_authed())
        r.raise_for_status()
        payload = r.json()
        return payload.get("rows") or payload.get(table) or payload.get("results") or []

    @mcp.tool()
    def cancel_task(task_id: str) -> dict:
        """Cancel a running pipeline task."""
        import httpx as _httpx
        from .config import biocheminsight_url
        r = _httpx.post(
            f"{biocheminsight_url().rstrip('/')}/api/tasks/{task_id}/cancel",
            timeout=30.0, **_authed())
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
                         x: float, y: float, w: float, h: float,
                         page: int = 1) -> dict:
        """Decode one boxed region of a rendered page into SMILES. The
        region is specified in the image's pixel coordinates. Use after
        detection to confirm and commit a structure."""
        from .config import harness_url
        with open(page_image_path, "rb") as handle:
            r = httpx.post(
                f"{harness_url().rstrip('/')}/v1/structures/recognize",
                files={"file": handle}, timeout=180.0)
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
                       timeout=120.0, **_authed())
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
            files={"file": ("smiles.txt", smiles.encode())}, timeout=120.0, **_authed())
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
                data={"smiles": smiles}, timeout=180.0, **_authed())
        r.raise_for_status()
        return r.json()

    @mcp.tool()
    def open_review_workspace(task_id: str) -> dict:
        from .frontend import review_workspace_url
        return {"url": review_workspace_url(task_id), "task_id": task_id}

    @mcp.tool()
    def task_artifact_urls(task_id: str) -> dict:
        """Browser URLs for the finished run's structures, assays and
        merged-relationship tables."""
        from . import frontend
        return {"task_id": task_id,
                "structures": frontend.structures_url(task_id),
                "assays": frontend.assays_url(task_id),
                "merged": frontend.merged_url(task_id)}

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
                              timeout=60.0, **_authed())
        response.raise_for_status()
        payload = response.json()
        session_id = payload.get("session_id")
        prompt = payload.get("prompt")
        if prompt:
            path = Path(out_dir) / f"review_{session_id[:8]}_0.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(prompt, ensure_ascii=False, indent=1),
                            encoding="utf-8")
            return {"session_id": session_id, "prompt_file": str(path)}
        return {"session_id": session_id, "done": True}

    @mcp.tool()
    def measurement_review_submit(session_id: str, answer_file: str,
                                  out_dir: str) -> dict:
        """Submit an answered prompt file. Returns the next prompt or the
        final result."""
        answer = Path(answer_file).read_text(encoding="utf-8")
        base = f"{harness_url().rstrip('/')}/v1/harness/measurement-review"
        response = httpx.post(f"{base}/{session_id}/submit",
                              json={"answer": answer}, timeout=120.0, **_authed())
        response.raise_for_status()
        payload = response.json()
        prompt = payload.get("prompt")
        import re
        prior = [
            int(match.group(1))
            for path in Path(out_dir).glob(f"review_{session_id[:8]}_*.txt")
            if (match := re.fullmatch(
                rf"review_{re.escape(session_id[:8])}_(\d+)\.txt", path.name))
        ]
        index = max(prior, default=-1) + 1
        if prompt:
            path = Path(out_dir) / f"review_{session_id[:8]}_{index}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(prompt, ensure_ascii=False, indent=1),
                            encoding="utf-8")
            return {"session_id": session_id, "next_prompt_file": str(path)}
        return {"done": True, "result": payload.get("result")}

    return mcp

def main():
    create_server().run()

if __name__ == "__main__":
    main()
