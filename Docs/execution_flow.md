# docs/execution_flow.md
# Signal → Quantum → Runtime → Monitoring — Execution Flow

---

## End-to-End Flow

```
External Caller (BHIV Core / TANTRA)
          │
          ▼
  invoke_runtime(module_name, payload)
  src/invoke_runtime.py
          │
    ┌─────┴──────────────────────────────┐
    │                                    │
    ▼                                    ▼
module = "signal"             module = "quantum_pipeline"
src/signal/                   src/quantum/
signal_generator.run()        execution.run()
    │                              │
    ▼                              ▼
generate_state_event()        run_corrosion_qapp()
    │                              │
    ├─ validate_input()            ├─ validate_corrosion_input()
    ├─ resolve_transition()        ├─ normalize_corrosion_input()
    ├─ build timestamp             ├─ simulate_circuit_classically()
    ├─ assemble event              ├─ compute degradation_probability
    └─ validate_output()          ├─ compute confidence_score
                                   ├─ validate_corrosion_output()
                                   └─ build deterministic_event
          │
    ┌─────┴──────────────────────────────┐
    │                                    │
    ▼                                    ▼
module = "distributed_qapp"   module = "operational_monitor"
src/runtime/                  src/monitoring/
distributed_qapp_runner.run() operational_drift_monitor.run()
    │                              │
    ▼                              ▼
QAppExecutionEnvelope.create() ingest(event)
    │                              │
propagate_qapp_event()        _check_drift()
    │                              │
    ├─ Node_A.receive()            ├─ confidence degradation
    ├─ Node_A → Node_B            ├─ variance spike
    ├─ Node_A → Node_C            ├─ energy spike
    └─ append _PROPAGATION_LOG    └─ state shift
          │
    replay_qapp_log()
          │
    consensus_hash
```

---

## Signal Layer Flow

```
input_payload (dict)
    ↓
validator.validate_input()     ← raises ValidationError if bad. No computation if invalid.
    ↓
mapping_logic.resolve_transition()
    ↓  priority-ordered rules (first match wins):
    │   energy_delta > 0.01       → DIVERGED
    │   iterations > 500          → DIVERGED
    │   confidence < 0.70         → SUSPENDED
    │   variance > 0.01           → SUSPENDED
    │   all three convergence criteria → CONVERGED
    │   fallback                  → SUSPENDED
    ↓
timestamp = anchor(2026-01-01T00:00:00Z) + (iterations × 60s)
sigma     = sqrt(variance)
    ↓
event assembly (engine_event_version 2.0)
    ↓
validator.validate_output()    ← confirms shape before returning
    ↓
return structured event dict
```

---

## Quantum Pipeline Flow

```
corrosion_payload (dict: 6 physical fields)
    ↓
validate_corrosion_input()     ← range-checks all 6 fields
    ↓
normalize_corrosion_input()    ← maps physical values → [0, π]
    ↓
simulate_circuit_classically() ← deterministic HEA simulation
    ↓  (Full execution: AerSimulator with seed_simulator=seed)
    ↓
Hamming-weighted degradation_probability
entropy-based confidence_score
linear anode current recommendation
    ↓
validate_corrosion_output()    ← 8 contract rules (R1–R8)
    ↓
risk threshold mapping → risk_level → action_required → signal
    ↓
return structured result dict
```

---

## Distributed QApp Flow

```
payloads: List[dict]
    ↓
QAppExecutionEnvelope.create() × N  ← SHA-256 IDs, deterministic timestamp
    ↓
propagate_qapp_event(envelope) × N
    │
    ├─ Node_A.receive(env)          ← updates execution_hash chain
    ├─ ORIGIN entry → _PROPAGATION_LOG
    │
    ├─ Node_A → Node_B.receive(env)
    ├─ PROPAGATE entry → _PROPAGATION_LOG
    │
    └─ Node_A → Node_C.receive(env)
       PROPAGATE entry → _PROPAGATION_LOG
    ↓
replay_qapp_log(log)
    ├─ causal sort by (sequence_id, step_order)
    ├─ rebuild node hash chains
    ├─ compute consensus_hash
    └─ verify coverage (A == B == C invocations)
    ↓
return { consensus_hash, consistent, log_hash, node_hashes }
```

---

## Monitoring Flow

```
event_stream: List[signal_event_dicts]
    ↓
OperationalDriftMonitor.ingest(event) × N
    │
    ├─ append to rolling window (per node, max 10)
    ├─ check rolling avg confidence < 0.75 → CONFIDENCE_DEGRADATION
    ├─ check variance > 0.008              → VARIANCE_SPIKE
    └─ check CONVERGED → SUSPENDED/DIVERGED → STATE_SHIFT
    ↓
drift_log: List[DriftEvent]
    ↓
summary() → { events_ingested, drift_events, nodes_monitored, drift_log }
```

---

*Dhiraj Chavan · Marine Intelligence System · May 2026*
