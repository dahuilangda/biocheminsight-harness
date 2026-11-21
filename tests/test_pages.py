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
