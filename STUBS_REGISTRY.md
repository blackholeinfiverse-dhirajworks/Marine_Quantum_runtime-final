# STUBS_REGISTRY.md
# Honest Stub Declarations — Marine Intelligence System
# Every stub in the system is declared here.
# Undeclared stubs are defects, not features.
#
# Author: Dhiraj Chavan | Date: June 2026

Each stub entry states: what it is, what it replaces, who owns the real
implementation, what the runtime does while the stub is active, and what
the risk is if the stub is never replaced.

---

## STUB-001 — CanonicalReplayAuthority (REPLACED)

| Field | Value |
|---|---|
| Previous stub | `_CanonicalReplayAuthorityStub` in `capability_runtime.py` |
| Real implementation | `src/governance/replay_legitimacy.py :: CanonicalReplayAuthority` |
| Status | **REPLACED** — real implementation now wired by default |
| Current default | `CanonicalReplayAuthority(allow_re_execution=True)` for development |
| Production config | `CanonicalReplayAuthority(allow_re_execution=False)` — attach via `attach_replay_authority()` |
| Previous stub behavior | Returned PERMIT unconditionally. Did NOT track seen invocations. |
| Real behavior | PERMIT on first execution; DENY on repeat; REPLAY_VERIFIED/DIVERGED on explicit replay |
| Residual risk | `allow_re_execution=True` in development mode. Set False before production. |

---

## STUB-002 — EvidenceLedger (REPLACED)

| Field | Value |
|---|---|
| Previous stub | `_EvidenceLedgerStub` in `capability_runtime.py` |
| Real implementation | `src/runtime/persistent_history.py :: PersistentHistory` |
| Status | **REPLACED** — persistent JSONL log wired by default |
| Current behavior | Appends to `runtime_history.jsonl` in repo root. Survives restarts. |
| Production config | Call `attach_evidence_ledger(PersistentHistory(path=<prod-path>))` |
| Previous risk | Execution evidence lost on process restart. No audit trail across sessions. |
| Current risk | Log file grows indefinitely. No rotation implemented. |

---

## STUB-003 — Global Sequence Counter (REPLACED)

| Field | Value |
|---|---|
| Previous stub | `next_seq()` in `runtime_observability.py` — one counter shared across all capabilities |
| Real implementation | `src/runtime/sequence_registry.py :: SequenceRegistry` |
| Status | **REPLACED** — per-capability isolated counters in `capability_runtime.py` |
| Previous behavior | Two concurrent capability invocations shared the same seq namespace |
| Real behavior | Each capability has its own monotonic counter — `_SEQ_REGISTRY.next(capability_id)` |

---

## STUB-004 — Quantum Circuit (ACTIVE)

| Field | Value |
|---|---|
| Stub location | `src/quantum/execution.py :: run_corrosion_qapp()` |
| Real implementation | `src/quantum/algorithm.py :: build_corrosion_circuit()` + AerSimulator |
| Status | **STUB ACTIVE** |
| Stub behavior | Deterministic classical simulation using `random.Random(seed=42)` |
| Production behavior | 6-qubit HEA circuit executed on Qiskit AerSimulator |
| Activation | `pip install qiskit qiskit-aer pydantic` then swap executor in `execution.py` |
| Risk | Quantum outputs do not reflect real superposition or entanglement. Entropy calculation is approximate. |

---

## STUB-005 — Physical Hull Engine — Kanishk (EXCLUDED)

| Field | Value |
|---|---|
| Stub location | Referenced in Task 5–6 review packets. Not bundled. |
| Real implementation | Kanishk's `physical_engine/multi_zone_executor.py :: MultiZoneExecutor` |
| Status | **EXCLUDED** |
| Stub behavior | Hull state mutations (corrosion, coating, risk_score) are not executed. |
| Activation | Import `physical_engine`, wire `execution_engine.py` to `MultiZoneExecutor.execute_batch()` |
| Risk | Hull state is never updated. Corrosion/coating progression is not simulated. |

---

## STUB-006 — Distributed Network Transport (ACTIVE)

| Field | Value |
|---|---|
| Stub location | `src/runtime/nodes.py`, `src/runtime/propagation.py` |
| Real implementation | Real distributed message queue (Kafka, AMQP, or gRPC streams) |
| Owner | Jaffer Ali (Distributed Telemetry layer) |
| Status | **STUB ACTIVE** |
| Stub behavior | All propagation is in-process Python function calls. Node_A/B/C are objects in the same process. |
| Risk | No real partition tolerance. No real Byzantine failure handling. No network latency. |

---

## STUB-007 — Governance Pre-Approval Hook (NOT IMPLEMENTED)

| Field | Value |
|---|---|
| Stub location | `src/runtime/capability_runtime.py` — hook point exists but not wired |
| Real owner | TMS Strategic layer / Raj |
| Status | **NOT IMPLEMENTED** |
| Current behavior | No governance pre-approval check before invocation |
| Required behavior | Every invocation requires pre-approval from governance layer |
| Risk | Capabilities can be invoked without governance authorization |
| Next step | Define `GovernanceApprovalHook` interface; wire in `invoke_capability()` step 3.5 |

---

## STUB-008 — Enforcement Engine (NOT INTEGRATED)

| Field | Value |
|---|---|
| Stub location | Not yet present in this repo |
| Real owner | Raj Prajapati (Routing and Enforcement layer) |
| Status | **NOT INTEGRATED** |
| Current behavior | Authority matrix provides enforcement at check time only — no external enforcement agent |
| Required behavior | Raj's enforcement engine receives every invocation result and validates legitimacy |
| Risk | Execution legitimacy is locally asserted, not externally verified |

---

## Stub Summary

| Stub | Status |
|---|---|
| CanonicalReplayAuthority | ✅ REPLACED |
| EvidenceLedger | ✅ REPLACED |
| Global Sequence Counter | ✅ REPLACED |
| Quantum Circuit | ⚠️ STUB ACTIVE |
| Physical Hull Engine | ❌ EXCLUDED |
| Distributed Network Transport | ⚠️ STUB ACTIVE |
| Governance Pre-Approval Hook | ❌ NOT IMPLEMENTED |
| Enforcement Engine | ❌ NOT INTEGRATED |

3 stubs replaced. 2 active (acceptable for dev). 3 missing (must be addressed before production).
