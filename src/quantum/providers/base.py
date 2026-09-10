# src/quantum/providers/base.py
# Quantum Execution Provider Abstraction — Phase 1: Quantum Runtime Modernization
#
# This is the contract every quantum backend (IBM, Aer, IonQ, local simulator,
# or any future provider) must implement. The runtime never imports a specific
# provider's SDK directly — it only depends on this interface.
#
# Adding a new provider requires ZERO changes to the runtime, router, or
# distributed manager. This is the testable claim of Phase 1.

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class BackendStatus(Enum):
    AVAILABLE             = "AVAILABLE"
    UNAVAILABLE           = "UNAVAILABLE"
    DEGRADED              = "DEGRADED"
    CREDENTIALS_REQUIRED  = "CREDENTIALS_REQUIRED"
    NETWORK_UNREACHABLE   = "NETWORK_UNREACHABLE"


class JobStatus(Enum):
    QUEUED     = "QUEUED"
    ROUTING    = "ROUTING"
    RUNNING    = "RUNNING"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"
    CANCELLED  = "CANCELLED"


class ProviderUnavailableError(Exception):
    """Raised when a provider cannot execute (no credentials, no network, etc.)."""
    pass


@dataclass
class BackendCapabilities:
    """What a backend can do. Used for capability negotiation."""
    max_qubits:       int
    max_shots:        int
    supports_noise:   bool
    native_gates:     List[str]
    is_simulator:     bool
    is_real_hardware: bool

    def to_dict(self) -> dict:
        return {
            "max_qubits":       self.max_qubits,
            "max_shots":        self.max_shots,
            "supports_noise":   self.supports_noise,
            "native_gates":     self.native_gates,
            "is_simulator":     self.is_simulator,
            "is_real_hardware": self.is_real_hardware,
        }

    def satisfies(self, requirements: "BackendRequirements") -> bool:
        if requirements.min_qubits is not None and self.max_qubits < requirements.min_qubits:
            return False
        if requirements.min_shots is not None and self.max_shots < requirements.min_shots:
            return False
        if requirements.require_real_hardware and not self.is_real_hardware:
            return False
        if requirements.require_simulator and not self.is_simulator:
            return False
        return True


@dataclass
class BackendRequirements:
    """What a caller needs from a backend. Used for negotiation."""
    min_qubits:            Optional[int] = None
    min_shots:              Optional[int] = None
    require_real_hardware: bool = False
    require_simulator:     bool = False
    preferred_provider:    Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "min_qubits":            self.min_qubits,
            "min_shots":             self.min_shots,
            "require_real_hardware": self.require_real_hardware,
            "require_simulator":     self.require_simulator,
            "preferred_provider":    self.preferred_provider,
        }


@dataclass
class BackendHealth:
    provider_name:   str
    backend_name:    str
    status:          BackendStatus
    reason:          str
    last_checked_seq: int

    def to_dict(self) -> dict:
        return {
            "provider_name":    self.provider_name,
            "backend_name":     self.backend_name,
            "status":           self.status.value,
            "reason":           self.reason,
            "last_checked_seq": self.last_checked_seq,
        }


@dataclass
class CircuitSpec:
    """
    Provider-agnostic circuit specification.
    Every provider must accept this shape and translate to its own SDK internally.
    """
    num_qubits:     int
    gate_sequence:  List[Dict[str, Any]]   # e.g. [{"gate":"h","qubits":[0]}, {"gate":"cx","qubits":[0,1]}]
    shots:          int = 4096
    seed:           int = 42

    def to_dict(self) -> dict:
        return {
            "num_qubits":    self.num_qubits,
            "gate_sequence": self.gate_sequence,
            "shots":         self.shots,
            "seed":          self.seed,
        }


@dataclass
class ExecutionResult:
    """
    Standardized result shape. Every provider returns this exact structure
    regardless of backend. This is the Phase 4 "identical execution surface" proof.
    """
    provider_name:      str
    backend_name:        str
    measurement_counts:   Dict[str, int]
    shots_used:           int
    is_simulator:         bool
    seed:                 Optional[int]
    execution_time_ms:    float

    def to_dict(self) -> dict:
        return {
            "provider_name":      self.provider_name,
            "backend_name":       self.backend_name,
            "measurement_counts": self.measurement_counts,
            "shots_used":         self.shots_used,
            "is_simulator":       self.is_simulator,
            "seed":               self.seed,
            "execution_time_ms":  round(self.execution_time_ms, 3),
        }


class QuantumExecutionBackend(ABC):
    """A single executable backend offered by a provider (e.g. 'aer_simulator', 'ibm_brisbane')."""

    name: str
    capabilities: BackendCapabilities

    @abstractmethod
    def execute(self, circuit: CircuitSpec) -> ExecutionResult:
        ...

    @abstractmethod
    def health(self, seq: int) -> BackendHealth:
        ...


class QuantumExecutionProvider(ABC):
    """
    A quantum execution provider (IBM, Aer, IonQ, local simulator, or any future one).

    The runtime depends ONLY on this interface. Concrete providers live in
    src/quantum/providers/. Registering a new provider requires implementing
    this class and calling provider_registry.register_provider() — nothing
    else in the runtime changes.
    """

    provider_name: str

    @abstractmethod
    def list_backends(self) -> List[QuantumExecutionBackend]:
        ...

    @abstractmethod
    def get_backend(self, backend_name: str) -> Optional[QuantumExecutionBackend]:
        ...

    def negotiate(self, requirements: BackendRequirements) -> Optional[QuantumExecutionBackend]:
        """Default negotiation: first backend whose capabilities satisfy requirements."""
        for backend in self.list_backends():
            if backend.capabilities.satisfies(requirements):
                return backend
        return None

    def discover(self) -> List[dict]:
        return [
            {"backend_name": b.name, "capabilities": b.capabilities.to_dict()}
            for b in self.list_backends()
        ]
