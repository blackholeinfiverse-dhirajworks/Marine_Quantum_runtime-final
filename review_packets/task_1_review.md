# Task 1 Review — Digital Twin Definition
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
src/signal_generator.py    ← calls validate_input → resolve_transition → builds event
src/mapping_logic.py       ← pure state decision: CONVERGED / DIVERGED / SUSPENDED
src/validator.py           ← checks input fields and output shape
```

**What Task 1 established:**

The digital twin mirrors four physical processes on a ship hull:

- **Corrosion** — seawater electrochemically converts iron to iron oxide. Rate controlled by O₂, salinity, temperature, and coating state.
- **Biofouling** — barnacles attach and grow. Intact antifouling paint suppresses 90% of growth. Heavy fouling costs 10–15% extra fuel.
- **Coating degradation** — mechanical erosion (flow), UV breakdown, and chemical decay. Coating is the master variable — everything else depends on it.
- **Performance loss** — rougher hull = higher drag = higher fuel cost, converted to an annual dollar figure.

State variables tracked per zone: `corrosion_depth`, `coating_thickness`, `barnacle_density`, `flow_velocity`, `roughness_index`, `risk_score`.

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

- Defined the four physical degradation processes the twin simulates
- Specified the full zone state variable set with units and usage
- Established scope boundary: hull surface only (no propulsion, cargo, routing)
- Defined the zone grid model: 50–200 rectangular zones, each updated independently
- Set up 4 update rules (Coating master switch → Corrosion → Drag → Flow feedback)

---

## 5. FAILURE CASES

| Input | Result |
|---|---|
| `confidence = 0.55` | SUSPENDED — below 0.70 floor |
| `energy_delta = 0.05` | DIVERGED — exceeds 0.01 threshold |
| Missing `energy_delta` field | ValidationError — caught before any logic runs |
| `confidence = 1.5` | ValidationError — out of range [0.0, 1.0] |

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
