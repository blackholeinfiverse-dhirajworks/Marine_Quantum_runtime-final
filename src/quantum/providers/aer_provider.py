# src/quantum/providers/aer_provider.py
# Aer Simulator Provider — REAL execution via qiskit-aer when installed.
#
# Unlike the IBM/IonQ adapters in this same package, this provider is not a
# shape-complete stub. When qiskit + qiskit-aer are importable, every call
# to execute() runs an actual AerSimulator job and returns real measurement
# counts. If qiskit-aer is not installed, health() reports UNAVAILABLE and
# execute() raises ProviderUnavailableError — it never silently fakes output.

import time
from typing import List, Optional

from src.quantum.providers.base import (
    QuantumExecutionProvider, QuantumExecutionBackend,
    BackendCapabilities, BackendHealth, BackendStatus,
    CircuitSpec, ExecutionResult, ProviderUnavailableError,
)

try:
    from qiskit import QuantumCircuit, transpile
    from qiskit_aer import AerSimulator
    _AER_AVAILABLE = True
    _AER_IMPORT_ERROR = None
except ImportError as exc:
    _AER_AVAILABLE = False
    _AER_IMPORT_ERROR = str(exc)


_GATE_DISPATCH = {
    "h":   lambda qc, q: qc.h(q[0]),
    "x":   lambda qc, q: qc.x(q[0]),
    "y":   lambda qc, q: qc.y(q[0]),
    "z":   lambda qc, q: qc.z(q[0]),
    "cx":  lambda qc, q: qc.cx(q[0], q[1]),
    "cz":  lambda qc, q: qc.cz(q[0], q[1]),
    "swap": lambda qc, q: qc.swap(q[0], q[1]),
    "rx":  lambda qc, q, p: qc.rx(p, q[0]),
    "ry":  lambda qc, q, p: qc.ry(p, q[0]),
    "rz":  lambda qc, q, p: qc.rz(p, q[0]),
}


def _build_qiskit_circuit(circuit: CircuitSpec):
    qc = QuantumCircuit(circuit.num_qubits, circuit.num_qubits)
    for gate_spec in circuit.gate_sequence:
        gate = gate_spec["gate"]
        qubits = gate_spec["qubits"]
        if gate in ("rx", "ry", "rz"):
            param = gate_spec.get("param", 0.0)
            _GATE_DISPATCH[gate](qc, qubits, param)
        else:
            _GATE_DISPATCH[gate](qc, qubits)
    qc.measure(range(circuit.num_qubits), range(circuit.num_qubits))
    return qc


class AerSimulatorBackend(QuantumExecutionBackend):
    def __init__(self) -> None:
        self.name = "aer_simulator"
        self.capabilities = BackendCapabilities(
            max_qubits=29, max_shots=1_000_000, supports_noise=True,
            native_gates=list(_GATE_DISPATCH.keys()),
            is_simulator=True, is_real_hardware=False,
        )

    def execute(self, circuit: CircuitSpec) -> ExecutionResult:
        if not _AER_AVAILABLE:
            raise ProviderUnavailableError(
                f"qiskit-aer not installed: {_AER_IMPORT_ERROR}. "
                f"Run: pip install qiskit qiskit-aer"
            )
        t0 = time.perf_counter()
        qc = _build_qiskit_circuit(circuit)
        sim = AerSimulator(seed_simulator=circuit.seed)
        transpiled = transpile(qc, sim, seed_transpiler=circuit.seed)
        job = sim.run(transpiled, shots=circuit.shots, seed_simulator=circuit.seed)
        result = job.result()
        counts = {str(k): int(v) for k, v in result.get_counts().items()}
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return ExecutionResult(
            provider_name="aer", backend_name=self.name,
            measurement_counts=counts, shots_used=circuit.shots,
            is_simulator=True, seed=circuit.seed, execution_time_ms=elapsed_ms,
        )

    def health(self, seq: int) -> BackendHealth:
        if _AER_AVAILABLE:
            return BackendHealth(
                provider_name="aer", backend_name=self.name,
                status=BackendStatus.AVAILABLE,
                reason="qiskit-aer installed and importable",
                last_checked_seq=seq,
            )
        return BackendHealth(
            provider_name="aer", backend_name=self.name,
            status=BackendStatus.UNAVAILABLE,
            reason=f"qiskit-aer not installed: {_AER_IMPORT_ERROR}",
            last_checked_seq=seq,
        )


class AerProvider(QuantumExecutionProvider):
    """
    Real local quantum circuit simulator via Qiskit Aer.
    Genuinely executes circuits — not a stub — when qiskit-aer is installed.
    Degrades to UNAVAILABLE (not a silent fake) when it is not.
    """

    def __init__(self) -> None:
        self.provider_name = "aer"
        self._backend = AerSimulatorBackend()

    def list_backends(self) -> List[QuantumExecutionBackend]:
        return [self._backend]

    def get_backend(self, backend_name: str) -> Optional[QuantumExecutionBackend]:
        return self._backend if backend_name == self._backend.name else None


def is_aer_available() -> bool:
    return _AER_AVAILABLE
