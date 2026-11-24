import subprocess

import pytest

from biocheminsight_harness.pages import extract_page_images, render_page


def test_extract_page_images_names_by_page(tmp_path, monkeypatch):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    def fake_run(cmd, check, capture_output):
        prefix = cmd[-1]
        for index in range(2):
            (tmp_path / f"{prefix}-{index:0{len('-0')}}.png").touch()
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = extract_page_images(pdf, [21], tmp_path / "imgs")
    assert [p.name for p in out] == ["page_21_img_0.png", "page_21_img_1.png"]
    assert all(p.exists() for p in out)


def test_extract_page_images_raises_without_images(tmp_path, monkeypatch):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, check, capture_output: subprocess.CompletedProcess(cmd, 0))
    with pytest.raises(RuntimeError):
        extract_page_images(pdf, [5], tmp_path / "imgs")


def test_render_contact_sheet_captions_each_panel(tmp_path, monkeypatch):
    from PIL import Image

    from biocheminsight_harness.pages import render_contact_sheet

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    def fake_run(cmd, check, capture_output):
        prefix = cmd[-1]
        Image.new("RGB", (800, 1000), "white").save(f"{prefix}-0.png")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = render_contact_sheet(pdf, [3, 1, 22, 7], tmp_path / "sheet.png",
                               columns=2, thumb_width=320)
    sheet = Image.open(out).convert("L")
    cell_height = sheet.height // 2
    for index in range(4):
        left, top = (index % 2) * 320, (index // 2) * cell_height
        band = sheet.crop((left, top, left + 320, top + 18))
        dark = sum(band.histogram()[:40]) / (320 * 18)
        assert dark > 0.95
        assert sheet.getpixel((left + 4, top + 40)) > 200
