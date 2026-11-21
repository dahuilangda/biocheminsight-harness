"""Perception answers returned by the agent, validated before use."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class PageDecision(BaseModel):
    page: int = Field(ge=1)
    has_structure: bool
    confidence: Literal["low", "medium", "high"]
    reason: str = ""


class StructureDetection(BaseModel):
    decisions: list[PageDecision]

    def detected_pages(self) -> list[int]:
        return sorted(d.page for d in self.decisions if d.has_structure)


class MeasurementReview(BaseModel):
    page: int = Field(ge=1)
    has_assay_data: bool | None = None
    confidence: Literal["low", "medium", "high"]
    assay_names: list[str] = Field(default_factory=list)
    reason: str = ""


class MeasurementDiscovery(BaseModel):
    decisions: list[MeasurementReview]

    def selected_pages(self) -> list[int]:
        return sorted(d.page for d in self.decisions if d.has_assay_data)

    def failed_pages(self) -> list[int]:
        return sorted(d.page for d in self.decisions if d.has_assay_data is None)

    def assay_names(self) -> list[str]:
        seen: dict[str, None] = {}
        for d in self.decisions:
            for name in d.assay_names:
                seen.setdefault(name.strip(), None)
        return list(seen)


class ReconciliationAction(BaseModel):
    candidate_id: str
    action: Literal["merge", "drop", "rename"]
    canonical_candidate_id: str | None = None
    canonical_assay_name: str | None = None
    confidence: Literal["low", "medium", "high"]
    evidence: str


class AssayReconciliation(BaseModel):
    decisions: list[ReconciliationAction]

    @field_validator("decisions")
    @classmethod
    def targets_must_exist(cls, value: list[ReconciliationAction]
                           ) -> list[ReconciliationAction]:
        """Merges must land on a kept candidate with no cycles; renames
        must name the canonical assay."""
        ids = {d.candidate_id for d in value}
        edges = {}
        for d in value:
            if d.action == "merge" and d.canonical_candidate_id not in ids:
                raise ValueError(
                    f"merge target {d.canonical_candidate_id} is not a candidate")
            if d.action == "merge" and d.canonical_candidate_id == d.candidate_id:
                raise ValueError(f"{d.candidate_id} cannot merge into itself")
            if d.action == "rename" and not d.canonical_assay_name:
                raise ValueError(f"rename of {d.candidate_id} needs canonical_assay_name")
            if d.action == "merge":
                edges[d.candidate_id] = d.canonical_candidate_id
        for start in edges:
            seen = set()
            node = start
            while node in edges and node not in seen:
                seen.add(node)
                node = edges[node]
            if node in seen and node == start:
                raise ValueError(f"merge cycle at {start}")
        return value


def record_structure_detection(path: str | Path, decisions: dict[str, Any]
                               ) -> StructureDetection:
    model = StructureDetection.model_validate(decisions)
    Path(path).write_text(model.model_dump_json(indent=2),
                          encoding="utf-8")
    return model


def record_measurement_discovery(path: str | Path, decisions: dict[str, Any]
                                 ) -> MeasurementDiscovery:
    model = MeasurementDiscovery.model_validate(decisions)
    Path(path).write_text(model.model_dump_json(indent=2),
                          encoding="utf-8")
    return model


def record_assay_reconciliation(path: str | Path, decisions: dict[str, Any]
                                ) -> AssayReconciliation:
    model = AssayReconciliation.model_validate(decisions)
    Path(path).write_text(model.model_dump_json(indent=2),
                          encoding="utf-8")
    return model
