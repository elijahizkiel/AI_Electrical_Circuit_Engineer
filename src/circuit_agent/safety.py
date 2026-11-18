from __future__ import annotations

import re
from .domain import ScopeResult

BLOCKED = (r"\bmains\b", r"\b(120|230|240)\s*v(?:ac)?\b", r"high[- ]energy", r"safety[- ]critical", r"medical device", r"defibrillator", r"real[- ]world (?:installation|protective)", r"high voltage")
AMBIGUOUS = (r"\bpower supply\b", r"\btransformer\b", r"\bgrid\b")

def check_scope(request: str, payload: dict) -> ScopeResult:
    text = (request + " " + str(payload)).lower()
    hits = [pattern for pattern in BLOCKED if re.search(pattern, text)]
    if hits:
        return ScopeResult(False, "out_of_scope", ["Hazardous or excluded scope keyword detected."])
    supply = payload.get("supply", {})
    max_v = supply.get("max_voltage_v")
    if max_v is not None and (not isinstance(max_v, (int, float)) or max_v > 24 or max_v < 0):
        return ScopeResult(False, "out_of_scope", ["Only explicit 0–24 V educational simulations are supported."])
    if not max_v and any(re.search(p, text) for p in AMBIGUOUS):
        return ScopeResult(False, "needs_clarification", ["Specify a low-voltage supply limit before design."])
    return ScopeResult(True, "low_voltage_educational", ["Simulation evidence is not proof of physical safety."])
