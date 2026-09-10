# TESTING_PACKET.md
# BHIV Universal Testing Protocol v2
# marine_quantum_runtime | Marine Intelligence System
# For: Vinayak — Testing Department
# Author: Dhiraj Chavan | Date: June 2026

---

## Scope

Verify that all four runtime modules execute correctly, deterministically, and with
correct failure handling. Full verification in under 10 minutes.

---

## Prerequisites

```bash
python --version        # must be 3.8+
pip install -r requirements.txt
```

---

## Command Sequence

Run each command and confirm: exit code 0, `[PASS]` in output.

```bash
# 1 — Signal module
python run/run_signal.py
# Expected: EXECUTION COMPLETE | Determinism: PASS

# 2 — Distributed QApp module
python run/run_distributed_qapp.py
# Expected: EXECUTION COMPLETE | Determinism: PASS

# 3 — Operational Drift module
python run/run_operational_drift.py
# Expected: EXECUTION COMPLETE | Determinism: PASS

# 4 — Quantum Pipeline module (requires qiskit)
python run/run_quantum_pipeline.py
# Expected: EXECUTION COMPLETE | Determinism: PASS
```

---

## Expected Outputs (Summary)

### signal
- `"next": "CONVERGED"`, `sigma=0.04472136`, `ts=2026-01-01T02:00:00Z`
- 5 determinism runs: all hash `42a8cbd540e0ad22...`
- Failure cases: SUSPENDED, DIVERGED, 2× ValidationError

### quantum_pipeline
- `degradation_probability: 0.510678`, `confidence_score: 0.130492`
- 5 determinism runs: all hash `243c9ccc239bec9e...`
- Failure cases: invalid salinity, missing pH, low shots

### distributed_qapp
- `consistent: True`, `consensus_hash: c504d11369d96a07...`, `log_entries: 3`
- 5 determinism runs: all hash `b8ca5117e47b0e8a...`
- Failure case: missing qapp_id → FAILED

### operational_monitor
- `drift_status: WARN`, `state_counts: {CONVERGED:8, SUSPENDED:4, DIVERGED:2}`
- Alert: `WARN: DIVERGED rate=14.3% exceeds 10%`
- 5 determinism runs: all hash `5c7d4aee057ff7cd...`
- Failure case: missing events field → FAILED

---

## Evidence Checklist

Take screenshots immediately after each run:

- [ ] `testing/testing_evidence/signal_run.png`
- [ ] `testing/testing_evidence/quantum_run.png`
- [ ] `testing/testing_evidence/distributed_run.png`
- [ ] `testing/testing_evidence/drift_run.png`

---

## Pass Criteria

| Module | Exit 0 | Determinism | Failures |
|---|---|---|---|
| signal | ✓ | ✓ | ✓ |
| quantum_pipeline | ✓ | ✓ | ✓ |
| distributed_qapp | ✓ | ✓ | ✓ |
| operational_monitor | ✓ | ✓ | ✓ |

All four rows must be ✓ for sign-off.

---

## Contact

Any failure: contact **Dhiraj Chavan** with the full console output and screenshot.
