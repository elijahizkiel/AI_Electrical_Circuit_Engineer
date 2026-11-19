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
# Optional local API (no arbitrary tool-execution endpoint)
circuit-agent serve --host 127.0.0.1 --port 8000
```

The web service stores its SQLite database at `data/circuit_agent.db` and artifacts under `runs/` by default. Start it with `circuit-agent serve --host 127.0.0.1 --port 8000`, then open `http://127.0.0.1:8000/`.

For API-key persistence, the application requires the `cryptography` dependency included in `pyproject.toml`. Keys are encrypted before being stored in SQLite and are never returned by the API. By default a local master key is created at `data/circuit_agent.master.key` with restrictive permissions. For managed deployments, set `CIRCUIT_AGENT_MASTER_KEY` to a Fernet key instead and protect it outside the database. Back up the master key securely; losing it makes stored API keys unrecoverable.

The default mock agents complete the RC example without credentials or a simulator. With no configured simulator, the workflow produces a reproducible artifact package and explicitly records that no simulation evidence exists. LTspice is required only when selecting `"simulator": "ltspice"`; it is not needed for validation, artifact-only projects, or the deterministic `"fake"` test adapter.

## Supported first-release capabilities

- RC low-pass architecture/design in mock mode; structured requirements may also provide an explicit `circuit_ir`.
- Resistor, capacitor, and ideal voltage-source IR components.
- SPICE netlist and limited LTspice `.asc` generation.
- LTspice batch adapter when explicitly configured; Proteus handoff bundle with a trusted configured bridge only.
- Deterministic fake simulator for repeatable integration tests; it is labelled fixture evidence, never LTspice or physical evidence.
- `.log` and CSV measurement parsing; deterministic numeric verification.
- SQLite projects/tasks/artifacts/events/approvals and safe state transitions.
- Provider registry, structured mock provider, versioned role prompts, and explicit per-role tool-permission policy; external providers require host configuration and credentials.

See [AGENTS.md](AGENTS.md) for the complete v0.4 contract and [examples/rc_lowpass/spec.json](examples/rc_lowpass/spec.json) for a runnable fixture.

## Local API

The optional dependency-free API is intended for a trusted local host/UI. It exposes only project lifecycle routes: `POST /projects`, `GET /projects/{id}`, `POST /projects/{id}/run`, `POST /projects/{id}/approvals`, `POST /projects/{id}/resume`, `POST /projects/{id}/cancel`, `GET /projects/{id}/artifacts`, and `GET /projects/{id}/events`. It has no arbitrary command or tool-execution endpoint.

Visiting `http://127.0.0.1:8000/` opens a chat-style local dashboard. It can create projects, run/resume the workflow, record approvals, and view artifacts or events. The dashboard is a local host interface; it uses the same restricted lifecycle API described above. A browser may still request `/favicon.ico`, which has no route and can safely return `404`.

The dashboard has a **Model provider** panel for persisting the provider, model identifier, API key, optional base URL, temperature, token limit, and enabled state. API keys are write-only in the UI: entering a blank key preserves the existing key, and **Clear API key** removes it. `mock` is the only built-in adapter. Choosing names such as `openai`, `anthropic`, or `google` stores configuration securely but does not send requests externally until a corresponding trusted provider adapter is installed and registered.

Create a project from another terminal instead:

```bash
curl -X POST http://127.0.0.1:8000/projects \
  -H 'Content-Type: application/json' \
  --data @examples/rc_lowpass/spec.json
```

The response includes `project_id`; use it in subsequent requests, for example:

```bash
curl http://127.0.0.1:8000/projects/PROJECT_ID
curl -X POST http://127.0.0.1:8000/projects/PROJECT_ID/run
```
