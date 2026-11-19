from __future__ import annotations
import json, math, shutil, subprocess
from pathlib import Path
from .domain import SimulatorNotConfigured
from .tools import generate_ltspice_asc, generate_spice_netlist

class LTspiceAdapter:
    name="ltspice"
    def __init__(self, executable:str=""): self.executable=executable
    def capabilities(self)->dict: return {"available":bool(self.executable),"analyses":["op","transient","ac","dc"],"raw_parsing":False,"asc_symbols":["resistor","capacitor","voltage_source"]}
    def prepare(self,ir:dict,workspace:Path)->dict:
        workspace.mkdir(parents=True,exist_ok=True); net=workspace/"design.cir"; asc=workspace/"design.asc"; net.write_text(generate_spice_netlist(ir)); asc.write_text(generate_ltspice_asc(ir)); return {"netlist":str(net),"asc":str(asc),"adapter":self.name}
    def run(self,prepared:dict,timeout_s:int=180)->dict:
        if not self.executable: raise SimulatorNotConfigured("LTspice executable is not configured")
        result=subprocess.run([self.executable,"-b",prepared["netlist"]],cwd=str(Path(prepared["netlist"]).parent),capture_output=True,text=True,timeout=timeout_s,check=False)
        return {"status":"completed" if result.returncode==0 else "failed","exit_code":result.returncode,"stdout":result.stdout[-6000:],"stderr":result.stderr[-6000:],"log":str(Path(prepared["netlist"]).with_suffix(".log"))}
class ProteusHandoffAdapter:
    name="proteus_handoff"
    def __init__(self, bridge_executable:str="", template_project:str=""): self.bridge_executable,self.template_project=bridge_executable,template_project
    def capabilities(self)->dict: return {"available":True,"native_automation":bool(self.bridge_executable and self.template_project),"status":"handoff_only"}
    def prepare(self,ir:dict,workspace:Path)->dict:
        workspace.mkdir(parents=True,exist_ok=True); (workspace/"circuit_ir.json").write_text(__import__("json").dumps(ir,indent=2)); (workspace/"design.cir").write_text(generate_spice_netlist(ir))
        manifest={"schema_version":"1.0","design_id":ir["design_id"],"target":"proteus","template_project":self.template_project or None,"bridge_command":"configured-by-host" if self.bridge_executable else None,"expected_outputs":["project-file"],"status":"prepared"}; (workspace/"manifest.json").write_text(__import__("json").dumps(manifest,indent=2)); return {"adapter":self.name,"handoff":str(workspace),"manifest":manifest}

class FakeSimulatorAdapter:
    """Deterministic educational fixture adapter; never represents LTspice evidence."""
    name = "fake"
    def capabilities(self) -> dict:
        return {"available": True, "fixture_only": True, "analyses": ["op", "transient", "ac", "dc"]}
    def prepare(self, ir: dict, workspace: Path) -> dict:
        workspace.mkdir(parents=True, exist_ok=True)
        input_path = workspace / "fake_input_ir.json"
        input_path.write_text(json.dumps(ir, indent=2), encoding="utf-8")
        return {"adapter": self.name, "input": str(input_path), "workspace": str(workspace)}
    def run(self, prepared: dict, timeout_s: int = 0) -> dict:
        ir = json.loads(Path(prepared["input"]).read_text(encoding="utf-8"))
        components = {c["ref"]: c for c in ir["components"]}
        resistors = [c for c in components.values() if c["kind"] == "resistor"]
        capacitors = [c for c in components.values() if c["kind"] == "capacitor"]
        measurements: list[dict] = []
        if resistors and capacitors:
            r = resistors[0]["parameters"]["resistance_ohm"]
            c = capacitors[0]["parameters"]["capacitance_farad"]
            cutoff = 1 / (2 * math.pi * r * c)
            for definition in ir.get("measurements", []):
                if definition["id"] == "cutoff_frequency_hz":
                    measurements.append({"id": definition["id"], "value": cutoff, "unit": "Hz", "signal": definition["signal"], "extraction_method": "deterministic_fake_rc_transfer_function", "sample_count": None})
        output = Path(prepared["workspace"]) / "fake_results.json"
        output.write_text(json.dumps({"measurements": measurements}, indent=2), encoding="utf-8")
        return {"status": "completed", "exit_code": 0, "simulator_version": "fake-1.0", "result_file": str(output), "measurements": measurements, "warnings": ["Fake simulator output is a deterministic test fixture, not physical or LTspice evidence."]}
