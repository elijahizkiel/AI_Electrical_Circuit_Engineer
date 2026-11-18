from __future__ import annotations
import json
from pathlib import Path
from .agents import RequirementsAnalyst,CircuitArchitect,DesignEngineer,DesignReviewer,Optimizer
from .domain import ApprovalRequired,State
from .safety import check_scope
from .simulators import LTspiceAdapter,ProteusHandoffAdapter
from .storage import ProjectStore
from .tools import generate_ltspice_asc,generate_spice_netlist,parse_log
from .validation import verify

class Orchestrator:
    def __init__(self,store:ProjectStore, ltspice:LTspiceAdapter|None=None, proteus:ProteusHandoffAdapter|None=None):
        self.store=store; self.requirements=RequirementsAnalyst(); self.architect=CircuitArchitect(); self.engineer=DesignEngineer(); self.reviewer=DesignReviewer(); self.optimizer=Optimizer(); self.ltspice=ltspice or LTspiceAdapter(); self.proteus=proteus or ProteusHandoffAdapter()
    def _artifact(self,pid,kind,fn,agent): return self.store.task(pid,agent,kind,lambda _tid:self.store.artifact(pid,kind,fn(),agent))
    def run(self,pid:str)->dict:
        p=self.store.project(pid); spec=p["config"]; state=State(p["status"])
        if state==State.CREATED:
            self.store.transition(pid,State.SCOPE_CHECK); state=State.SCOPE_CHECK
        if state==State.SCOPE_CHECK:
            scope=check_scope(p["request_text"],spec); self.store.artifact(pid,"scope_result",scope.__dict__,"scope_gate")
            if not scope.allowed: self.store.transition(pid,State.NEEDS_CLARIFICATION if scope.classification=="needs_clarification" else State.FAILED); return self.store.project(pid)
            self.store.transition(pid,State.REQUIREMENTS_ANALYSIS); state=State.REQUIREMENTS_ANALYSIS
        if state==State.REQUIREMENTS_ANALYSIS:
            req=self._artifact(pid,"requirements",lambda:self.requirements.run(spec),self.requirements.name)
            if req["content"]["needs_clarification"]: self.store.transition(pid,State.NEEDS_CLARIFICATION); return self.store.project(pid)
            self.store.transition(pid,State.REQUIREMENTS_READY); state=State.REQUIREMENTS_READY
        if state==State.REQUIREMENTS_READY: self.store.transition(pid,State.ARCHITECTURE_DESIGN); state=State.ARCHITECTURE_DESIGN
        req=self.store.latest_artifact(pid,"requirements")["content"]
        if state==State.ARCHITECTURE_DESIGN:
            self._artifact(pid,"architecture",lambda:self.architect.run(spec,req),self.architect.name); self.store.transition(pid,State.CIRCUIT_DESIGN); state=State.CIRCUIT_DESIGN
        arch=self.store.latest_artifact(pid,"architecture")["content"]
        if state in {State.CIRCUIT_DESIGN,State.DESIGN_REVISION}:
            if state==State.DESIGN_REVISION: self.store.transition(pid,State.CIRCUIT_DESIGN)
            design=self._artifact(pid,"circuit_ir",lambda:self.engineer.run(spec,arch),self.engineer.name); self.store.transition(pid,State.DESIGN_REVIEW); state=State.DESIGN_REVIEW
        design=self.store.latest_artifact(pid,"circuit_ir")["content"]
        if state==State.DESIGN_REVIEW:
            review=self._artifact(pid,"design_review",lambda:self.reviewer.run(req,arch,design),self.reviewer.name)
            if review["content"]["status"]!="approved": self.store.transition(pid,State.DESIGN_REVISION); return self.store.project(pid)
            self.store.transition(pid,State.DESIGN_APPROVAL); state=State.DESIGN_APPROVAL
        if state==State.DESIGN_APPROVAL: self.store.transition(pid,State.SIMULATION_PREPARATION); state=State.SIMULATION_PREPARATION
        if state==State.SIMULATION_PREPARATION:
            ir=design["circuit_ir"]; plan={"requested":spec.get("simulator","none"),"netlist":generate_spice_netlist(ir),"asc":generate_ltspice_asc(ir),"capabilities":{"ltspice":self.ltspice.capabilities(),"proteus":self.proteus.capabilities()}}
            self.store.artifact(pid,"simulation_plan",plan,"simulator_preparation"); self.store.transition(pid,State.AWAITING_SIMULATION_APPROVAL)
        return self.store.project(pid)
    def resume(self,pid:str)->dict:
        p=self.store.project(pid)
        if State(p["status"]) != State.AWAITING_SIMULATION_APPROVAL: return self.run(pid)
        design=self.store.latest_artifact(pid,"circuit_ir");
        if not self.store.approved(pid,"design",str(design["revision"])): raise ApprovalRequired("Approve the design revision before simulator execution.")
        spec=p["config"]; selected=spec.get("simulator","none")
        # Artifact-only mode deliberately does not enter SIMULATION_RUNNING.
        if selected=="none": self.store.transition(pid,State.REPORT_GENERATION); return self._report(pid, warning=True)
        self.store.transition(pid,State.SIMULATION_RUNNING)
        ir=design["content"]["circuit_ir"]; work=self.store.artifact_root/pid/"simulation"
        adapter=self.ltspice if selected=="ltspice" else self.proteus; prepared=adapter.prepare(ir,work)
        if selected=="proteus": run={"status":"prepared","exit_code":None,"prepared":prepared}
        else: run=adapter.run(prepared)
        self.store.artifact(pid,"simulation_run",run,"simulator_adapter",[design["artifact_id"]]); self.store.transition(pid,State.WAVEFORM_ANALYSIS)
        measurements=[]
        if run.get("log") and Path(run["log"]).is_file(): measurements,warnings=parse_log(Path(run["log"]))
        self.store.artifact(pid,"measurements",{"measurements":measurements,"warnings":warnings if run.get("log") else ["No supported measurement output available."]},"waveform_analyst"); self.store.transition(pid,State.REQUIREMENT_VERIFICATION)
        verification=verify(req:=self.store.latest_artifact(pid,"requirements")["content"]["requirements"],measurements); self.store.artifact(pid,"verification",{"results":verification},"verification")
        self.store.transition(pid,State.REPORT_GENERATION); return self._report(pid,warning=any(r["status"]!="pass" for r in verification))
    def _report(self,pid:str,warning:bool)->dict:
        p=self.store.project(pid); artifacts=self.store.artifacts(pid); report={"project_id":pid,"request_summary":p["request_text"],"scope_and_safety_limitations":["Low-voltage educational simulation only.","Simulation is not proof of physical safety; human review is required."],"artifacts":[{"type":a["artifact_type"],"path":a["storage_path"],"hash":a["content_hash"]} for a in artifacts],"human_review_checklist":["Review design and component/model assumptions.","Review any simulator logs and verification evidence.","Do not implement in hardware without qualified review."]}
        artifact=self.store.artifact(pid,"report",report,"report_agent")
        verification=self.store.latest_artifact(pid,"verification")
        results=(verification or {"content":{"results":[]}})["content"]["results"]
        report_path=self.store.artifact_root/pid/"report.md"
        rows="\n".join(f"| {item['requirement_id']} | {item['status']} | {item.get('criterion','not tested')} |" for item in results) or "| No simulation evidence | inconclusive | Artifact-only mode |"
        report_path.write_text(f"# Engineering report\n\n## Request summary\n\n{p['request_text']}\n\n## Scope and safety limitations\n\n- Low-voltage educational simulation only.\n- Simulation is not proof of physical safety. Human review is mandatory before physical implementation.\n\n## Requirement verification\n\n| Requirement | Status | Criterion |\n|---|---|---|\n{rows}\n\n## Human review checklist\n\n- Review models, assumptions, and simulator warnings.\n- Confirm each requirement has source-linked evidence.\n- Do not use this result as a hardware safety certification.\n\n## Reproducibility\n\nMachine-readable report artifact: `{artifact['storage_path']}`\n",encoding="utf-8")
        self.store.event(pid,"report_markdown_created","report_agent",{"path":str(report_path)}); self.store.conn.commit()
        self.store.transition(pid,State.COMPLETED_WITH_WARNINGS if warning else State.COMPLETED); return self.store.project(pid)
