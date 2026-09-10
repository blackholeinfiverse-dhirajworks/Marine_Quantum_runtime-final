# Docs/PROVIDER_MODEL.md
# Quantum Provider Abstraction Model
**Author:** Dhiraj Chavan | Marine Intelligence System | June 2026

---

## The Contract

Every quantum backend — real or simulated, present or future — implements
exactly two interfaces from `src/quantum/providers/base.py`:

```python
class QuantumExecutionProvider(ABC):
    provider_name: str
    def list_backends(self) -> List[QuantumExecutionBackend]: ...
    def get_backend(self, backend_name: str) -> Optional[QuantumExecutionBackend]: ...
    def negotiate(self, requirements: BackendRequirements) -> Optional[QuantumExecutionBackend]: ...

class QuantumExecutionBackend(ABC):
    name: str
    capabilities: BackendCapabilities
    def execute(self, circuit: CircuitSpec) -> ExecutionResult: ...
    def health(self, seq: int) -> BackendHealth: ...
```

The runtime, the router, and the distributed manager depend ONLY on these
two interfaces. None of them import `qiskit`, `qiskit_aer`, `qiskit_ibm_runtime`,
or any IonQ SDK directly. All provider-specific code lives inside the
provider's own file in `src/quantum/providers/`.

---

## Registered Providers

| Provider | File | Status | Real Execution |
|---|---|---|---|
| `local_simulator` | `local_simulator_provider.py` | Always AVAILABLE | Yes — stdlib-only deterministic classical approximation |
| `aer` | `aer_provider.py` | AVAILABLE (qiskit-aer installed) | Yes — genuine `AerSimulator` execution |
| `ibm_runtime` | `ibm_runtime_provider.py` | CREDENTIALS_REQUIRED / NETWORK_UNREACHABLE | No — shape-complete, honestly unavailable in this sandbox |
| `ionq` | `ionq_provider.py` | CREDENTIALS_REQUIRED | No — shape-complete, honestly unavailable in this sandbox |

---

## Standardized Data Shapes

### `CircuitSpec` (input — same shape for every provider)
```python
CircuitSpec(
    num_qubits=3,
    gate_sequence=[{"gate": "h", "qubits": [0]}, {"gate": "cx", "qubits": [0,1]}],
    shots=4096, seed=42,
)
```

### `ExecutionResult` (output — same shape regardless of which provider ran it)
```python
{
    "provider_name": "aer", "backend_name": "aer_simulator",
    "measurement_counts": {"000": 490, "111": 534},
    "shots_used": 1024, "is_simulator": True, "seed": 42,
    "execution_time_ms": 91.2,
}
```

A caller cannot tell from the result shape alone which provider executed
the circuit. This is the Phase 4 "identical execution surface" requirement,
proven in `run_ecosystem_integration.py` Phase 7.1 by comparing key sets
across `local_simulator` and `aer` results.

---

## Negotiation and Failover

`BackendRequirements` describes what a caller needs:

```python
BackendRequirements(
    min_qubits=3, min_shots=1024,
    require_real_hardware=False, require_simulator=True,
    preferred_provider="aer",
)
```

`quantum_execution_router.route_and_execute()` tries the preferred provider
first, then falls through every other registered provider in order,
catching `ProviderUnavailableError` and recording each attempt. It never
returns a fabricated success — if no provider can satisfy the requirements,
it returns `status: ROUTING_FAILED` with the full attempt audit trail.

---

## Adding a New Provider

1. Create `src/quantum/providers/your_provider.py`.
2. Implement `QuantumExecutionProvider` and `QuantumExecutionBackend`.
3. Call `provider_registry.register_provider(YourProvider())`.

No other file changes. This is proven, not asserted — see
`run/run_ecosystem_integration.py` and the `KNOWN_LIMITATIONS.md` entry on
the `rigetti` test provider.

---

## Capability Negotiation Logic

```
BackendCapabilities.satisfies(requirements):
    if requirements.min_qubits > capabilities.max_qubits: DENY
    if requirements.min_shots  > capabilities.max_shots:  DENY
    if requirements.require_real_hardware and not capabilities.is_real_hardware: DENY
    if requirements.require_simulator and not capabilities.is_simulator: DENY
    otherwise: PERMIT
```

This is pure, deterministic, and provider-agnostic — it operates only on
the `BackendCapabilities` dataclass, never on provider-specific SDK objects.
