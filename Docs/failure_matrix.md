# docs/failure_matrix.md
# Failure Matrix — Marine Intelligence Quantum Runtime

All failure modes across all modules. No silent recovery anywhere.

---

## Signal Layer Failures

| Trigger | Detection | Response | Exception |
|---|---|---|---|
| Missing required field | `validate_input()` before any computation | ValidationError with exact field list | `ValidationError` |
| `confidence` out of `[0.0, 1.0]` | `validate_input()` range check | ValidationError with field, value, rule | `ValidationError` |
| `energy_delta < 0` | `validate_input()` bound check | ValidationError | `ValidationError` |
| `iterations < 0` | `validate_input()` bound check | ValidationError | `ValidationError` |
| `node_id` empty string | `validate_input()` string check | ValidationError | `ValidationError` |
| Wrong payload type (not dict) | `validate_input()` type check | ValidationError | `ValidationError` |
| `energy_delta > 0.01` | `resolve_transition()` Rule 1 | State = DIVERGED (valid signal, not error) | None |
| `iterations > 500` | `resolve_transition()` Rule 2 | State = DIVERGED | None |
| `confidence < 0.70` | `resolve_transition()` Rule 3 | State = SUSPENDED | None |
| `variance > 0.01` | `resolve_transition()` Rule 4 | State = SUSPENDED | None |
| Output missing required key | `validate_output()` structural check | ValidationError before return | `ValidationError` |
| `transition.seq` not int | `validate_output()` type check | ValidationError before return | `ValidationError` |

---

## Quantum Pipeline Failures

| Trigger | Detection | Response | Error Code |
|---|---|---|---|
| Corrosion input out of physical range | `validate_corrosion_input()` | `SchemaValidationError` with field + range | `INPUT_VALIDATION_FAILED` |
| Missing corrosion field | `validate_corrosion_input()` | `SchemaValidationError` | `INPUT_VALIDATION_FAILED` |
| `shots < 512` | Pre-check in `run_corrosion_qapp()` | `ValueError` | `QUANTUM_EXECUTION_FAILED` |
| `confidence_score < 0.5` | `validate_corrosion_output()` Rule R4 | Returns False → `CONTRACT_VIOLATION` | `CONTRACT_VIOLATION` |
| `measurement_distribution` sum ≠ 1.0 | Rule R7 (±0.01 tolerance) | `CONTRACT_VIOLATION` | `CONTRACT_VIOLATION` |
| Missing output key | Rule R1 | `CONTRACT_VIOLATION` | `CONTRACT_VIOLATION` |

---

## Distributed QApp Failures

| Trigger | Detection | Response | Exception |
|---|---|---|---|
| Delayed propagation (seq gap > threshold) | `simulate_delayed_propagation()` | `CAUSAL_DELAY` flag — accepted with audit log | None — flagged |
| Duplicate `invocation_id` | `simulate_duplicate_propagation()` | Hard reject — log unchanged | `PropagationFailure` |
| Missing node propagation | `simulate_missing_propagation()` | HALT — partial state preserved for valid nodes | `PropagationFailure` |
| Out-of-order `sequence_id` | `simulate_out_of_order()` | HALT at first violation — batch rejected | `PropagationFailure` |
| Replay hash mismatch vs live | Phase 4 cross-check | Hard FAIL — prints diff, exits code 1 | `sys.exit(1)` |
| Shuffle replay non-convergence | Phase 7 Proof B | Hard FAIL | `sys.exit(1)` |

---

## Contract Failures

| Trigger | Detection | Response |
|---|---|---|
| Missing top-level key in event | `enforce_signal_contract()` | `ContractViolation` with field list |
| `transition.next` not in valid states | `enforce_signal_contract()` | `ContractViolation` |
| `confidence` out of range | `enforce_signal_contract()` | `ContractViolation` |
| `sigma < 0` | `enforce_signal_contract()` | `ContractViolation` |
| Schema version mismatch | `check_version_compatibility()` | Returns `compatible=False` with reason |

---

## Monitoring Failures

| Trigger | Detection | Response |
|---|---|---|
| Avg confidence < 0.75 (rolling window) | `OperationalDriftMonitor._check_drift()` | `DriftEvent(CONFIDENCE_DEGRADATION)` appended to drift log |
| `variance > 0.008` | `_check_drift()` | `DriftEvent(VARIANCE_SPIKE)` |
| State shifts CONVERGED → SUSPENDED/DIVERGED | `_check_drift()` | `DriftEvent(STATE_SHIFT)` |

---

## invoke_runtime Gateway Failures

| Trigger | Detection | Response |
|---|---|---|
| Unknown module name | Name check in `invoke_runtime()` | `{"status": "MODULE_NOT_FOUND", ...}` |
| Module import error | `ImportError` catch | `{"status": "IMPORT_ERROR", ...}` |
| Runtime exception in module | `Exception` catch | `{"status": "RUNTIME_ERROR", ...}` |

---

## Failure Response Format (all modules)

Every failure that reaches the `invoke_runtime` surface returns:

```json
{
  "module":  "<module_name>",
  "status":  "<VALIDATION_ERROR | CONTRACT_VIOLATION | ERROR | MODULE_NOT_FOUND>",
  "result":  null,
  "error":   "<human-readable reason>"
}
```

**No silent failures anywhere in the system.**

---

*Dhiraj Chavan · Marine Intelligence System · May 2026*
