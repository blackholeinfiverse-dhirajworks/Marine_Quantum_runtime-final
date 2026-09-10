# Docs/QUANTUM_RUNTIME_GUIDE.md
# Quantum Runtime Guide
**Author:** Dhiraj Chavan | Marine Intelligence System | June 2026

---

## Submitting a Single Circuit

```python
import sys; sys.path.insert(0, ".")
from src.quantum.providers.base import CircuitSpec, BackendRequirements
from src.quantum.providers.quantum_execution_router import route_and_execute

circuit = CircuitSpec(
    num_qubits=3, shots=2048, seed=42,
    gate_sequence=[
        {"gate": "h",  "qubits": [0]},
        {"gate": "cx", "qubits": [0, 1]},
        {"gate": "cx", "qubits": [1, 2]},
    ],
)

result = route_and_execute(circuit, BackendRequirements(require_simulator=True))
print(result["status"])                          # SUCCESS
print(result["result"]["measurement_counts"])     # {'000': ~1024, '111': ~1024}
print(result["routing"]["final_provider"])        # whichever provider was healthy and capable
```

## Forcing a Specific Provider

```python
result = route_and_execute(circuit, BackendRequirements(preferred_provider="aer"))
```

## Submitting Many Circuits Through the Distributed Manager

```python
from src.runtime.distributed_runtime_manager import DistributedRuntimeManager, RetryPolicy

mgr = DistributedRuntimeManager(node_ids=["node_1", "node_2", "node_3"])
job_id = mgr.submit_job(circuit, BackendRequirements(require_simulator=True),
                        retry_policy=RetryPolicy(max_retries=2))
results = mgr.process_queue()
status = mgr.get_job_status(job_id)
```

## Cancelling and Monitoring Jobs

```python
mgr.cancel_job(job_id)
mgr.queue_statistics()
mgr.event_log(limit=20)
```

## Checking Backend Health and Discovery

```python
from src.quantum.providers import provider_registry

provider_registry.list_providers()
provider_registry.backend_health()
provider_registry.backend_discovery()
provider_registry.provider_health_summary()
```

## Gate Sequence Format

Each entry in `gate_sequence` is `{"gate": <name>, "qubits": [<int>, ...]}`,
with an optional `"param"` key for parameterized rotations:

| Gate | Qubits | Param |
|---|---|---|
| `h`, `x`, `y`, `z` | 1 | — |
| `cx`, `cz`, `swap` | 2 | — |
| `rx`, `ry`, `rz` | 1 | required (radians) |

The `local_simulator` provider does not use these gate semantics literally
(it's a deterministic classical approximation, not real linear algebra —
see `KNOWN_LIMITATIONS.md`). The `aer` provider executes them exactly via
real Qiskit gate operations.

## Circuit Construction Limits

`max_qubits` and `max_shots` vary per backend — check
`capabilities.to_dict()` on any backend before submitting a circuit that
might exceed them. `BackendRequirements` lets you express minimums so
negotiation automatically rejects backends that can't fit your circuit.
