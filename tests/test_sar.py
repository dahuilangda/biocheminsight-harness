"""SAR table builder and summary."""
import pytest

from biocheminsight_harness.sar import build_sar_table, sar_summary, _seq_id


def test_seq_id_extraction():
    assert _seq_id("ac-I-H-Ogl-T-I (SEQ ID NO:163)") == 163
    assert _seq_id("compound with SEQ ID NO. 42") == 42
    assert _seq_id("no seq id here") is None
    assert _seq_id("") is None


def test_build_sar_table_joins_on_seq_id():
    structures = [
        {"seq_id": 163, "notation": "ac-I-H-Ogl-T-I", "smiles": "CC",
         "form": "M", "mass": 1970.355, "page": 325},
        {"seq_id": 165, "notation": "ac-I- T-Tba-T", "smiles": "CCC",
         "form": "M", "mass": 1976.311, "page": 325},
    ]
    measurements = [
        {"seq_id": 163, "endpoint": "IC50", "value": "12", "unit": "nM",
         "assay_name": "HEK Blue"},
        {"seq_id": 165, "endpoint": "IC50", "value": "5", "unit": "nM",
         "assay_name": "HEK Blue"},
    ]
    result = build_sar_table(structures, measurements)
    assert result["joined"] == 2
    assert len(result["sar_rows"]) == 2
    assert result["structure_only"] == []
    assert result["assay_only"] == []
    assert result["sar_rows"][0]["smiles"] == "CC"
    assert result["sar_rows"][0]["value"] == "12"


def test_orphan_measurements_surface():
    structures = [{"seq_id": 163, "notation": "x", "smiles": "CC",
                   "form": "M", "mass": 100.0, "page": 1}]
    measurements = [{"seq_id": 999, "endpoint": "IC50", "value": "5",
                     "unit": "nM"}]
    result = build_sar_table(structures, measurements)
    assert result["joined"] == 0
    assert len(result["assay_only"]) == 1


def test_sar_summary_ranks_by_potency():
    rows = [
        {"endpoint": "IC50", "value": "12", "notation": "comp-A"},
        {"endpoint": "IC50", "value": "0.5", "notation": "comp-B"},
        {"endpoint": "IC50", "value": "500", "notation": "comp-C"},
    ]
    lines = sar_summary(rows)
    assert len(lines) == 1
    assert "comp-B" in lines[0] and "0.5" in lines[0]
