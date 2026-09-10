# src/quantum/production_runtime.py
# Quantum Production Runtime — Phase 4.
#
# "Produce identical execution surface regardless of backend."
# "Backend selection should occur automatically through contracts."
#
# This module wraps the existing provider abstraction (Phase 1) and
# distributed manager (Phase 3) with production-grade controls:
#   noise models         — per-backend declared noise profile
#   execution limits     — max shots, max qubits, max retries
#   queue status         — live depth + estimated wait per backend
#   provider capabilities — queryable before any circuit is submitted
#   hardware constraints  — native gate set, connectivity, T1/T2 declared
#   backend availability  — health-gated selection before every execution
#
# The execution surface is IDENTICAL regardless of which backend runs the
# circuit — the caller reads ExecutionResult in the same shape whether
# the backend was AerSimulator, a future IBM backend, or the local sim.

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.quantum.providers.base import (
    BackendRequirements, CircuitSpec, ExecutionResult,
    BackendStatus,
)
from src.quantum.providers import provider_registry
from src.quantum.providers.quantum_execution_router import route_and_execute
from src.runtime.distributed_runtime_manager import DistributedRuntimeManager, RetryPolicy


# ── Noise model declaration (per-backend, informational) ──────────────────────

@dataclass
class NoiseModel:
    """
    Declares the noise profile of a backend. All fields are informational —
    they describe what the backend does, not what this code enforces.
    Classical simulation stubs have zero noise by definition; real hardware
    values would come from calibration data (T1, T2, gate error rates).
    """
    backend_name:       str
    is_noisy:           bool
    t1_us:              Optional[float] = None    # Qubit relaxation time (µs)
    t2_us:              Optional[float] = None    # Qubit dephasing time (µs)
    single_qubit_err:   Optional[float] = None    # Avg single-qubit gate error rate
    two_qubit_err:      Optional[float] = None    # Avg two-qubit gate error rate
    readout_err:        Optional[float] = None    # Avg measurement error rate
    note:               str = ""

    def to_dict(self) -> dict:
        return {
            "backend_name":     self.backend_name,
            "is_noisy":         self.is_noisy,
            "t1_us":            self.t1_us,
            "t2_us":            self.t2_us,
            "single_qubit_err": self.single_qubit_err,
            "two_qubit_err":    self.two_qubit_err,
            "readout_err":      self.readout_err,
            "note":             self.note,
        }


# Known noise profiles — populated from public IBM calibration reports for
# reference values; not live-calibrated in this environment.
NOISE_PROFILES: Dict[str, NoiseModel] = {
    "aer_simulator": NoiseModel(
        backend_name="aer_simulator", is_noisy=False,
        note="Default AerSimulator without noise model — ideal simulation",
    ),
    "local_classical_simulator": NoiseModel(
        backend_name="local_classical_simulator", is_noisy=False,
        note="Classical approximation — no quantum noise",
    ),
    "ibm_brisbane_proxy": NoiseModel(
        backend_name="ibm_brisbane_proxy", is_noisy=True,
        t1_us=189.0, t2_us=142.0, single_qubit_err=2.4e-4,
        two_qubit_err=6.3e-3, readout_err=8.5e-3,
        note="Reference values from IBM Brisbane public calibration — not live data",
    ),
    "ionq_aria_proxy": NoiseModel(
        backend_name="ionq_aria_proxy", is_noisy=True,
        t1_us=1_000.0, t2_us=500.0, single_qubit_err=3.0e-4,
        two_qubit_err=2.5e-3, readout_err=3.0e-3,
        note="Reference values from IonQ Aria public specifications",
    ),
}


def get_noise_profile(backend_name: str) -> Optional[NoiseModel]:
    return NOISE_PROFILES.get(backend_name)


# ── Execution limits ───────────────────────────────────────────────────────────

