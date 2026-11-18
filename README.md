# AI Electrical Circuit Agent v0.4

A local-first, provider-neutral workflow for **low-voltage educational and laboratory circuit simulations**. It persists projects in SQLite, keeps immutable content-hashed artifacts, requires approval before simulator execution, and separates deterministic validation from agent reasoning.

It is not a physical-design, safety-certification, mains, high-energy, medical, or real-world protective-system tool. Simulation results require human review before any physical implementation.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
circuit-agent validate examples/rc_lowpass/spec.json
circuit-agent create examples/rc_lowpass/spec.json
circuit-agent run PROJECT_ID
circuit-agent approve PROJECT_ID --subject design --revision 1
circuit-agent resume PROJECT_ID
circuit-agent export PROJECT_ID --out exports/PROJECT_ID
```

The default mock agents complete the RC example without credentials or a simulator. With no configured simulator, the workflow produces a reproducible artifact package and explicitly records that no simulation evidence exists.

## Supported first-release capabilities

- RC low-pass architecture/design in mock mode; structured requirements may also provide an explicit `circuit_ir`.
- Resistor, capacitor, and ideal voltage-source IR components.
- SPICE netlist and limited LTspice `.asc` generation.
- LTspice batch adapter when explicitly configured; Proteus handoff bundle with a trusted configured bridge only.
- `.log` and CSV measurement parsing; deterministic numeric verification.
- SQLite projects/tasks/artifacts/events/approvals and safe state transitions.

See [AGENTS.md](AGENTS.md) for the complete v0.4 contract and [examples/rc_lowpass/spec.json](examples/rc_lowpass/spec.json) for a runnable fixture.
