# src/quantum/providers/ibm_runtime_provider.py
# IBM Quantum Runtime Adapter — Phase 1 provider abstraction.
#
# HONEST DECLARATION:
# This adapter is shape-complete (correctly implements QuantumExecutionProvider
# and QuantumExecutionBackend) but cannot execute real jobs from this sandbox.
# Real IBM Runtime execution requires:
#   1. `qiskit-ibm-runtime` SDK installed
#   2. IBM Quantum API credentials (IBM_QUANTUM_TOKEN)
#   3. Network egress to IBM's cloud API (not permitted in this environment)
#
# Its purpose here is to PROVE the provider abstraction is real: this class
# satisfies the exact same QuantumExecutionProvider interface as the local
# simulator and Aer provider, and the runtime/router accept it identically.
# health() honestly reports CREDENTIALS_REQUIRED / NETWORK_UNREACHABLE rather
# than silently returning fake measurement counts.
#
# To activate for real: implement execute() using qiskit_ibm_runtime.QiskitRuntimeService
# and SamplerV2, following the exact same CircuitSpec -> ExecutionResult contract
# that AerProvider already proves works.

import os
import time
from typing import List, Optional

from src.quantum.providers.base import (
    QuantumExecutionProvider, QuantumExecutionBackend,
    BackendCapabilities, BackendHealth, BackendStatus,
    CircuitSpec, ExecutionResult, ProviderUnavailableError,
)

try:
    import qiskit_ibm_runtime  # noqa: F401
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False


class IBMRuntimeBackend(QuantumExecutionBackend):
    def __init__(self, name: str, max_qubits: int) -> None:
        self.name = name
        self.capabilities = BackendCapabilities(
            max_qubits=max_qubits, max_shots=100_000, supports_noise=True,
            native_gates=["rz", "sx", "x", "cx", "ecr"],
            is_simulator=False, is_real_hardware=True,
        )

    def execute(self, circuit: CircuitSpec) -> ExecutionResult:
        raise ProviderUnavailableError(
            "IBM Runtime execution requires qiskit-ibm-runtime SDK, a valid "
            "IBM_QUANTUM_TOKEN, and network egress to IBM's cloud API. None "
            "of these are available in this environment. This is the "
            "honestly-declared boundary of the provider abstraction proof: "
            "the interface is real, the credential/network path is not."
        )

    def health(self, seq: int) -> BackendHealth:
        if not _SDK_AVAILABLE:
            return BackendHealth(
                provider_name="ibm_runtime", backend_name=self.name,
                status=BackendStatus.UNAVAILABLE,
                reason="qiskit-ibm-runtime SDK not installed",
                last_checked_seq=seq,
            )
        if not os.environ.get("IBM_QUANTUM_TOKEN"):
            return BackendHealth(
                provider_name="ibm_runtime", backend_name=self.name,
                status=BackendStatus.CREDENTIALS_REQUIRED,
                reason="IBM_QUANTUM_TOKEN environment variable not set",
                last_checked_seq=seq,
            )
        return BackendHealth(
            provider_name="ibm_runtime", backend_name=self.name,
            status=BackendStatus.NETWORK_UNREACHABLE,
            reason="Network egress to IBM Quantum cloud API not permitted in this environment",
            last_checked_seq=seq,
        )


class IBMRuntimeProvider(QuantumExecutionProvider):
    """
    Shape-complete IBM Quantum Runtime adapter.
    See module docstring for the honest declaration of what is and is not real.
    """

    def __init__(self) -> None:
        self.provider_name = "ibm_runtime"
        self._backends = [
            IBMRuntimeBackend("ibm_brisbane_proxy", max_qubits=127),
            IBMRuntimeBackend("ibm_kyiv_proxy", max_qubits=127),
        ]

    def list_backends(self) -> List[QuantumExecutionBackend]:
        return list(self._backends)

    def get_backend(self, backend_name: str) -> Optional[QuantumExecutionBackend]:
        for b in self._backends:
            if b.name == backend_name:
                return b
        return None