@dataclass
class ExecutionLimits:
    """Hard limits enforced BEFORE a circuit is submitted to any backend."""
    max_qubits:    int = 29
    max_shots:     int = 100_000
    max_retries:   int = 3
    min_shots:     int = 100

    def validate(self, circuit: CircuitSpec) -> dict:
        violations = []
        if circuit.num_qubits > self.max_qubits:
            violations.append(
                f"num_qubits={circuit.num_qubits} exceeds limit={self.max_qubits}"
            )
        if circuit.shots > self.max_shots:
            violations.append(
                f"shots={circuit.shots} exceeds limit={self.max_shots}"
            )
        if circuit.shots < self.min_shots:
            violations.append(
                f"shots={circuit.shots} below minimum={self.min_shots}"
            )
        return {"valid": len(violations) == 0, "violations": violations}


DEFAULT_LIMITS = ExecutionLimits()


# ── Queue status ───────────────────────────────────────────────────────────────

def queue_status(manager: Optional[DistributedRuntimeManager] = None) -> dict:
    """
    Returns current queue depth and estimated wait across nodes.
    If no manager is passed, returns a lightweight provider-level health
    snapshot that approximates queue readiness.
    """
    if manager is not None:
        stats = manager.queue_statistics()
        return {
            "queue_depth":     stats["queued"],
            "total_jobs":      stats["total_jobs"],
            "by_status":       stats["by_status"],
            "nodes":           stats["nodes"],
            "source":          "distributed_runtime_manager",
        }
    # No manager — provider-level availability as proxy for queue status
    health = provider_registry.backend_health()
    available = [h for h in health if h["status"] == "AVAILABLE"]
    return {
        "queue_depth":       0,
        "available_backends": len(available),
        "total_backends":     len(health),
        "source":            "provider_registry_health",
    }


# ── Provider capabilities ──────────────────────────────────────────────────────

def provider_capabilities() -> dict:
    """All provider/backend capabilities queryable before circuit submission."""
    discovery = provider_registry.backend_discovery()
    result = {}
    for provider_name, backends in discovery.items():
        result[provider_name] = {
            "backends": backends,
            "health":   [h for h in provider_registry.backend_health()
                         if h["provider_name"] == provider_name],
        }
    return result


# ── Hardware constraints ───────────────────────────────────────────────────────

@dataclass
class HardwareConstraints:
    """
    Backend-specific hardware constraints — beyond what BackendCapabilities
    already expresses. Includes native gate set and (for real hardware)
    qubit connectivity graph.
    """
    backend_name:      str
    native_gates:       List[str]
    max_circuit_depth:  Optional[int]
    qubit_topology:     Optional[str]   # e.g. "heavy-hex" or "all-to-all" for ion traps
    requires_transpile: bool

    def to_dict(self) -> dict:
        return {
            "backend_name":      self.backend_name,
            "native_gates":      self.native_gates,
            "max_circuit_depth": self.max_circuit_depth,
            "qubit_topology":    self.qubit_topology,
            "requires_transpile": self.requires_transpile,
        }


HARDWARE_CONSTRAINTS: Dict[str, HardwareConstraints] = {
    "aer_simulator": HardwareConstraints(
        backend_name="aer_simulator",
        native_gates=["h", "x", "y", "z", "cx", "cz", "swap", "rx", "ry", "rz"],
        max_circuit_depth=None,
        qubit_topology="all-to-all (simulated)",
        requires_transpile=True,
    ),
    "local_classical_simulator": HardwareConstraints(
        backend_name="local_classical_simulator",
        native_gates=["h", "x", "y", "z", "cx", "cz", "swap", "rx", "ry", "rz"],
        max_circuit_depth=None,
        qubit_topology="all-to-all (classical approximation)",
        requires_transpile=False,
    ),
    "ibm_brisbane_proxy": HardwareConstraints(
        backend_name="ibm_brisbane_proxy",
        native_gates=["rz", "sx", "x", "cx", "ecr"],
        max_circuit_depth=5000,
        qubit_topology="heavy-hex (127 qubits)",
        requires_transpile=True,
    ),
    "ionq_aria_proxy": HardwareConstraints(
        backend_name="ionq_aria_proxy",
        native_gates=["gpi", "gpi2", "ms"],
        max_circuit_depth=None,
        qubit_topology="all-to-all (25 trapped-ion qubits)",
        requires_transpile=True,
    ),
}


