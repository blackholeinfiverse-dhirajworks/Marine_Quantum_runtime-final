# Task 5 Review — Signal → Execution → Observable State
**Author:** Dhiraj Chavan | Marine Intelligence System
**Date:** April 2026

---

## 1. ENTRY POINT

**File:** `run_signal.py` (repo root)

```bash
python run_signal.py
```

No arguments. No external dependencies. No file I/O. Fully self-contained.

Internally runs:
1. Phase 4 — Single signal execution
2. Phase 5 — Failure handling (execution level)
3. Phase 6 — Determinism proof (5 identical runs)
4. Phase 7 — Observable state proof (before/after + hash chain)
5. Phase 8 — Traceability (trace_id end-to-end)

---

## 2. CORE FLOW

**5 src files. Fixed order.**

```
src/signal_generator.py      ← unchanged from Task 4 (Dhiraj)
src/mapping_logic.py         ← unchanged from Task 4 (Dhiraj)
src/validator.py             ← unchanged from Task 4 (Dhiraj)
src/execution_engine.py      ← NEW: wraps Kanishk's real engine
src/integration_runner.py    ← NEW: direct invocation bridge
```

**Kanishk's engine (integrated, not stubbed):**

```
physical_engine/ship_state_vector.py   ← ShipState, ShipStateVector
physical_engine/transition_engine.py   ← TransitionInput, DeterministicTransitionEngine
physical_engine/multi_zone_executor.py ← MultiZoneExecutor (4-zone hull model)
```

**Pipeline:**

```
input_payload
    ↓
integration_runner.run_integration(input, trace_id)
    ↓
signal_generator.generate_state_event()     ← Dhiraj: quantum signal
    ↓
execution_engine.execute_event(event)
    ↓
    _signal_to_transition_rates()            ← maps confidence/sigma → physical rates
    ↓
MultiZoneExecutor.execute_batch()           ← Kanishk's real engine
    ↓
ShipStateVector updated (corrosion, coating, barnacle, roughness, risk_score)
    ↓
{ trace_id, node_id, final_state, pre_hash, post_hash, zone_state }
```

**Execution policy:**

| Transition | Action   | Kanishk's Engine Called | State Updated |
|---|---|---|---|
| CONVERGED  | EXECUTED | ✅ Yes                  | ✅ Yes |
| SUSPENDED  | SKIPPED  | ❌ No                   | ❌ No  |
| DIVERGED   | LOGGED   | ❌ No                   | ❌ No  |
| Bad schema | REJECTED | ❌ No                   | ❌ No  |

**Signal → Physical Rate Mapping (deterministic):**

```
corrosion_rate           = 0.02 + (1 - confidence) × 0.05
coating_degradation_rate = 0.01 + sigma × 0.5
barnacle_growth_rate     = 0.10 + (1 - confidence) × 0.3
roughness_rate           = 0.002 + sigma × 0.05
dt                       = 1.0  (1 time unit per event)
```

Same event → same rates → same ShipState → same global hash. Always.

---

## 3. LIVE FLOW

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

**Transformation trace:**

```
generate_state_event() → transition=CONVERGED  sigma=0.04472136

_signal_to_transition_rates():
  corrosion_rate           = 0.02 + (1 - 0.92) × 0.05 = 0.024
  coating_degradation_rate = 0.01 + 0.04472136 × 0.5  = 0.03236068
  barnacle_growth_rate     = 0.10 + (1 - 0.92) × 0.3  = 0.124
  roughness_rate           = 0.002 + 0.04472136 × 0.05 = 0.00423607
  dt = 1.0

MultiZoneExecutor.execute_batch({"bow": TransitionInput(...)})
  pre_hash  = 26f283980dc23de7...
  post_hash = 39b2fb12c7ce279f...

Zone bow — before → after:
  corrosion_depth  : 0.10000000 → 0.12400000
  coating_thickness: 4.50000000 → 4.46763932
  risk_score       : 0.55055556 → 0.58500518
```

**Final output:**
```
trace_id    = "test-trace-001"
node_id     = "qnode_01"
final_state = "CONVERGED"
zone_state  = bow → corrosion=0.12400000  risk=0.58500518
pre_hash    = 26f283980dc23de71849abb501bae6e9...
post_hash   = 39b2fb12c7ce279f47fca278ee215441...
```

---

## 4. WHAT WAS BUILT

**`execution_engine.py`**
- Calls Kanishk's `MultiZoneExecutor.execute_batch()` — not a stub
- Maps CONVERGED signal → `TransitionInput` via deterministic rate formula
- Updates `ShipStateVector` (corrosion, coating, barnacle, roughness, risk_score)
- Logs `pre_hash` / `post_hash` from Kanishk's hash chain — proves state changed
- Policy: CONVERGED→EXECUTED, SUSPENDED→SKIPPED, DIVERGED→LOGGED, bad schema→REJECTED

**`integration_runner.py`**
- Direct bridge: `run_integration(input_payload, trace_id, target_zone)` → full result dict
- No file I/O. No async. No queue. Just direct function calls.
- trace_id carried through input → event → execution → output

---

## 5. FAILURE CASES

