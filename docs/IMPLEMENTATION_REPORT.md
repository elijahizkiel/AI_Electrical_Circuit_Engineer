# v0.4 Implementation and Architecture Report

## Purpose and scope

This document records how the initial v0.4 implementation addresses the project specification in `AGENTS.md`, and why its architecture uses a central orchestrator with narrow agent roles.

The implementation is deliberately limited to low-voltage educational and laboratory simulation workflows. It does not certify hardware safety, create arbitrary circuit topologies, generate universal Proteus projects, or treat a successful simulator process as proof that a design meets requirements.

## Architecture decision

The implemented application uses a controlled pipeline rather than a free-form agent swarm:

```text
CLI → SQLite project store → scope gate → specialized roles →
IR validation → design review → persisted approval → simulator adapter →
measurement analysis → deterministic verification → report
```

This was chosen for four reasons:

1. Safety boundaries are enforceable in code. The deterministic scope gate runs before any design work and rejects excluded requests such as mains, high-energy, safety-critical, or medical-device work.
2. The workflow is auditable. State changes, artifacts, approvals, and agent tasks are persisted in SQLite and linked to a project ID.
3. Simulators remain replaceable. The canonical Circuit IR is the only design representation consumed by simulator adapters; neither LTspice nor Proteus files become the source of truth.
4. Model reasoning cannot bypass evidence. Numeric pass/fail checks are performed by deterministic verification code. Missing measurements become `not_tested`, never `pass`.

## Implementation map

| Specification area | Implementation | Reasoning |
|---|---|---|
| State machine and orchestration | `src/circuit_agent/domain.py`, `orchestrator.py` | Explicit allowed transitions prevent agents or CLI commands from skipping approval and review stages. |
| Scope and safety gate | `src/circuit_agent/safety.py` | A deterministic and conservative precondition is more dependable than a language-model-only safety decision. |
| Persistent project state | `src/circuit_agent/storage.py` | SQLite supports local-first use, restart recovery, and a small deployment footprint. |
| Artifact revisioning | `ProjectStore.artifact()` | Each artifact receives an ID, revision, SHA-256 content hash, parent links, and an immutable on-disk envelope. |
| Specialized roles | `src/circuit_agent/agents.py` | Requirements, architecture, design, independent review, and optimization are separate stateless classes with distinct responsibilities. |
| Provider abstraction | `LLMProvider` protocol in `agents.py` | Agent logic can later use a configured provider without coupling the workflow to one vendor. The current supplied path is deterministic/mock. |
| Circuit contract and validation | `validation.py`, `schemas/circuit_ir.schema.json` | A strict canonical IR blocks unsupported models, unknown nodes, invalid pins, missing ground, malformed bounds, and unrecognized top-level IR fields. |
| Tool boundary | `tools.py` | Netlist generation and measurement analysis are deterministic functions rather than LLM-issued shell operations. |
| LTspice support | `simulators.py` | The adapter prepares a `.cir` and a deliberately limited `.asc`, and only runs LTspice when an executable is configured. |
| Proteus support | `ProteusHandoffAdapter` | It creates an IR/netlist/manifest handoff only. Native automation is represented as a configured, trusted bridge capability, not guessed project-file generation. |
| Measurements and verification | `tools.py`, `validation.verify()` | Source-linked CSV/log measurements feed explicit comparison operators. This prevents a successful process exit from being mistaken for a verified design. |
| Human review | `approvals` table and `resume()` | Simulator execution cannot proceed until an approval for the persisted design revision exists. |
| Reporting | `orchestrator._report()` | Produces both a machine-readable report artifact and `report.md`, clearly retaining human-review and evidence limitations. |
| CLI | `src/circuit_agent/main.py` | The CLI is the first supported interface as requested: validate, create, run, status, approve, resume, cancel, and export. |

## Workflow behavior

The workflow begins in `CREATED`. It performs the scope gate, requirements analysis, architecture selection, IR creation, and an independent review. A review finding causes `DESIGN_REVISION`; an approved review leads to `AWAITING_SIMULATION_APPROVAL`.

When the user approves the exact design revision, `resume` either runs a configured adapter or, in artifact-only mode, produces a report marked `COMPLETED_WITH_WARNINGS`. The warning state is intentional: no simulator evidence means requirements cannot be reported as passing.

For configured LTspice execution, the adapter records the process result and a supported text log can be parsed for measurements. The verification engine then evaluates each requirement using its declared operator. Proteus is currently a reproducible handoff path; it makes no claim that a native project has been generated or simulated unless a tested configured bridge supplies evidence.

## Why the canonical Circuit IR is central

The `circuit_ir` is simulator-independent and represents nodes, supported component models, parameters, analyses, measurement definitions, and source requirement IDs. This prevents accidental coupling between simulator file formats and engineering intent.

The first supported component catalog is intentionally small:

- `resistor` / `ideal_resistor`
- `capacitor` / `ideal_capacitor`
- `voltage_source` / `ideal_voltage_source`

Restricting the catalog is a safety and correctness decision. New components require validated pin definitions, model identifiers, netlist rendering, schema support, and tests before they can be admitted.

## How the archived v0.3 baseline informed the design

The `builds/ai-electrical-circuit-agent-v0.3.zip` material was used as the compatibility and capability baseline. Its safety guidance, constrained SPICE set, LTspice batch approach, Proteus handoff limitation, CSV/log waveform model, and bounded-optimization intent informed the v0.4 design.

The v0.4 code retains compatibility wrappers in `scripts/` for validation and constrained generation while moving new behavior into the installable `src/circuit_agent/` package.

## Verification performed

The implementation was checked with:

1. Python compilation of all source and compatibility scripts.
2. Validation of `examples/rc_lowpass/spec.json`.
3. An end-to-end artifact-only workflow: create → run → persisted design approval → resume → report generation.
4. Safety and verification checks confirming that a 230 VAC request is rejected and a missing measurement is `not_tested`.

The environment did not have `pytest` installed, so the included tests in `tests/` were not executed through pytest during implementation. They are configured for normal execution after installing the development dependency:

```bash
pip install -e .[dev]
pytest -q
```

## Current limitations and recommended next work

The delivered foundation implements the core vertical slice, but several specification items remain intentionally bounded:

- The default agent path is deterministic/mock; provider registry, prompt files, redaction, latency tracking, and structured-output repair are extension points rather than complete provider integrations.
- The initial architect/design role supports a provided IR and an RC-style educational example; it is not a general topology synthesizer.
- LTspice ASC output is limited and must be opened and checked in LTspice.
- Binary `.raw` waveform parsing is not implemented.
- The optimization role creates a bounded proposal but is not yet wired into the full approval/simulate/revision iteration loop.
- Cancellation, task timeouts/retries, unit conversion, FastAPI endpoints, and detailed simulator-run database records are not yet fully exercised by the first vertical slice.

These limits are exposed rather than approximated, consistent with the specification’s instruction not to claim unsupported capabilities. The recommended next increment is to complete the fake-simulator integration path, wire measurements and verification through a known fixture, then add a real LLM provider behind the existing protocol.
