"""Stateless roles: deterministic mock outputs are replaceable through LLMProvider."""
from __future__ import annotations
import math
from datetime import datetime, timezone
from typing import Protocol
from .validation import validate_circuit_ir, validate_requirements

class LLMProvider(Protocol):
    async def generate(self, *, system_prompt:str, user_payload:dict, response_schema:dict, model:str|None=None, timeout_s:float=60)->dict: ...

def envelope(project_id:str, task_id:str, agent:str, summary:str, warnings:list[str]|None=None)->dict:
    return {"schema_version":"1.0","project_id":project_id,"task_id":task_id,"agent":agent,"status":"success","created_at":datetime.now(timezone.utc).isoformat(),"input_artifact_ids":[],"output_artifact_ids":[],"summary":summary,"warnings":warnings or [],"errors":[]}

class RequirementsAnalyst:
    name="requirements_analyst"
    def run(self, spec:dict)->dict:
        reqs=spec.get("requirements",[]); missing=[] if reqs else ["At least one measurable requirement is required."]
        errors=validate_requirements({"requirements":reqs})
        return {"requirements":reqs,"assumptions":["Educational simulation only.","Physical implementation requires human review."],"missing_information":missing+errors,"needs_clarification":bool(missing or errors),"measurement_mapping":[{"requirement_id":r.get("id"),"measurement_id":r.get("measurement_id")} for r in reqs]}
class CircuitArchitect:
    name="circuit_architect"
    def run(self, spec:dict, requirements:dict)->dict:
        ir=spec.get("circuit_ir",{}); title=ir.get("title",spec.get("name","Circuit"));
        topology="first_order_rc_low_pass" if {c.get("kind") for c in ir.get("components",[])} >= {"resistor","capacitor"} else "user_supplied_supported_topology"
        return {"topology":topology,"block_description":"Source → passive network → output node.","rationale":"Uses a documented supported topology and ideal models for educational simulation.","alternatives":[{"topology":"active_filter","tradeoff":"Not selected: requires validated op-amp models."}],"known_limitations":["Topology is not proven until simulation and deterministic verification complete."],"source_requirements":[r["id"] for r in requirements["requirements"]],"title":title}
class DesignEngineer:
    name="design_engineer"
    def run(self,spec:dict,architecture:dict,revision:int=1)->dict:
        ir=dict(spec.get("circuit_ir",{})); ir["design_revision"]=revision; ir.setdefault("title",architecture["title"]); return {"circuit_ir":ir,"design_decisions":["IR is simulator-independent.","Only catalogued ideal R/C/V models are used."],"parameter_ranges":{c["ref"]:c.get("bounds",{}) for c in ir.get("components",[]) if c.get("tunable")}}
class DesignReviewer:
    name="design_reviewer"
    def run(self,requirements:dict,architecture:dict,design:dict)->dict:
        errors=validate_circuit_ir(design["circuit_ir"]); requirement_ids=set(design["circuit_ir"].get("source_requirements",[])); missing=[r["id"] for r in requirements["requirements"] if r["id"] not in requirement_ids]
        findings=[{"severity":"blocker","message":e,"evidence_field":"circuit_ir"} for e in errors]+[{"severity":"major","message":f"Requirement {rid} is not mapped to IR.","evidence_field":"circuit_ir.source_requirements"} for rid in missing]
        return {"status":"approved" if not findings else "changes_requested","findings":findings,"review_basis":["circuit_ir.components","circuit_ir.source_requirements"],"summary":"Deterministic independent IR validation completed."}
class Optimizer:
    name="optimizer"
    def propose(self,ir:dict, verification:list[dict], iteration:int=0)->dict:
        failures=[x for x in verification if x["status"]=="fail"]
        tunable=[c for c in ir["components"] if c.get("tunable")]
        if not failures or not tunable: return {"continue":False,"reason":"No eligible failed criterion or tunable parameter.","candidates":[]}
        c=tunable[0]; key=next(iter(c["bounds"])); current=c["parameters"][key]; bounds=c["bounds"][key]; candidate=max(bounds["min"],min(bounds["max"],current*1.1))
        return {"continue":True,"iteration":iteration,"reason":"Single bounded candidate; confirmation requires a new simulation.","candidates":[{"ref":c["ref"],"parameter":key,"value":candidate,"bounds":bounds}]}
