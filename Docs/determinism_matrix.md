# Determinism Matrix — Marine Intelligence System
**Author:** Dhiraj Chavan | BHIV Core / TANTRA Ecosystem  
**Version:** 1.0.0  
**Date:** June 2026

---

## Overview

"Determinism" is not one thing. This system distinguishes six precise determinism categories. Collapsing them into a single claim is a semantic error that causes integration failures.

---

## Category 1: Seed Determinism

**Definition:** Given the same seed value, the same pseudo-random sequence is produced. Applies to seeded simulations and seeded hash-based ID generation.

**Scope:** Quantum participant VQE stub (`_run_quantum_participant`, `seed=42`). SHA-256 ID generation throughout the contract layer.

**Proof Method:** Run with `seed=42` three times. Compare k_base and all derived values. Must be bit-identical.

**Current Implementation State:** ACTIVE — seeded stub in `invoke_runtime.py` is seed-deterministic. Real AerSimulator calls with `seed_simulator` parameter are also seed-deterministic in simulation mode.

**Known Unknowns:** Real quantum hardware (QPU) is NOT seed-deterministic. Shot noise cannot be seeded away. This is documented in `QAppDescriptor.known_limitations`.

---

## Category 2: Simulation Determinism

**Definition:** Given the same initial quantum state vector and same circuit, the simulation produces the same statevector output. This is the determinism class of the `RECONSTRUCTABLE` traces.

**Scope:** `quantum_vqe_participant` in `invoke_runtime.py`. AerSimulator with `StatevectorSampler` in Task 5 VQE pipeline.

**Proof Method:** Two independent simulation runs with identical state vector input and same seed. Compare E0 Hartree values — must agree to 6 decimal places.

**Current Implementation State:** ACTIVE for stub. In full Qiskit pipeline (Task 5): `seed_simulator` parameter ensures simulation determinism.

**Known Unknowns:** COBYLA optimiser convergence path may vary slightly under numerical precision differences across Python versions or OS platforms. This is a known limitation documented in the VQE pipeline.

---

## Category 3: Runtime Determinism

**Definition:** Given the same `RuntimeRequest` payload (same `module_name`, `seq`, `payload`), the same `RuntimeResponse` is produced. This is the determinism class of `REPLAYABLE` traces.

**Scope:** Classical signal participant (`_run_classical_participant`). All `generate_state_event()` calls in the signal layer. All contract ID generation (SHA-256).

**Proof Method:** 5-run proof pattern (inherited from Tasks 3–9). Same input → same `transition`, `sigma`, `ts`, `cause`. Content fingerprint must be bit-identical.

**Current Implementation State:** ACTIVE and proven. See Phase 4 console output:
```
Run 1: transition='CONVERGED'  sigma=0.04472136  ts=2026-01-01T02:00:00Z
       content_hash=fd4f97100a47210f19abb52c...
Run 2: transition='CONVERGED'  sigma=0.04472136  ts=2026-01-01T02:00:00Z
       content_hash=fd4f97100a47210f19abb52c...
Run 3: transition='CONVERGED'  sigma=0.04472136  ts=2026-01-01T02:00:00Z
       content_hash=fd4f97100a47210f19abb52c...
[PASS] All 3 classical outputs IDENTICAL
```

**Known Unknowns:** `request_id` includes `seq` — different seq values produce different `request_id` values by design. This is not a determinism violation: it is correct isolation of invocation identity from content determinism.

---

## Category 4: Contract Determinism

**Definition:** Given the same constructor inputs, a contract object always produces the same ID fields (`request_id`, `response_id`, `descriptor_id`, `trace_id`, `chain_hash`).

**Scope:** All classes in `runtime_contracts.py` and `descriptors.py`. All SHA-256 ID generation.

**Proof Method:** Construct identical `RuntimeRequest` twice. Compare `request_id` — must be identical. Same for `ModuleDescriptorContract.descriptor_id`.

**Current Implementation State:** ACTIVE. All IDs are SHA-256 of deterministic inputs. No randomness anywhere in contract construction.

**Known Unknowns:** None at this time. SHA-256 is deterministic by definition.

---

## Category 5: Observability Determinism

**Definition:** Given the same execution, log output, trace records, and lineage chain_hash are identical.

**Scope:** `ModuleExecutionTrace` (input_hash, output_hash, trace_id). `RuntimeLineageRecord` (chain_hash). All `[HALT]` formatted failure messages.

**Proof Method:** Run the same invocation twice. Compare `chain_hash` from `lineage_record.seal()`. If the invocation is runtime-deterministic (REPLAYABLE classical), chain_hash must be identical.

**Current Implementation State:** ACTIVE for classical leg. chain_hash for the hybrid invocation varies between runs because quantum `output_hash` is seed-deterministic but request-ID-sensitive.

**Known Unknowns:** Log timestamps use deterministic anchored timestamps — no wall-clock. Lineage chain_hash changes when seq changes (by design). See Category 3 note above.

---

## Category 6: Distributed Determinism

**Definition:** Given the same `RuntimeRequest` dispatched to multiple nodes, each node produces an output that is parity-equivalent (same state transition, same cause category) even if raw hashes differ due to node-ID seeding.

**Scope:** Cross-node comparison in distributed QApp propagation (Task 8). Node_B vs Node_C hash divergence is expected and documented.

**Proof Method:** Compare invocation-set parity (same set of `next` states produced), not raw output_hash equality. See Task 8 divergence-detection fix.

**Current Implementation State:** DOCUMENTED PATTERN — the single-node hybrid runtime in Task 10 does not exercise distributed determinism. Cross-node scenarios remain in `src/runtime/` (Tasks 7–9).

**Known Unknowns:** Distributed determinism under network partition is not currently modelled. This is a known limitation declared in the handover documentation.

---

## Summary Table

| Category | Scope | Status | Proof |
|---|---|---|---|
| Seed | Quantum stub, SHA-256 IDs | ✅ Active | Same seed → same k_base |
| Simulation | VQE AerSimulator stub | ✅ Active (sim) | Same statevector → same E0 |
| Runtime | Classical signal participant | ✅ Proven | 3-run content fingerprint |
| Contract | All RuntimeRequest/Response IDs | ✅ Active | ID audit (SHA-256) |
| Observability | Trace hashes, chain_hash | ✅ Active (classical) | chain_hash comparison |
| Distributed | Cross-node parity | 📄 Documented | Invocation-set parity check |

---

## What Is NOT Deterministic

- Quantum hardware (QPU) sampling outputs — explicitly `NON_DETERMINISTIC`.
- COBYLA optimiser path under cross-platform float precision differences.
- Network-partitioned distributed execution (not yet modelled).

These are documented, not hidden. Undocumented non-determinism is a defect. Documented non-determinism is a known boundary.
