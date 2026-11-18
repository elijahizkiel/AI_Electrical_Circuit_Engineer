from __future__ import annotations

import math
import re
from .domain import SchemaValidationError

COMPONENTS = {"resistor": ({"1", "2"}, "ideal_resistor", "resistance_ohm"), "capacitor": ({"1", "2"}, "ideal_capacitor", "capacitance_farad"), "voltage_source": ({"positive", "negative"}, "ideal_voltage_source", "dc_voltage_v")}
ANALYSES = {"op", "transient", "ac", "dc"}

def validate_requirements(data: dict) -> list[str]:
    errors = []
    for item in data.get("requirements", []):
        for key in ("id", "measurement_id", "operator", "unit"):
            if not item.get(key): errors.append(f"requirement missing {key}")
        if item.get("operator") not in {"eq", "lt", "lte", "gt", "gte", "between", "abs_error_lte", "relative_error_lte"}: errors.append(f"unsupported operator: {item.get('operator')}")
    return errors

def validate_circuit_ir(ir: dict) -> list[str]:
    errors: list[str] = []
    required = {"schema_version", "design_id", "design_revision", "title", "units", "nodes", "components", "analyses", "measurements", "source_requirements"}
    unknown = set(ir) - required
    if unknown: errors.append(f"unrecognized IR fields: {sorted(unknown)}")
    if required - set(ir): errors.append(f"missing IR fields: {sorted(required-set(ir))}")
    nodes = {n.get("id") for n in ir.get("nodes", []) if isinstance(n, dict)}
    if "0" not in nodes: errors.append("ground node '0' is required")
    refs: set[str] = set()
    for c in ir.get("components", []):
        ref, kind = c.get("ref", ""), c.get("kind")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", ref): errors.append(f"invalid component ref: {ref}")
        if ref.lower() in refs: errors.append(f"duplicate component ref: {ref}")
        refs.add(ref.lower())
        if kind not in COMPONENTS: errors.append(f"{ref}: unsupported component kind {kind}"); continue
        pins, model, parameter = COMPONENTS[kind]
        if set(c.get("pins", {})) != pins: errors.append(f"{ref}: invalid pins for {kind}")
        if c.get("model") != model: errors.append(f"{ref}: unapproved model {c.get('model')}")
        if parameter not in c.get("parameters", {}) or not isinstance(c["parameters"].get(parameter), (int, float)): errors.append(f"{ref}: missing numeric {parameter}")
        if any(v not in nodes for v in c.get("pins", {}).values()): errors.append(f"{ref}: references unknown node")
        if c.get("tunable"):
            bound = c.get("bounds", {}).get(parameter, {})
            if not isinstance(bound.get("min"), (int, float)) or not isinstance(bound.get("max"), (int, float)) or bound["min"] >= bound["max"]: errors.append(f"{ref}: invalid tunable bounds")
    for a in ir.get("analyses", []):
        if a.get("kind") not in ANALYSES: errors.append(f"unsupported analysis: {a.get('kind')}")
    for m in ir.get("measurements", []):
        if not m.get("id") or not m.get("unit") or not m.get("signal"): errors.append("measurement requires id, signal, and unit")
    return errors

def require_valid_ir(ir: dict) -> None:
    if errors := validate_circuit_ir(ir): raise SchemaValidationError("; ".join(errors))

def verify(requirements: list[dict], measurements: list[dict]) -> list[dict]:
    index = {m["id"]: m for m in measurements}
    results = []
    for r in requirements:
        m = index.get(r["measurement_id"])
        if not m: results.append({"requirement_id": r["id"], "status": "not_tested", "criterion": r["operator"], "evidence": []}); continue
        value, target, op = m["value"], r["target"], r["operator"]
        if m["unit"] != r["unit"]: status, note = "inconclusive", "unit mismatch"
        else:
            checks = {"eq": lambda: value == target, "lt": lambda: value < target, "lte": lambda: value <= target, "gt": lambda: value > target, "gte": lambda: value >= target, "between": lambda: target["min"] <= value <= target["max"], "abs_error_lte": lambda: abs(value-target["value"]) <= target["tolerance"], "relative_error_lte": lambda: abs(value-target["value"])/abs(target["value"]) <= target["tolerance"]}
            status, note = ("pass" if checks[op]() else "fail"), ""
        results.append({"requirement_id": r["id"], "status": status, "observed": value, "unit": m["unit"], "criterion": f"{op} {target}", "evidence": [m.get("artifact_id", m["id"])], "note": note})
    return results
