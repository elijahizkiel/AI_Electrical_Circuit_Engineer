from __future__ import annotations
from .domain import CircuitAgentError

class ToolPermissionError(CircuitAgentError): pass

ROLE_TOOLS = {
    "requirements_analyst": {"validate_requirements"},
    "circuit_architect": {"lookup_component"},
    "design_engineer": {"lookup_component", "validate_circuit_ir"},
    "design_reviewer": {"validate_circuit_ir"},
    "simulator_preparation": {"generate_spice_netlist", "generate_ltspice_asc", "prepare_proteus_handoff"},
    "waveform_analyst": {"parse_simulation_log", "analyze_csv_waveform"},
    "verification": {"verify_measurements"},
    "optimizer": {"propose_parameter_sweep"},
    "report_agent": {"write_report"},
}

def require_tool_permission(role: str, tool: str) -> None:
    if tool not in ROLE_TOOLS.get(role, set()): raise ToolPermissionError(f"{role} is not allowed to invoke {tool}")
