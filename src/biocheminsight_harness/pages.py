"""Page rendering: dual-channel extraction for PDF and scanned documents.

Two extraction paths:
  native — pdfimages extracts the embedded scan at its original resolution;
           correct for scanned patents where pdftoppm downsamples and loses
           detail
  render — pdftoppm renders the page for PDFs with text layers or vector
           content

The caller selects the path; `detect_best` picks based on whether the PDF
page has an embedded image."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import paddleocr_url


class PDFRendererUnavailable(RuntimeError):
    pass


def _require(*tools: str) -> None:
    for tool in tools:
        if shutil.which(tool) is None:
            raise PDFRendererUnavailable(f"{tool} is required")


def extract_native(pdf_path: str | Path, page: int,
                   out_path: str | Path) -> Path:
    """Extract the embedded page image at native resolution (pdfimages)."""
    _require("pdfimages")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.parent / f"_raw_{out.name}"
    subprocess.run(
        ["pdfimages", "-f", str(page), "-l", str(page),
         "-png", str(pdf_path), str(raw)],
        check=True, capture_output=True,
    )
    found = sorted(out.parent.glob(f"_raw_{out.stem}*.png"))
    if not found:
        raise RuntimeError(f"page {page}: no embedded image")
    found[0].rename(out)
    return out


def extract_page_images(pdf_path: str | Path, pages: list[int],
                        out_dir: str | Path) -> list[Path]:
    """Extract every embedded image on the given pages (chart crops,
    structure plates). Returns the saved paths in page order."""
    _require("pdfimages")
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for page in sorted(dict.fromkeys(int(p) for p in pages)):
        base = root / f"_page_{page}"
        subprocess.run(
            ["pdfimages", "-f", str(page), "-l", str(page),
             "-png", str(pdf_path), str(base)],
            check=True, capture_output=True,
        )
        found = sorted(root.glob(f"_page_{page}*.png"))
        if not found:
            raise RuntimeError(f"page {page}: no embedded image")
        for index, image in enumerate(found):
            target = root / f"page_{page}_img_{index}.png"
            image.rename(target)
            saved.append(target)
    return saved


def render_page(pdf_path: str | Path, page: int, out_path: str | Path,
                dpi: int = 150) -> Path:
    """Render a page via pdftoppm (for PDFs with text layers)."""
    _require("pdftoppm")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi),
         "-png", str(pdf_path), str(out.with_suffix(""))],
        check=True, capture_output=True,
    )
    rendered = sorted(out.parent.glob(out.stem + "*.png"))
    if not rendered:
        raise RuntimeError(f"page {page} rendered nothing")
    rendered[0].rename(out)
    return out


def render_contact_sheet(pdf_path: str | Path, pages: list[int],
                         out_path: str | Path, columns: int = 4,
                         thumb_width: int = 320, dpi: int = 100) -> Path:
    from PIL import Image

    _require("pdftoppm")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    thumbs: list[tuple[int, Image.Image]] = []
    with tempfile.TemporaryDirectory(prefix="bch-sheets-") as tmp:
        tmp_path = Path(tmp)
        for page in pages:
            base = tmp_path / f"p{page}"
            subprocess.run(
                ["pdftoppm", "-f", str(page), "-l", str(page), "-r",
                 str(dpi), "-png", str(pdf_path), str(base)],
                check=True, capture_output=True,
            )
            found = sorted(tmp_path.glob(base.name + "*.png"))
            if not found:
                continue
            image = Image.open(found[0])
            scale = thumb_width / image.width
            image = image.resize(
                (thumb_width, max(1, int(image.height * scale))))
            thumbs.append((page, image))
        if not thumbs:
            raise RuntimeError("contact sheet produced nothing")

        cell_height = max(image.height for _, image in thumbs)
        rows = -(-len(thumbs) // columns)
        sheet = Image.new("RGB",
                          (columns * thumb_width, rows * cell_height),
                          "white")
        for index, (page, image) in enumerate(thumbs):
            sheet.paste(image, ((index % columns) * thumb_width,
                                (index // columns) * cell_height))
        sheet.save(out)
    return out


def tempfile_dir() -> Path:
    import tempfile
    return Path(tempfile.mkdtemp(prefix="bch-pages-"))
