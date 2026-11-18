import json
from pathlib import Path
from circuit_agent.domain import State
from circuit_agent.orchestrator import Orchestrator
from circuit_agent.storage import ProjectStore
from circuit_agent.validation import validate_circuit_ir,verify

ROOT=Path(__file__).parents[1]
def spec(): return json.loads((ROOT/"examples/rc_lowpass/spec.json").read_text())
def test_rc_ir_is_valid(): assert validate_circuit_ir(spec()["circuit_ir"]) == []
def test_missing_measurement_never_passes(): assert verify(spec()["requirements"],[])[0]["status"] == "not_tested"
def test_artifact_only_workflow_requires_approval(tmp_path):
 store=ProjectStore(tmp_path/"data.db",tmp_path/"runs"); pid=store.create_project(spec()); engine=Orchestrator(store)
 engine.run(pid); assert store.project(pid)["status"] == State.AWAITING_SIMULATION_APPROVAL
 design=store.latest_artifact(pid,"circuit_ir"); store.approve(pid,"design",str(design["revision"])); engine.resume(pid)
 assert store.project(pid)["status"] == State.COMPLETED_WITH_WARNINGS
 assert store.latest_artifact(pid,"report") is not None
