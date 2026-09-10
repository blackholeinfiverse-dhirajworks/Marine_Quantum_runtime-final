# Handover Documentation — Marine Intelligence System
**Author:** Dhiraj Chavan | BHIV Core / TANTRA Ecosystem  
**Version:** Post-Task-10  
**Date:** June 2026

---

## Immediate Start

```bash
git clone <repo>
cd marine_quantum_runtime
python run_hybrid_runtime.py    # Hybrid runtime (Task 10) — expected: PASS, exit 0
python run_signal.py            # Signal generator (Tasks 1–4) — expected: PASS, exit 0
```

No pip install. No external dependencies. Python 3.8+ stdlib only (plus Qiskit for quantum pipeline if Task 5 is being exercised — see `requirements.txt`).

---

## What This System Is

A **quantum-enhanced digital twin runtime** for maritime hull management. The runtime tracks corrosion, biofouling, coating degradation, and performance loss across hull zones. The quantum layer computes corrosion rate constants from first principles (VQE). The classical layer maps quantum node states to CONVERGED / DIVERGED / SUSPENDED transitions. The contract layer governs every boundary crossing.

This is not a demo. It is an infrastructure-grade runtime with determinism proofs, SHA-256 audit trails, and explicit contract governance.

---

## Repository Structure

```
marine_quantum_runtime/
├── src/
│   ├── contracts/
│   │   ├── runtime_contracts.py    ← RuntimeRequest, RuntimeResponse,
│   │   │                              FailureContract, ModuleDescriptorContract
│   │   └── descriptors.py          ← QAppDescriptor, DescriptorRegistry,
│   │                                  3 pre-registered descriptors
│   ├── runtime/
│   │   ├── invoke_runtime.py       ← invoke_hybrid_runtime() — unified entry
│   │   └── provenance.py           ← ExecutionLineage, RuntimeLineageRecord,
│   │                                  ModuleExecutionTrace
│   ├── signal/
│   │   ├── signal_generator.py     ← generate_state_event()
│   │   ├── mapping_logic.py        ← resolve_transition() — pure function
│   │   └── validator.py            ← validate_input(), validate_output()
│   ├── quantum/                    ← VQE pipeline (Task 5)
│   └── monitoring/                 ← Drift monitor (Task 6)
├── run_hybrid_runtime.py           ← MAIN — Task 10
├── run_signal.py                   ← MAIN — Tasks 1–4
├── docs/
│   ├── runtime_contracts.md        ← What is guaranteed, not guaranteed, deterministic
│   ├── capability_attachment.md    ← Attachment modes, authority ceilings
│   ├── descriptor_governance.md    ← Lifecycle, registration rules
│   ├── provenance_model.md         ← Replayable vs reconstructable vs truth
│   ├── hybrid_participation.md     ← What makes a participant hybrid-compliant
│   └── determinism_matrix.md       ← 6 determinism categories, proof methods
├── review_packets_/
│   ├── task_1_review.md … task_4_review.md
│   └── task_next_review.md         ← Task 10 review packet
└── requirements.txt
```

---

## Team Map

| Person | Owns |
|---|---|
| **Dhiraj** | Signal generation, contract layer, hybrid participation, provenance, this repo |
| **Kanishk** | Physical hull execution engine, deterministic hybrid runtime semantics, `MultiZoneExecutor` |
| **Raj / Raj Prajapati** | Invocation routing, enforcement and execution governance |
| **Jaffer Ali** | Distributed telemetry propagation |
| **Ganesh** | Deterministic runtime coordination |
| **Vinayak (Testing)** | BHIV Universal Testing Protocol verification |

---

## Non-Negotiable Design Rules

1. **No `datetime.now()`** — timestamps are `anchor(2026-01-01T00:00:00Z) + (iterations × 60s)`.
2. **SHA-256 for all IDs** — request_id, response_id, descriptor_id, trace_id, chain_hash.
3. **Append-only lineage** — `RuntimeLineageRecord` and `ExecutionLineage` never mutate records.
4. **Loud failures** — `ContractViolation` and `FailureContract` always propagate. No silent recovery.
5. **Attachment ≠ ownership** — registering a descriptor does not grant governance authority.
6. **Determinism is categorical** — six categories. Never collapse to "it's deterministic."
7. **No file I/O, no global mutable state, no randomness** in core signal/contract logic.

---

## Integration Points for Kanishk

- Register `MultiZoneExecutor` as a `QAppDescriptor` with `capability_class="CLASSICAL"`, `authority_ceiling="RUNTIME_GOVERN"`.
- Wrap invocations in `RuntimeRequest`. Consume `RuntimeResponse`.
- Consume `RuntimeLineageRecord.chain_hash` for audit verification.
- One-line swap in `invoke_runtime.py` to replace the classical signal stub with the real executor.
- See `task_next_review.md` §8 for full integration notes.

---

## Testing Entry Point (Vinayak)

Run both entry points and confirm exit code 0:

```bash
python run_hybrid_runtime.py && echo "Task 10: PASS"
python run_signal.py         && echo "Tasks 1-4: PASS"
```

Expected output markers:
- `[PASS] All 3 classical outputs IDENTICAL — determinism CONFIRMED.`
- `EXECUTION COMPLETE | Determinism: PASS ✅`
- `Hybrid participation  : CONFIRMED (classical + quantum in shared contract)`
- `Lineage sealed        : <chain_hash>...`
