"""Page rendering for the perception round-trip: the harness renders, the
agent looks."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class PDFRendererUnavailable(RuntimeError):
    pass


def _require_pdftoppm() -> None:
    if shutil.which("pdftoppm") is None:
        raise PDFRendererUnavailable("pdftoppm is required to render pages")


def render_page(pdf_path: str | Path, page: int, out_path: str | Path,
                dpi: int = 150) -> Path:
    _require_pdftoppm()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    base = out.with_suffix("")
    subprocess.run(
        ["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi),
         "-png", str(pdf_path), str(base)],
        check=True,
    )
    rendered = sorted(out.parent.glob(base.name + "*.png"))
    if not rendered:
        raise RuntimeError(f"page {page} rendered nothing")
    rendered[0].rename(out)
    return out


def render_contact_sheet(pdf_path: str | Path, pages: list[int],
                         out_path: str | Path, columns: int = 4,
                         thumb_width: int = 320, dpi: int = 100) -> Path:
    """Lay the requested pages out on one image for a single look."""
    from PIL import Image

    _require_pdftoppm()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    thumbs: list[Image.Image] = []
    for page in pages:
        with tempfile_dir() as tmp:
            base = tmp / f"p{page}"
            subprocess.run(
                ["pdftoppm", "-f", str(page), "-l", str(page), "-r",
                 str(dpi), "-png", str(pdf_path), str(base)],
                check=True,
            )
            rendered = sorted(tmp.glob(base.name + "*.png"))
            if not rendered:
                continue
            image = Image.open(rendered[0])
            scale = thumb_width / image.width
            image = image.resize(
                (thumb_width, max(1, int(image.height * scale))))
            thumbs.append((page, image))
    if not thumbs:
        raise RuntimeError("contact sheet produced nothing")

    cell_height = max(image.height for _, image in thumbs)
    rows = -(-len(thumbs) // columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * cell_height),
                      "white")
    for index, (page, image) in enumerate(thumbs):
        x = (index % columns) * thumb_width
        y = (index // columns) * cell_height
        sheet.paste(image, (x, y))
    sheet.save(out)
    return out


def tempfile_dir() -> Path:
    import tempfile

    return Path(tempfile.mkdtemp(prefix="bch-pages-"))