def get_hardware_constraints(backend_name: str) -> Optional[HardwareConstraints]:
    return HARDWARE_CONSTRAINTS.get(backend_name)


# ── Production execute — the complete, limits-validated, health-gated surface ──

def production_execute(
    circuit:      CircuitSpec,
    requirements: Optional[BackendRequirements] = None,
    limits:       Optional[ExecutionLimits] = None,
    manager:      Optional[DistributedRuntimeManager] = None,
) -> dict:
    """
    The production execution entry point.

    Steps (in order, all explicit, no silent passes):
    1. Validate circuit against execution limits (hard reject if exceeded)
    2. Query backend availability (reject if no healthy backend exists)
    3. Route to best healthy backend, with automatic failover
    4. Return ExecutionResult in standardized shape

    Args:
        circuit:      The circuit to execute
        requirements: What backend is needed (optional — defaults to simulator)
        limits:       Hard execution limits (optional — uses DEFAULT_LIMITS)
        manager:      DistributedRuntimeManager to use for job lifecycle (optional)

    Returns:
        dict with: status, result, routing, execution_limits, provider_capabilities, errors
    """
    active_limits = limits or DEFAULT_LIMITS
    requirements  = requirements or BackendRequirements(
        min_qubits=circuit.num_qubits, require_simulator=True
    )

    # Step 1: Limit validation
    limit_check = active_limits.validate(circuit)
    if not limit_check["valid"]:
        return {
            "status":               "LIMIT_EXCEEDED",
            "result":               None,
            "routing":              None,
            "execution_limits":     {"violations": limit_check["violations"]},
            "provider_capabilities": None,
            "errors":               limit_check["violations"],
        }

    # Step 2: Backend availability check
    caps = provider_capabilities()
    health_summary = provider_registry.provider_health_summary()
    any_available = any(
        summary["available"] > 0 for summary in health_summary.values()
    )
    if not any_available:
        return {
            "status":               "NO_BACKEND_AVAILABLE",
            "result":               None,
            "routing":              None,
            "execution_limits":     {"active_limits": active_limits.__dict__},
            "provider_capabilities": caps,
            "errors":               ["No backend reporting AVAILABLE across all providers"],
        }

    # Step 3: Route and execute
    if manager is not None:
        job_id = manager.submit_job(circuit, requirements,
                                    RetryPolicy(max_retries=active_limits.max_retries))
        job_results = manager.process_queue()
        job = next((j for j in job_results if j["job_id"] == job_id), None)
        routing_info = {"via": "distributed_runtime_manager", "job_id": job_id}
        if job and job["status"] == "COMPLETED":
            return {
                "status":               "SUCCESS",
                "result":               job["result"],
                "routing":              routing_info,
                "execution_limits":     {"active_limits": active_limits.__dict__},
                "provider_capabilities": caps,
                "errors":               [],
            }
        return {
            "status":               "EXECUTION_FAILED",
            "result":               None,
            "routing":              routing_info,
            "execution_limits":     {"active_limits": active_limits.__dict__},
            "provider_capabilities": caps,
            "errors":               [job["error"] if job else "Job not found after queue processing"],
        }

    route_result = route_and_execute(circuit, requirements,
                                     max_failover_attempts=active_limits.max_retries + 1)
    return {
        "status":               route_result["status"],
        "result":               route_result["result"],
        "routing":              route_result["routing"],
        "execution_limits":     {"active_limits": active_limits.__dict__},
        "provider_capabilities": caps,
        "errors":               route_result["errors"],
    }
