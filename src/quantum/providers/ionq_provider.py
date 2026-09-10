# src/quantum/providers/ionq_provider.py
# IonQ Adapter Interface — Phase 1 provider abstraction.
#
# HONEST DECLARATION: same posture as ibm_runtime_provider.py. Shape-complete,
# satisfies QuantumExecutionProvider exactly, cannot execute real jobs from
# this sandbox (requires IonQ API key + network egress to IonQ's cloud API,
# neither available here). health() reports the true reason rather than
# faking output.

import os
import time
from typing import List, Optional

from src.quantum.providers.base import (
    QuantumExecutionProvider, QuantumExecutionBackend,
    BackendCapabilities, BackendHealth, BackendStatus,
    CircuitSpec, ExecutionResult, ProviderUnavailableError,
)


class IonQBackend(QuantumExecutionBackend):
    def __init__(self, name: str, max_qubits: int, is_simulator: bool) -> None:
        self.name = name
        self.capabilities = BackendCapabilities(
            max_qubits=max_qubits, max_shots=10_000, supports_noise=not is_simulator,
            native_gates=["gpi", "gpi2", "ms"],
            is_simulator=is_simulator, is_real_hardware=not is_simulator,
        )

    def execute(self, circuit: CircuitSpec) -> ExecutionResult:
        raise ProviderUnavailableError(
            "IonQ execution requires an IONQ_API_KEY and network egress to "
            "IonQ's cloud API. Neither is available in this environment. "
            "Interface is real and provider-agnostic; the credential/network "
            "path to real IonQ hardware/cloud-simulator is not."
        )

    def health(self, seq: int) -> BackendHealth:
        if not os.environ.get("IONQ_API_KEY"):
            return BackendHealth(
                provider_name="ionq", backend_name=self.name,
                status=BackendStatus.CREDENTIALS_REQUIRED,
                reason="IONQ_API_KEY environment variable not set",
                last_checked_seq=seq,
            )
        return BackendHealth(
            provider_name="ionq", backend_name=self.name,
            status=BackendStatus.NETWORK_UNREACHABLE,
            reason="Network egress to IonQ cloud API not permitted in this environment",
            last_checked_seq=seq,
        )


class IonQProvider(QuantumExecutionProvider):
    """Shape-complete IonQ adapter. See module docstring for honest declaration."""

    def __init__(self) -> None:
        self.provider_name = "ionq"
        self._backends = [
            IonQBackend("ionq_simulator_proxy", max_qubits=29, is_simulator=True),
            IonQBackend("ionq_aria_proxy", max_qubits=25, is_simulator=False),
        ]

    def list_backends(self) -> List[QuantumExecutionBackend]:
        return list(self._backends)

    def get_backend(self, backend_name: str) -> Optional[QuantumExecutionBackend]:
        for b in self._backends:
            if b.name == backend_name:
                return b
        return None
