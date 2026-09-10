# Docs/DEPLOYMENT_GUIDE.md
# Deployment Guide — Quantum Runtime Capability
**Author:** Dhiraj Chavan | Marine Intelligence System | July 2026

---

## Development (No Credentials)

Everything works with stdlib-only. The Aer provider also works if
`qiskit` and `qiskit-aer` are installed.

```bash
pip install qiskit qiskit-aer --break-system-packages  # optional but recommended
python run/run_ecosystem_integration.py                 # verifies all 33 checks
```

Providers that require credentials (`ibm_runtime`, `ionq`) will report
`CREDENTIALS_REQUIRED` or `NETWORK_UNREACHABLE` and be skipped by the
router. This is the expected, correct behavior in development.

---

## Staging / Production (With Credentials)

### IBM Runtime

```bash
pip install qiskit qiskit-ibm-runtime
export IBM_QUANTUM_TOKEN=<your_token>
```

Then update `src/quantum/providers/ibm_runtime_provider.py` — implement
`execute()` using `qiskit_ibm_runtime.QiskitRuntimeService` and
`SamplerV2`. The `CircuitSpec → QuantumCircuit` builder already exists
in `aer_provider.py` (`_build_qiskit_circuit`); reuse it. Return an
`ExecutionResult` with the same shape. The rest of the runtime changes
nothing.

### IonQ

```bash
pip install qiskit-ionq  # or qiskit-terra + custom provider
export IONQ_API_KEY=<your_key>
```

Same pattern — implement `execute()` in `ionq_provider.py`. The interface
contract is in `base.py`. No other files change.

---

## Attaching Ecosystem Dependencies at Startup

All dependencies use dependency injection. Wire them at process startup
before any invocations:

```python
from src.federation.federation_runtime import FederationRuntime
from src.runtime.capability_runtime import (
    attach_replay_authority, attach_evidence_ledger,
)
from src.governance.replay_legitimacy import CanonicalReplayAuthority
from src.runtime.persistent_history import PersistentHistory

# Wire real replay authority (set allow_re_execution=False for production)
auth = CanonicalReplayAuthority(allow_re_execution=False)
attach_replay_authority(auth)

# Wire persistent evidence ledger
ledger = PersistentHistory(path="/var/log/bhiv/runtime_history.jsonl")
attach_evidence_ledger(ledger)

# Alternatively — attach Pritesh's real implementations when available:
# attach_replay_authority(PriteshReplayAuthority(...))
# attach_evidence_ledger(PriteshEvidenceLedger(...))
```

---

## Production Execution Limits

Adjust in `src/quantum/production_runtime.py`:

```python
from src.quantum.production_runtime import ExecutionLimits

production_limits = ExecutionLimits(
    max_qubits=29,      # increase when IBM 127-qubit backend is active
    max_shots=100_000,
    max_retries=3,
    min_shots=100,
)
```

Pass `limits=production_limits` to `production_execute()`.

---

## Requirements Summary

| Environment | Required | Optional |
|---|---|---|
| Development | Python 3.8+ (stdlib only) | `qiskit`, `qiskit-aer` |
| Staging/Production | Python 3.8+, `qiskit`, `qiskit-aer` | `qiskit-ibm-runtime` (IBM), IonQ SDK |
| Real hardware | All above + credentials + network egress to provider APIs | — |

No other pip dependencies. No databases. No message brokers. No containers required.
