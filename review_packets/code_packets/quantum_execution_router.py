# src/quantum/providers/quantum_execution_router.py
# Quantum Execution Router — Phase 4: identical execution surface regardless
# of backend. Single entry point. Handles negotiation + automatic failover.
#
# This is what the rest of the runtime calls. It never imports a specific
# provider's SDK. Adding a 5th provider requires zero changes to this file.

import time
from typing import List, Optional

from src.quantum.providers.base import (
    BackendRequirements, CircuitSpec, ExecutionResult, ProviderUnavailableError,
)
from src.quantum.providers import provider_registry


class RoutingFailure(Exception):
    """Raised when no registered provider can satisfy the requirements."""
    pass


def route_and_execute(
    circuit: CircuitSpec,
    requirements: Optional[BackendRequirements] = None,
    max_failover_attempts: int = 3,
) -> dict:
    """
    Negotiate a healthy backend and execute the circuit on it.
    On ProviderUnavailableError, automatically fails over to the next
    candidate provider up to max_failover_attempts times.

    Returns a dict with:
        status:    SUCCESS | ROUTING_FAILED | EXECUTION_FAILED
        result:    ExecutionResult.to_dict() or None
        routing:   {attempted providers, final provider/backend chosen}
        errors:    list of strings
    """
    requirements = requirements or BackendRequirements(min_qubits=circuit.num_qubits, min_shots=circuit.shots)
    attempts  = []
    errors    = []

    negotiation = provider_registry.negotiate_with_health(requirements)
    candidates  = negotiation["attempted"]

    # Re-derive an ordered candidate backend list (preferred first, then all others)
    # so failover can try the next one if execute() raises.
    all_providers = []
    if requirements.preferred_provider:
        p = provider_registry.get_provider(requirements.preferred_provider)
        if p:
            all_providers.append(p)
    all_providers += [
        provider_registry.get_provider(name)
        for name in provider_registry.list_providers()
        if provider_registry.get_provider(name) not in all_providers
    ]

    tried = 0
    for provider in all_providers:
        if tried >= max_failover_attempts:
            break
        backend = provider.negotiate(requirements)
        if not backend:
            attempts.append({"provider": provider.provider_name, "outcome": "NO_CAPABLE_BACKEND"})
            continue
        tried += 1
        try:
            result = backend.execute(circuit)
            attempts.append({
                "provider": provider.provider_name, "backend": backend.name,
                "outcome": "SUCCESS",
            })
            return {
                "status":  "SUCCESS",
                "result":  result.to_dict(),
                "routing": {"attempted": attempts, "final_provider": provider.provider_name,
                           "final_backend": backend.name, "failover_count": tried - 1},
                "errors":  [],
            }
        except ProviderUnavailableError as exc:
            attempts.append({
                "provider": provider.provider_name, "backend": backend.name,
                "outcome": "UNAVAILABLE", "reason": str(exc),
            })
            errors.append(f"{provider.provider_name}/{backend.name}: {exc}")
            continue
        except Exception as exc:
            attempts.append({
                "provider": provider.provider_name, "backend": backend.name,
                "outcome": "EXECUTION_ERROR", "reason": str(exc),
            })
            errors.append(f"{provider.provider_name}/{backend.name}: {exc}")
            return {
                "status":  "EXECUTION_FAILED",
                "result":  None,
                "routing": {"attempted": attempts, "final_provider": None,
                           "final_backend": None, "failover_count": tried - 1},
                "errors":  errors,
            }

    return {
        "status":  "ROUTING_FAILED",
        "result":  None,
        "routing": {"attempted": attempts, "final_provider": None,
                   "final_backend": None, "failover_count": tried},
        "errors":  errors or ["No provider could satisfy requirements"],
    }
