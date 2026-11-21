"""MCP server: BioChemInsight tools for coding agents."""
from __future__ import annotations

import json
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
from .config import harness_url

_states: dict[str, dict] = {}


def create_server():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("biocheminsight-harness")

    @mcp.tool()
    def parse_peptide_notation(notation: str) -> dict:
        return chemistry.parse_notation(notation)

    @mcp.tool()
    def resolve_peptide_notation(notation: str,
                                 declared_mass: float | None = None,
                                 form: str = "", seq_id: str = "") -> dict:
        return chemistry.resolve_notation(notation, declared_mass, form,
                                          seq_id)

    @mcp.tool()
    def peptide_fragment_forms(smiles: str) -> dict:
        return chemistry.fragment_forms(smiles)

    @mcp.tool()
    def mass_arbitration(smiles: str, declared_mass: float,
                         tolerance: float = 0.8) -> dict:
        return chemistry.mass_arbitration(smiles, declared_mass, tolerance)

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
    def upload_pdf(path: str) -> str:
        from .client import BioChemInsightClient
        return BioChemInsightClient().upload_pdf(path)

    @mcp.tool()
    def start_full_pipeline(pdf_id: str, strictness: str = "strict",
                            assemble_markush: bool = True) -> str:
        from .client import BioChemInsightClient
        return BioChemInsightClient().start_full_pipeline(
            pdf_id, strictness, assemble_markush)

    @mcp.tool()
    def task_status(task_id: str) -> dict:
        from .client import BioChemInsightClient
        task = BioChemInsightClient().task(task_id)
        return {"status": task.get("status"), "progress": task.get("progress"),
                "message": task.get("message"), "error": task.get("error")}

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
    def batch_merge(results_dir: str) -> dict:
        return coord.merge_decision_files(results_dir)

    @mcp.tool()
    def sar_build(structures: list[dict],
                  measurements: list[dict]) -> dict:
        return sar_mod.build_sar_table(structures, measurements)

    @mcp.tool()
    def sar_analysis(sar_rows: list[dict]) -> list[str]:
        return sar_mod.sar_summary(sar_rows)

    return mcp


def main():
    create_server().run()


if __name__ == "__main__":
    main()
