# Task 7 Review — Signal Purification + Core-Ready Contract
**Author:** Dhiraj Chavan | Marine Intelligence System
**Date:** April 2026

---

## 1. ENTRY POINT

**External invocation (how BHIV Core calls this):**
```bash
python invoke_signal.py
```

**Full test harness:**
```bash
python run_signal.py
```

No arguments. No external dependencies. Python 3.8+.

---

## 2. CORE FLOW

**3 files only.**

```
src/signal_generator.py
    → generate_signal(input_payload: dict) -> dict
    → pure signal function: validate → map → build event → validate → return
    → NO execution decisions, NO orchestration, NO engine calls

src/mapping_logic.py
    → resolve_transition(payload, seq) -> dict
    → pure deterministic transition table
    → returns (prev, next, cause, sequence_id) + sigma

src/validator.py
    → validate_input(payload) -> dict
    → validate_output(event) -> None
    → validate_contract(event) -> dict   ← NEW: externally callable
    → raises ValidationError loudly on any problem
```

**Signal flow — generate_signal():**

```
input_payload
    ↓
validate_input()          ← fails loudly. No computation if invalid.
    ↓
resolve_transition()      ← pure deterministic rule table
    ↓
_make_trace_id()          ← deterministic: node_id + iterations + seq (no randomness)
    ↓
timestamp                 ← anchor(2026-01-01T00:00:00Z) + (iterations × 60s)
    ↓
event assembly            ← engine_event_version 2.0 — Core-ready contract
    ↓
validate_output()         ← confirms contract shape before returning
    ↓
return event              ← passable to BHIV Core as-is, no transformation needed
```

---

## 3. LIVE EXECUTION

**Input:**
```json
{
  "node_id": "qnode_01",
  "energy_delta": 0.0001,
  "iterations": 120,
  "confidence": 0.92,
  "variance": 0.002
}
```

**Output:**
```json
{
  "engine_event_version": "2.0",
  "trace_id": "qnode_01-iter120-seq1",
  "node_id": "qnode_01",
  "node_ref": "qnode_01",
  "transition": {
    "prev": "ACTIVE",
    "next": "CONVERGED",
    "cause": "confidence=0.92>=0.85, variance=0.002<=0.005, energy_delta=0.0001<=0.005",
    "sequence_id": 1,
    "ts": "2026-01-01T02:00:00Z"
  },
  "uncertainty_envelope": {
    "confidence": 0.92,
    "sigma": 0.04472136
  }
}
```

**Contract validation:**
```
validate_contract(event) → {"status": "PASS"}
```

---

## 4. WHAT CHANGED

### REMOVED

| Item | Reason |
|---|---|
| `process_event_batch()` and all batch control logic | Orchestration — belongs to Core / Invocation Layer, not here |
| Sorting by `(node_id, seq)` | Cross-node ordering is Core's responsibility; local sorting assumes independence |
| `final_hash` / parallel hash chain | Created dual sources of truth against Kanishk's canonical chain |
| Execution policies: `APPLIED / SKIPPED / LOGGED` | Signal layer must not know execution semantics |
| Any call to execution engine | This system only emits events — it does not call consumers |
| `seq` field name in transition | Renamed to `sequence_id` for contract clarity |
| `run_*.py` dependency in core logic | `generate_signal()` works with zero dependency on runner scripts |

### ADDED

| Item | Purpose |
|---|---|
| `generate_signal()` | Clean public API — replaces `generate_state_event()` (alias kept for backward compat) |
| `invoke_signal.py` | External invocation demo — shows how BHIV Core calls the system |
| `trace_id` field | Mandatory contract field — deterministic, derived from input fields |
| `node_id` at top level | Mandatory contract field — directly readable by Core without digging into transition |
| `sequence_id` in transition | Renamed from `seq` — matches TANTRA contract naming |
| `validate_contract(event) -> dict` | Externally callable contract check — returns pass/fail dict, never raises |

---

## 5. FAILURE CASES

**Case 1 — Missing required field**
```
Input:  { "node_id": "qnode_04", "iterations": 50, "confidence": 0.90, "variance": 0.002 }
Result: ValidationError: Input validation failed (1 error(s)):
          • Missing required field(s): ['energy_delta']
```

**Case 2 — Low confidence → SUSPENDED (valid signal, not an error)**
```
Input:  { ..., "confidence": 0.55, ... }
Result: transition=SUSPENDED
        cause=confidence=0.55 below suspend floor 0.7
```

**Case 3 — High energy_delta → DIVERGED (valid signal, not an error)**
```
Input:  { ..., "energy_delta": 0.05, ... }
Result: transition=DIVERGED
        cause=energy_delta=0.05 exceeds diverge threshold 0.01
```

**Case 4 — confidence out of valid range**
```
Input:  { ..., "confidence": 1.5, ... }
Result: ValidationError: Input validation failed (1 error(s)):
          • Field 'confidence' = 1.5: must be a float in [0.0, 1.0].
```

---

## 6. PROOF

### Determinism — 5 runs, same input

```
Run 1: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z
Run 2: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z
Run 3: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z
Run 4: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z
Run 5: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z

[PASS] All 5 outputs IDENTICAL — determinism CONFIRMED.
```

### Contract Validation

```
validate_contract(event) → {"status": "PASS"}
```

Fields confirmed present in every output:
- `engine_event_version` ✅
- `trace_id` ✅
- `node_id` ✅
- `node_ref` ✅
- `transition.prev` ✅
- `transition.next` ✅
- `transition.cause` ✅
- `transition.sequence_id` (int) ✅
- `transition.ts` (ISO 8601) ✅
- `uncertainty_envelope.confidence` ✅
- `uncertainty_envelope.sigma` ✅

### Backward Compatibility

`run_signal.py` still exits 0. `generate_state_event()` alias preserved.

---

## 7. SYSTEM BOUNDARY — CONFIRMED

| Layer | Owner | Responsibility |
|---|---|---|
| **Signal Generator** | Dhiraj | validate input → determine state → emit event |
| **BHIV Core** | Backend/Core | receive event, route to execution engine |
| **Execution Engine** | Kanishk | consume events, mutate state |
| **Enforcement Engine** | Raj Prajapati | validate execution permissions |

This system does **not** know:
- Whether an event was APPLIED, SKIPPED, or LOGGED
- What Kanishk's engine does with the event
- How events are ordered across nodes
- What the global hash chain contains

---

## 8. COMPLIANCE CHECKLIST

| Requirement | Status |
|---|---|
| `generate_signal(input_payload: dict) -> dict` callable | ✅ |
| Works independently — no run_*.py dependency | ✅ |
| `invoke_signal.py` demonstrates external usage | ✅ |
| No execution decisions (APPLIED / SKIPPED / LOGGED) | ✅ |
| No call to execution engine | ✅ |
| No `process_event_batch()` | ✅ |
| No sorting/ordering assumptions | ✅ |
| No parallel hash chain | ✅ |
| `trace_id` present — deterministic | ✅ |
| `node_id` at top level | ✅ |
| `sequence_id` in transition | ✅ |
| `validate_contract(event) -> dict` implemented | ✅ |
| Output Core-passable as-is — no downstream rename | ✅ |
| Same input → same output (5-run proof) | ✅ |
| Invalid input rejected with clear error | ✅ |
| Max 3 core source files | ✅ |
| No file I/O | ✅ |
| No global mutable state | ✅ |
| No randomness | ✅ |
