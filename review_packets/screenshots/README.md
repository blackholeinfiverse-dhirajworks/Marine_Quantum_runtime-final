# Screenshots Folder

This folder contains raw console captures in place of GUI screenshots.
No GUI environment is available in this build context.

## Contents

| File | Corresponds to brief screenshot requirement |
|---|---|
| `run_signal_console.txt` | Signal execution proof (Tasks 1–4) |
| `run_quantum_pipeline_console.txt` | Quantum pipeline proof (Task 8) |
| `run_distributed_qapp_console.txt` | Distributed execution |
| `run_operational_drift_console.txt` | Operational monitoring |
| `run_governance_console.txt` | Governance layer (46/46 checks) |
| `run_ecosystem_integration_console.txt` | Runtime federation + provider switching + replay verification + distributed execution + dashboard telemetry + testing results + failure handling + health APIs (33/33 checks) |
| `provider_health_snapshot.txt` | Backend health + discovery snapshot |

## For Vinayak (Independent Testing)

```bash
cd marine_quantum_runtime
python run/run_ecosystem_integration.py
```

Expected: exit code 0, "Checks passed: 33 / 33", every section marked PASS ✅.
Capture real screenshots of your terminal output for the formal deliverable.

## What the brief requires vs what is here

The brief requires image screenshots. These are text captures.
Real screenshots require running the scripts locally. The test suite is
deterministic — any machine with Python 3.8+ and `qiskit qiskit-aer` installed
(`pip install qiskit qiskit-aer --break-system-packages`) will produce
identical output to these captures.
