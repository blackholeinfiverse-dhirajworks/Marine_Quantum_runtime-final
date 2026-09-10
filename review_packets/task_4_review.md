# Task 4 Review — BHIV Core Interface Preparation
**Author:** Dhiraj Chavan | Marine Intelligence System
**Date:** April 2026

---

## 1. ENTRY POINT

**File:** `run_signal.py` (repo root)

```bash
python run_signal.py
```

No arguments. No external dependencies. No file I/O. Fully self-contained.

Internally:
1. Constructs fixed sample input (hardcoded, as permitted)
2. Calls `generate_state_event()` once — Phase 4
3. Runs 4 failure/edge-case inputs — Phase 5
4. Runs same input 5 times, proves identical output — Phase 6

---

## 2. CORE FLOW

**3 files only.**

```
src/signal_generator.py
    → generate_state_event(input_payload) -> dict
    → validates input, calls mapping, builds event, validates output, returns

src/mapping_logic.py
    → resolve_transition(payload, seq) -> dict
    → pure function: applies priority-ordered transition table
    → returns (prev, next, cause, seq) + sigma

src/validator.py
    → validate_input(payload) -> dict
    → validate_output(event) -> None
    → raises ValidationError loudly on any problem
```

**Internal sequence:**

```
input_payload
    ↓
validate_input()        ← fails loudly if anything wrong. No computation if invalid.
    ↓
resolve_transition()    ← deterministic rule table. Pure function. No side effects.
    ↓
timestamp              ← anchor(2026-01-01T00:00:00Z) + (iterations × 60s)
    ↓
event assembly         ← engine_event_version 2.0
    ↓
validate_output()      ← confirms shape before returning
    ↓
return event
```

**Transition table (priority order — first match wins):**

| Condition | State | Cause |
|---|---|---|
| `energy_delta > 0.01` | DIVERGED | energy spike |
| `iterations > 500` | DIVERGED | runaway iteration count |
| `confidence < 0.70` | SUSPENDED | below confidence floor |
| `variance > 0.01` | SUSPENDED | high variance ceiling |
| all three: `confidence >= 0.85`, `variance <= 0.005`, `energy_delta <= 0.005` | CONVERGED | all criteria met |
| fallback | SUSPENDED | marginal — not fully met |

**sigma:** `sqrt(variance)` — always.

**prev:** `INITIALISING` if `iterations == 0`, else `ACTIVE`.

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
validate_input():
  node_id      = "qnode_01"  ✅ non-empty string
  energy_delta = 0.0001      ✅ float >= 0.0
  iterations   = 120         ✅ int >= 0
  confidence   = 0.92        ✅ float in [0.0, 1.0]
  variance     = 0.002       ✅ float >= 0.0

resolve_transition():
  Rule 1: 0.0001 <= 0.01     → not DIVERGED
  Rule 2: 120 <= 500         → not DIVERGED
  Rule 3: 0.92 >= 0.70       → not SUSPENDED
  Rule 4: 0.002 <= 0.01      → not SUSPENDED
  Rule 5: 0.92>=0.85 ✓  0.002<=0.005 ✓  0.0001<=0.005 ✓  → CONVERGED
  sigma = sqrt(0.002) = 0.04472136

timestamp:
  anchor = 2026-01-01T00:00:00Z
  offset = 120 × 60s = 7200s
  ts     = 2026-01-01T02:00:00Z
```

**Output:**
```json
{
  "engine_event_version": "2.0",
  "node_ref": "qnode_01",
  "transition": {
    "prev": "ACTIVE",
    "next": "CONVERGED",
    "cause": "confidence=0.92>=0.85, variance=0.002<=0.005, energy_delta=0.0001<=0.005",
    "seq": 1,
    "ts": "2026-01-01T02:00:00Z"
  },
  "uncertainty_envelope": {
    "confidence": 0.92,
    "sigma": 0.04472136
  }
}
```

---

## 4. WHAT WAS BUILT

**Callable Interface**
- `generate_state_event(input_payload: dict) -> dict` in `src/signal_generator.py`
- Single function. No constructor. No instance required.
- BHIV Core calls this directly.

**Deterministic Mapping**
- Priority-ordered rule table in `src/mapping_logic.resolve_transition()`
- Pure function — takes a dict, returns a dict
- No side effects. No randomness. No I/O.
- Same input always triggers same rule, same output.

**Schema Enforcement**
- `validate_input()` — type, range, presence. Fails with exact error messages.
- `validate_output()` — checks all required keys and that `seq` is `int`.
- No silent failures anywhere in the system.

**Execution Script**
- `run_signal.py` — Phase 4 (single run), Phase 5 (4 failure cases), Phase 6 (5-run determinism proof)
- Exit code 0 on PASS, 1 on FAIL.

---

## 5. FAILURE CASES

**Case 1 — Missing required field**
```
Input:  { "node_id": "qnode_04", "iterations": 50, "confidence": 0.90, "variance": 0.002 }
Result: ValidationError: Input validation failed (1 error(s)):
          • Missing required field(s): ['energy_delta']
```

**Case 2 — Low confidence → SUSPENDED**
```
Input:  { ..., "confidence": 0.55, ... }
Result: transition=SUSPENDED
        cause=confidence=0.55 below suspend floor 0.7
```

**Case 3 — High energy_delta → DIVERGED**
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

**Console output — confirmed live run:**

```
============================================================
  Quantum Signal Generator
  Marine Intelligence System | BHIV Core Interface
============================================================

------------------------------------------------------------
  PHASE 4 -- Single Execution
------------------------------------------------------------
Input:
{ "node_id": "qnode_01", "energy_delta": 0.0001, "iterations": 120,
  "confidence": 0.92, "variance": 0.002 }

Output:
{ "engine_event_version": "2.0", "node_ref": "qnode_01",
  "transition": { "prev": "ACTIVE", "next": "CONVERGED",
    "cause": "confidence=0.92>=0.85, variance=0.002<=0.005, energy_delta=0.0001<=0.005",
    "seq": 1, "ts": "2026-01-01T02:00:00Z" },
  "uncertainty_envelope": { "confidence": 0.92, "sigma": 0.04472136 } }

------------------------------------------------------------
  PHASE 5 -- Failure Cases
------------------------------------------------------------
  >>  Low confidence -> SUSPENDED
      -> transition: SUSPENDED
      -> cause:      confidence=0.55 below suspend floor 0.7

  >>  High energy_delta -> DIVERGED
      -> transition: DIVERGED
      -> cause:      energy_delta=0.05 exceeds diverge threshold 0.01

  >>  Missing field -> ValidationError
      -> ValidationError (expected): Input validation failed (1 error(s)):
         • Missing required field(s): ['energy_delta']

  >>  confidence out of range -> ValidationError
      -> ValidationError (expected): Input validation failed (1 error(s)):
         • Field 'confidence' = 1.5: must be a float in [0.0, 1.0].

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

  EXECUTION COMPLETE  |  Determinism: PASS ✅
```

**Compliance checklist:**

| Requirement | Status |
|---|---|
| Single callable entry point `generate_state_event()` | ✅ |
| No file I/O | ✅ |
| No global mutable state | ✅ |
| No randomness | ✅ |
| Output schema `engine_event_version 2.0` | ✅ |
| `sigma = sqrt(variance)` | ✅ |
| `seq` is integer | ✅ |
| `ts` is valid ISO 8601 | ✅ |
| Same input → same output (5-run proof) | ✅ |
| Fails loudly on invalid input | ✅ |
| Max 3 core files | ✅ |
| `run_signal.py` executes with `python run_signal.py` | ✅ |
