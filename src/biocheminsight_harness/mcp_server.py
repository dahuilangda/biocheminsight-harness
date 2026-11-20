"""MCP server: BioChemInsight tools for coding agents."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import chemistry, decisions, ocr, pages, report


def create_server():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("biocheminsight-harness")

    @mcp.tool()
    def parse_peptide_notation(notation: str) -> dict:
        """Split a peptide linear notation into tokens and terminal markers."""
        return chemistry.parse_notation(notation)

    @mcp.tool()
    def resolve_peptide_notation(notation: str, declared_mass: float | None = None,
                                 form: str = "", seq_id: str = "") -> dict:
        """Run the evidence ladder and mass arbitration for one notation row."""
        return chemistry.resolve_notation(notation, declared_mass, form, seq_id)

    @mcp.tool()
    def peptide_fragment_forms(smiles: str) -> dict:
        """Backbone and cap forms of a candidate fragment under the contracts."""
        return chemistry.fragment_forms(smiles)

    @mcp.tool()
    def mass_arbitration(smiles: str, declared_mass: float,
                         tolerance: float = 0.8) -> dict:
        """Dual-convention (exact or average) mass check for a reading."""
        return chemistry.mass_verdict(smiles, declared_mass, tolerance)

    @mcp.tool()
    def render_pages(pdf_path: str, pages: list[int], out_path: str,
                     columns: int = 4, thumb_width: int = 320) -> str:
        """Render pages onto one contact-sheet image; look at it to decide
        what each page contains."""
        out = pages.render_contact_sheet(pdf_path, pages, out_path, columns,
                                         thumb_width)
        return str(out)

    @mcp.tool()
    def render_page(pdf_path: str, page: int, out_path: str,
                    dpi: int = 150) -> str:
        """Render one page at reading resolution."""
        return str(pages.render_page(pdf_path, page, out_path, dpi))

    @mcp.tool()
    def record_structure_detection(out_path: str, decisions: list[dict]) -> dict:
        """Validate and store per-page structure decisions answered by the
        agent from a contact sheet. Returns the detected page numbers."""
        model = decisions.record_structure_detection(
            out_path, {"decisions": decisions})
        return {"detected_pages": model.detected_pages(),
                "pages": len(model.decisions)}

    @mcp.tool()
    def record_measurement_discovery(out_path: str, decisions: list[dict]) -> dict:
        """Validate and store per-page measurement-evidence answers. Returns
        selected pages, failed pages and discovered assay names."""
        model = decisions.record_measurement_discovery(
            out_path, {"decisions": decisions})
        return {"selected_pages": model.selected_pages(),
                "failed_pages": model.failed_pages(),
                "assay_names": model.assay_names()}

    @mcp.tool()
    def record_assay_reconciliation(out_path: str, decisions: list[dict]) -> dict:
        """Validate and store assay-name reconciliation actions."""
        model = decisions.record_assay_reconciliation(
            out_path, {"decisions": decisions})
        return {"decisions": len(model.decisions)}

    @mcp.tool()
    def ocr_pages(pdf_path: str, pages: list[int], out_path: str,
                  lang: str = "en") -> str:
        """OCR pages through the paddle VL-1.6 service; returns the markdown
        file path."""
        client = ocr.OcrClient()
        markdowns = client.pages_markdown(pdf_path, pages, lang)
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(markdowns, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        return str(out)

    @mcp.tool()
    def upload_pdf(path: str) -> str:
        """Upload a PDF to a running BioChemInsight deployment."""
        from .client import BioChemInsightClient

        return BioChemInsightClient().upload_pdf(path)

    @mcp.tool()
    def start_full_pipeline(pdf_id: str, strictness: str = "strict",
                            assemble_markush: bool = True) -> str:
        """Start the full extraction pipeline on the server; returns a task id."""
        from .client import BioChemInsightClient

        return BioChemInsightClient().start_full_pipeline(
            pdf_id, strictness, assemble_markush)

    @mcp.tool()
    def task_status(task_id: str) -> dict:
        """Status, progress and message of a pipeline task."""
        from .client import BioChemInsightClient

        client = BioChemInsightClient()
        task = client.task(task_id)
        return {"status": task.get("status"), "progress": task.get("progress"),
                "message": task.get("message"), "error": task.get("error")}

    @mcp.tool()
    def download_task_result(task_id: str, dest_dir: str) -> str:
        """Download the finished task bundle and return the zip path."""
        from .client import BioChemInsightClient

        dest = BioChemInsightClient().download_result(
            task_id, Path(dest_dir) / f"{task_id}.zip")
        return str(dest)

    @mcp.tool()
    def build_extraction_report(task_dir: str, out_path: str,
                                title: str = "") -> str:
        """Assemble a markdown report from a finished run's artifacts."""
        out = report.build_report(task_dir, out_path, title)
        return str(out)

    return mcp


def main():
    create_server().run()


if __name__ == "__main__":
    main()
