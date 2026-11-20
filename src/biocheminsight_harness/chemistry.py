"""Deterministic peptide chemistry served by a BioChemInsight deployment."""
from __future__ import annotations

from typing import Any

import httpx

from .config import harness_url


def _post(path: str, payload: dict[str, Any], timeout: float) -> Any:
    response = httpx.post(f"{harness_url().rstrip('/')}{path}",
                          json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def parse_notation(notation: str, timeout: float = 60.0) -> Any:
    return _post("/v1/harness/parse-notation", {"notation": notation}, timeout)


def resolve_notation(notation: str, declared_mass: float | None = None,
                     form: str = "", seq_id: str = "",
                     smiles_reading: str = "",
                     timeout: float = 120.0) -> Any:
    payload = {"notation": notation, "form": form, "seq_id": seq_id,
               "smiles_reading": smiles_reading}
    if declared_mass is not None:
        payload["declared_mass"] = declared_mass
    return _post("/v1/harness/resolve-row", payload, timeout)


def fragment_forms(smiles: str, timeout: float = 60.0) -> Any:
    return _post("/v1/harness/fragment-forms", {"smiles": smiles}, timeout)


def mass_arbitration(smiles: str, declared_mass: float,
                     tolerance: float = 0.8,
                     timeout: float = 60.0) -> Any:
    return _post("/v1/harness/mass-arbitration",
                 {"smiles": smiles, "declared_mass": declared_mass,
                  "tolerance": tolerance}, timeout)
