# docs/architecture.md
# Marine Intelligence Quantum Runtime — Architecture

**Author:** Dhiraj Chavan | Marine Intelligence System
**Date:** May 2026

---

## What Exists

One canonical repository consolidating all prior build history (Tasks 1–9) into a deterministic, runtime-callable, quantum-hybrid-ready foundation.

### Layer Map

```
marine_quantum_runtime/
│
├── src/invoke_runtime.py          ← Single gateway: invoke_runtime(module, payload)
│
├── src/signal/                    ← Tasks 1–4: Quantum signal generator
│   ├── signal_generator.py        ← generate_state_event(), run()
│   ├── mapping_logic.py           ← Priority-ordered transition table
│   └── validator.py               ← Input/output schema enforcement
│
├── src/quantum/                   ← Tasks 2, 8: Quantum pipeline
│   ├── descriptors.py             ← QAppDescriptor + marine_corrosion_qapp registry
│   ├── schema.py                  ← Corrosion input/output validation
│   ├── algorithm.py               ← HEA circuit design (6-qubit)
│   └── execution.py               ← Pipeline execution + run()
│
├── src/runtime/                   ← Task 9: Distributed propagation
│   ├── envelope.py                ← QAppExecutionEnvelope (frozen, SHA-256 IDs)
│   ├── nodes.py                   ← DistributedNode + Node_A/B/C singletons
│   ├── propagation.py             ← Fan-out engine + append-only log
│   ├── replay.py                  ← Deterministic replay + shuffle convergence
│   ├── observability.py           ← Console dashboard rendering
│   └── distributed_qapp_runner.py ← Runtime-callable run()
│
├── src/monitoring/                ← Monitoring layer
│   ├── operational_drift_monitor.py ← Drift detection + run()
│   ├── metrics.py                 ← RuntimeMetrics + MetricsCollector
│   └── persistence.py             ← Append-only in-memory event log
│
└── src/contracts/                 ← Contract governance layer
    ├── qapp_contract.py           ← MARINE-INT-002 v1.0.0 enforcement
    ├── schema_contract.py         ← Schema registry + validation
    └── versioning.py              ← ContractVersion + compatibility check
```

---

## What Is Real

| Component | Status | Evidence |
|---|---|---|
| Signal generator (Tasks 1–4) | ✅ Implemented | `run/run_signal.py` — live execution |
| Transition table (priority rules) | ✅ Implemented | `src/signal/mapping_logic.py` |
| Schema validation (input + output) | ✅ Implemented | `src/signal/validator.py` |
| Quantum circuit (HEA, 6-qubit) | ✅ Designed | `src/quantum/algorithm.py` — needs qiskit for live circuit |
| Quantum execution (corrosion QApp) | ✅ Stdlib stub | `src/quantum/execution.py` — deterministic classical simulation |
| QApp descriptor registry | ✅ Implemented | `src/quantum/descriptors.py` — `marine_corrosion_qapp` registered |
| Distributed propagation (3-node) | ✅ Implemented | `run/run_distributed_qapp.py` — live execution |
| Append-only propagation log | ✅ Implemented | `src/runtime/propagation.py` |
| Causal-sort replay | ✅ Implemented | `src/runtime/replay.py` |
| Observability dashboard | ✅ Implemented | `src/runtime/observability.py` |
| Operational drift monitor | ✅ Implemented | `src/monitoring/operational_drift_monitor.py` |
| invoke_runtime gateway | ✅ Implemented | `src/invoke_runtime.py` |
| Contract enforcement | ✅ Implemented | `src/contracts/qapp_contract.py` |

---

## What Is Simulated

| Component | Simulation | What Would Replace It |
|---|---|---|
| VQE pipeline | Design documented in `review_packets/task_2_review.md` | PySCF + Qiskit VQE on real hardware |
| Quantum circuit execution | `src/quantum/algorithm.py` classical stub | `qiskit-aer` AerSimulator with `seed_simulator` |
| Physical hull state (corrosion, coating) | Described in Task 1–5 review packets | Kanishk's `physical_engine/` multi-zone executor |
| Network transport (QApp propagation) | In-process Python lists | Real distributed queue (e.g. Kafka) |
| Distributed consensus | Single-process hash comparison | Cross-node Byzantine consensus protocol |
| Timestamp (production) | `seq × 60s` anchor — deterministic | Wall-clock UTC with monotonic ordering |

---

## Boundaries

**Hull surface only.** No propulsion, cargo, routing, or structural fatigue.

**Propagation simulation only.** No networking stacks, async queues, cloud infrastructure.

**Classical stub for quantum circuit.** Full HEA circuit requires `qiskit` + `qiskit-aer`.

**Physical engine excluded.** Kanishk's `physical_engine/` modules are referenced in Task 5–6 review packets but not bundled here to maintain repo focus.

---

## Known Limitations

1. **Synthetic timestamp.** `ts` = `2026-01-01T00:00:00Z + (iterations × 60s)`. Not wall-clock. Downstream consumers must not treat `ts` as a real event time.
2. **`seq` monotonicity is caller-managed.** No enforcement across calls.
3. **VQE pipeline is design-only.** `src/quantum/execution.py` uses a deterministic classical stub.
4. **`iterations=0` + CONVERGED.** Semantically inconsistent in real physics — `prev="INITIALISING"` + `next="CONVERGED"` is not physically valid on the first iteration.
5. **Single-process propagation.** `Node_A/B/C` live in the same Python process. True partition tolerance is not exercised.

---

## Strategic Direction

```
Tasks 1–4   Signal generator + BHIV Core interface
Tasks 5–7   Execution integration + contract governance
Task 8      Quantum pipeline (HEA circuit + corrosion QApp)
Task 9      Distributed QApp propagation + replay
Current     Canonical convergence + invoke_runtime surface

Next steps:
  → QDApp formation (multi-QApp orchestration)
  → Governed quantum middleware
  → Hybrid quantum-classical runtime systems
  → Sovereign computational infrastructure (TANTRA direction)
```

---

*Dhiraj Chavan · Marine Intelligence System · May 2026*
