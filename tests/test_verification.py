"""Multi-evidence cross-validation tests."""
from biocheminsight_harness.verification import (
    seq_id_coverage, dual_source_consistency,
    completeness_check, cross_check)


def test_seq_id_coverage_finds_gaps():
    result = seq_id_coverage([163, 164, 166, 167])
    assert result["gaps"] == [165]
    assert result["found"] == 4
    assert result["expected"] == 5


def test_seq_id_coverage_no_gaps():
    result = seq_id_coverage([163, 164, 165])
    assert result["gaps"] == []


def test_dual_source_consistent():
    result = dual_source_consistency("CCO", "OCC")
    assert result["verdict"] == "consistent"


def test_dual_source_disagreed():
    result = dual_source_consistency("CCO", "CCC")
    assert result["verdict"] == "disagreed"


def test_cross_check_agreement():
    readings = [
        {"compound_id": "C1", "value": "12"},
        {"compound_id": "C1", "value": "12"},
    ]
    result = cross_check(readings, ["compound_id", "value"])
    assert result["verdict"] == "consistent"


def test_cross_check_disagreement():
    readings = [
        {"compound_id": "C1", "value": "12"},
        {"compound_id": "C1", "value": "24"},
    ]
    result = cross_check(readings, ["compound_id", "value"])
    assert result["verdict"] == "disagreed"
    assert result["field"] == "value"
