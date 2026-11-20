"""Perception contract validation."""
import pytest
from pydantic import ValidationError

from biocheminsight_harness import decisions


def test_structure_detection_keeps_detected_pages():
    model = decisions.record_structure_detection(
        "/tmp/detect.json",
        {"decisions": [
            {"page": 58, "has_structure": True, "confidence": "high",
             "reason": "dense rotated table"},
            {"page": 12, "has_structure": False, "confidence": "high",
             "reason": "prose"},
        ]})
    assert model.detected_pages() == [58]
    loaded = decisions.load_json("/tmp/detect.json")
    assert loaded["decisions"][0]["page"] == 58


def test_structure_detection_rejects_bad_confidence():
    with pytest.raises(ValidationError):
        decisions.record_structure_detection(
            "/tmp/detect.json",
            {"decisions": [{"page": 1, "has_structure": True,
                            "confidence": "certain"}]})


def test_measurement_discovery_groups_outputs():
    model = decisions.record_measurement_discovery(
        "/tmp/discovery.json",
        {"decisions": [
            {"page": 30, "has_assay_data": True, "confidence": "high",
             "assay_names": ["IC50"], "reason": "potency table"},
            {"page": 31, "has_assay_data": False, "confidence": "high",
             "assay_names": [], "reason": "prose"},
            {"page": 32, "has_assay_data": None, "confidence": "low",
             "assay_names": [], "reason": "unreadable"},
        ]})
    assert model.selected_pages() == [30]
    assert model.failed_pages() == [32]
    assert model.assay_names() == ["IC50"]


def test_reconciliation_merge_target_must_exist():
    with pytest.raises(ValidationError):
        decisions.record_assay_reconciliation(
            "/tmp/reconcile.json",
            {"decisions": [{"candidate_id": "a2", "action": "merge",
                            "canonical_candidate_id": "a9",
                            "confidence": "high", "evidence": "same"}]})


def test_reconciliation_accepts_valid_actions():
    model = decisions.record_assay_reconciliation(
        "/tmp/reconcile.json",
        {"decisions": [
            {"candidate_id": "a1", "action": "rename",
             "canonical_assay_name": "IL-17 HEK Blue IC50",
             "confidence": "high", "evidence": "header"},
            {"candidate_id": "a2", "action": "drop", "confidence": "high",
             "evidence": "duplicate"},
        ]})
    assert len(model.decisions) == 2
