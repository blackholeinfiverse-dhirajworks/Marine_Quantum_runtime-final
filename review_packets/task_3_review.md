# Task 3 Review — Signal Generator Design
**Author:** Dhiraj Chavan | Marine Intelligence System

---

## 1. ENTRY POINT

```bash
python run_signal.py
```

---

## 2. CORE FLOW

**3 files. Fixed order.**

```
src/signal_generator.py    ← entry logic: validate → map → build event → validate output
src/mapping_logic.py       ← pure deterministic transition: CONVERGED / DIVERGED / SUSPENDED
src/validator.py           ← input schema enforcement + output structural check
```

**Sequence inside `generate_state_event()`:**

```
input_payload
    │
    ▼
validator.validate_input()          ← fails loudly if anything wrong
    │
    ▼
mapping_logic.resolve_transition()  ← deterministic state decision
    │
    ▼
timestamp construction              ← anchor + (iterations × 60s), not datetime.now()
    │
    ▼
event dict assembly                 ← engine_event_version 2.0 schema
    │
    ▼
validator.validate_output()         ← confirms shape before returning
    │
    ▼
return event
```

**Transition table (priority order):**

| Condition | Next State |
|---|---|
| `energy_delta > 0.01` | DIVERGED |
| `iterations > 500` | DIVERGED |
| `confidence < 0.70` | SUSPENDED |
| `variance > 0.01` | SUSPENDED |
| `confidence >= 0.85` AND `variance <= 0.005` AND `energy_delta <= 0.005` | CONVERGED |
| fallback | SUSPENDED |

**sigma:** `sqrt(variance)` — always.

**prev state:** `INITIALISING` if `iterations == 0`, else `ACTIVE`.

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

**Step-by-step trace:**

- `validate_input()`: all 5 fields present and in range ✅
- Rule 1: energy_delta=0.0001 ≤ 0.01 → not DIVERGED
- Rule 2: iterations=120 ≤ 500 → not DIVERGED
- Rule 3: confidence=0.92 ≥ 0.70 → not SUSPENDED
- Rule 4: variance=0.002 ≤ 0.01 → not SUSPENDED
- Rule 5: 0.92 ≥ 0.85 AND 0.002 ≤ 0.005 AND 0.0001 ≤ 0.005 → **CONVERGED** ✅
- sigma = sqrt(0.002) = 0.04472136
- ts = 2026-01-01T00:00:00Z + (120 × 60s) = **2026-01-01T02:00:00Z**

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

- `generate_state_event()` — single callable, no constructor, no instance required
- `resolve_transition()` — pure function, priority-ordered rule table, no side effects
- `validate_input()` — checks type, range, and presence for all 5 required fields
- `validate_output()` — confirms all keys present and `seq` is int before returning
- Deterministic timestamp: `anchor + (iterations × 60s)` — not wall clock
- Contract: no file I/O, no global mutable state, no randomness anywhere in the system

---

## 5. FAILURE CASES

**Missing field:**
```
Input: { "node_id": "qnode_04", "iterations": 50, "confidence": 0.90, "variance": 0.002 }
→ ValidationError: Input validation failed (1 error(s)):
  • Missing required field(s): ['energy_delta']
```

**Low confidence:**
```
Input: { ..., "confidence": 0.55, ... }
→ transition: SUSPENDED
→ cause: confidence=0.55 below suspend floor 0.7
```

**High energy_delta:**
```
Input: { ..., "energy_delta": 0.05, ... }
→ transition: DIVERGED
→ cause: energy_delta=0.05 exceeds diverge threshold 0.01
```

**Out-of-range confidence:**
```
Input: { ..., "confidence": 1.5, ... }
→ ValidationError: Field 'confidence' = 1.5: must be a float in [0.0, 1.0].
```

---

## 6. PROOF

```
Run 1: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z
Run 2: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z
Run 3: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z
Run 4: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z
Run 5: transition='CONVERGED'   sigma=0.04472136   ts=2026-01-01T02:00:00Z

[PASS] All 5 outputs IDENTICAL — determinism CONFIRMED.
```
