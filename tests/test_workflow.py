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

def test_fake_simulator_verifies_rc_requirement_and_persists_results(tmp_path):
 simulation_spec=spec(); simulation_spec["simulator"]="fake"
 store=ProjectStore(tmp_path/"data.db",tmp_path/"runs"); pid=store.create_project(simulation_spec); engine=Orchestrator(store)
 engine.run(pid); design=store.latest_artifact(pid,"circuit_ir"); store.approve(pid,"design",str(design["revision"])); engine.resume(pid)
 assert store.project(pid)["status"] == State.COMPLETED
 verification=store.latest_artifact(pid,"verification")["content"]["results"]
 assert verification[0]["status"] == "pass"
 assert store.conn.execute("SELECT COUNT(*) FROM simulation_runs WHERE project_id=?",(pid,)).fetchone()[0] == 1
 assert store.conn.execute("SELECT COUNT(*) FROM measurements WHERE project_id=?",(pid,)).fetchone()[0] == 1

def test_optimization_creates_reviewed_approved_immutable_design_revision(tmp_path):
 simulation_spec=spec(); simulation_spec["simulator"]="fake"; simulation_spec["optimization"]={"max_iterations":1}
 simulation_spec["requirements"][0]["target"]={"min":1400,"max":1500}
 store=ProjectStore(tmp_path/"data.db",tmp_path/"runs"); pid=store.create_project(simulation_spec); engine=Orchestrator(store)
 engine.run(pid); store.approve(pid,"design","1"); engine.resume(pid)
 assert store.project(pid)["status"] == State.OPTIMIZATION_APPROVAL
 candidate=store.latest_artifact(pid,"circuit_ir"); assert candidate["content"]["circuit_ir"]["design_revision"] == 2
 store.approve(pid,"optimization","2"); engine.resume(pid)
 assert store.project(pid)["status"] == State.AWAITING_SIMULATION_APPROVAL
 store.approve(pid,"design","2"); engine.resume(pid)
 assert store.project(pid)["status"] == State.COMPLETED