**Low confidence → SKIPPED (no engine call)**
```
[SKIPPED]   node=qnode_02  reason=low_confidence  trace=test-failure
action=SKIPPED  final_state=None
```

**High energy_delta → LOGGED (quarantined, no engine call)**
```
[DIVERGED]  node=qnode_03  logged but NOT applied  trace=test-failure
action=LOGGED  final_state=None
```

**Missing field → REJECTED (before signal generation)**
```
[REJECTED] trace=test-failure  reason=invalid_schema
action=REJECTED  final_state=None
```

**confidence out of range → REJECTED**
```
[REJECTED] trace=test-failure  reason=invalid_schema
action=REJECTED  final_state=None
```

---

## 6. PROOF

**Console output — confirmed live run:**

```
============================================================
  Quantum Signal Generator — Integrated with Kanishk's Engine
  Marine Intelligence System | BHIV Core Interface
============================================================

------------------------------------------------------------
  PHASE 4 -- Single Execution (Signal Generator)
------------------------------------------------------------
Input:
{ "node_id": "qnode_01", "energy_delta": 0.0001,
  "iterations": 120, "confidence": 0.92, "variance": 0.002 }

Signal Output:
{ "engine_event_version": "2.0", "node_ref": "qnode_01",
  "transition": { "prev": "ACTIVE", "next": "CONVERGED",
    "cause": "confidence=0.92>=0.85, variance=0.002<=0.005, energy_delta=0.0001<=0.005",
    "seq": 1, "ts": "2026-01-01T02:00:00Z" },
  "uncertainty_envelope": { "confidence": 0.92, "sigma": 0.04472136 } }

------------------------------------------------------------
  PHASE 5 -- Failure Handling (Execution Level)
------------------------------------------------------------
  >>  Low confidence -> SUSPENDED
[SKIPPED]   node=qnode_02  reason=low_confidence  trace=test-failure
      action=SKIPPED  final_state=None

  >>  High energy_delta -> DIVERGED
[DIVERGED]  node=qnode_03  logged but NOT applied  trace=test-failure
      action=LOGGED  final_state=None

  >>  Missing field -> REJECTED
[REJECTED] trace=test-failure  reason=invalid_schema
      action=REJECTED  final_state=None

  >>  confidence out of range -> REJECTED
[REJECTED] trace=test-failure  reason=invalid_schema
      action=REJECTED  final_state=None

------------------------------------------------------------
  PHASE 6 -- Determinism Proof (5 runs, same input)
------------------------------------------------------------
  Run 1: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z
  Run 2: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z
  Run 3: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z
  Run 4: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z
  Run 5: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z

  [PASS] All 5 outputs IDENTICAL -- determinism CONFIRMED.

------------------------------------------------------------
  PHASE 7 -- Observable State Proof (Kanishk's Engine)
------------------------------------------------------------

  Before execution:
    state[bow].corrosion_depth   = 0.1
    state[bow].coating_thickness = 4.5
    state[bow].risk_score        = 0.55055556
    global_hash = 26f283980dc23de71849abb501bae6e9...

[EXECUTION] node=qnode_01 transitioned to CONVERGED  zone=bow  batch=1  trace=test-trace-001
            risk_score: 0.55055556 → 0.58500518
            pre_hash=26f283980dc23de7...  post_hash=39b2fb12c7ce279f...

  After execution:
    state[bow].corrosion_depth   = 0.124
    state[bow].coating_thickness = 4.46763932
    state[bow].risk_score        = 0.58500518
    global_hash = 39b2fb12c7ce279f47fca278ee215441...

  Hash changed:  True
  State changed: True
  [PASS] Observable state change CONFIRMED in Kanishk's engine.

------------------------------------------------------------
  PHASE 8 -- Traceability (trace_id end-to-end)
------------------------------------------------------------
[EXECUTION] node=qnode_01 transitioned to CONVERGED  zone=bow  batch=1  trace=test-trace-001
            risk_score: 0.55055556 → 0.58500518

  trace_id   : test-trace-001
  node_id    : qnode_01
  final_state: CONVERGED
  zone_state : bow → corrosion=0.12400000  risk=0.58500518

  [PASS] trace_id + node_id + final_state all present and correct.
------------------------------------------------------------

  EXECUTION COMPLETE  |  Overall: PASS ✅
```

**Compliance checklist:**

| Requirement | Status |
|---|---|
| 1 signal → 1 execution → 1 observable state change | ✅ |
| No new architecture / no redesign | ✅ |
| No file I/O, no async, no queue | ✅ |
| Direct function call only | ✅ |
| Kanishk's REAL engine used (not stubbed) | ✅ |
| ShipState physically updated (corrosion, coating, risk) | ✅ |
| pre_hash ≠ post_hash (Kanishk's hash chain proves change) | ✅ |
| Invalid event → REJECTED (before engine call) | ✅ |
| Low confidence → SKIPPED (no engine call) | ✅ |
| DIVERGED → LOGGED, not applied | ✅ |
| trace_id carried input → event → execution → output | ✅ |
| Output includes trace_id, node_id, final_state | ✅ |
| Determinism: 5 runs identical | ✅ |
| `python run_signal.py` — zero arguments, zero dependencies | ✅ |
