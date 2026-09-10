# src/quantum/providers/provider_registry.py
# Provider Registry — backend negotiation, capability negotiation, health, discovery.
#
# This is the central proof point for Phase 1: "No runtime changes required
# when adding a new provider." Any object implementing QuantumExecutionProvider
# can be registered here at runtime. The router (quantum_execution_router.py)
# and everything downstream of it never imports a specific provider's SDK —
# it only calls through this registry.

from typing import Dict, List, Optional

from src.quantum.providers.base import (
    QuantumExecutionProvider, QuantumExecutionBackend, BackendRequirements,
)


class ProviderRegistrationError(Exception):
    pass


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, QuantumExecutionProvider] = {}
        self._seq: int = 0

    def register_provider(self, provider: QuantumExecutionProvider) -> None:
        if provider.provider_name in self._providers:
            raise ProviderRegistrationError(
                f"Provider '{provider.provider_name}' already registered."
            )
        self._providers[provider.provider_name] = provider

    def deregister_provider(self, provider_name: str) -> None:
        if provider_name not in self._providers:
            raise ProviderRegistrationError(f"Provider '{provider_name}' not registered.")
        del self._providers[provider_name]

    def list_providers(self) -> List[str]:
        return sorted(self._providers.keys())

    def get_provider(self, provider_name: str) -> Optional[QuantumExecutionProvider]:
        return self._providers.get(provider_name)

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    # ── Backend negotiation ──────────────────────────────────────────────────

    def negotiate_backend(
        self, requirements: BackendRequirements
    ) -> Optional[QuantumExecutionBackend]:
        """
        Find a backend across ALL registered providers satisfying requirements.
        If requirements.preferred_provider is set, try that provider first.
        Falls through to any other provider that satisfies requirements.
        """
        if requirements.preferred_provider:
            provider = self._providers.get(requirements.preferred_provider)
            if provider:
                backend = provider.negotiate(requirements)
                if backend:
                    return backend
        for provider in self._providers.values():
            backend = provider.negotiate(requirements)
            if backend:
                return backend
        return None

    def negotiate_with_health(
        self, requirements: BackendRequirements
    ) -> dict:
        """
        Negotiate a backend AND confirm it's actually healthy.
        Tries providers in order; skips any reporting non-AVAILABLE health.
        Returns {backend, provider_name, health, attempted} for full auditability.
        """
        attempted = []
        candidates = []
        if requirements.preferred_provider:
            p = self._providers.get(requirements.preferred_provider)
            if p:
                candidates.append(p)
        candidates += [p for p in self._providers.values() if p not in candidates]

        for provider in candidates:
            backend = provider.negotiate(requirements)
            if not backend:
                attempted.append({"provider": provider.provider_name, "result": "NO_CAPABLE_BACKEND"})
                continue
            health = backend.health(self._next_seq())
            attempted.append({
                "provider": provider.provider_name, "backend": backend.name,
                "result": health.status.value,
            })
            if health.status.value == "AVAILABLE":
                return {
                    "backend":       backend,
                    "provider_name": provider.provider_name,
                    "health":        health.to_dict(),
                    "attempted":     attempted,
                }
        return {"backend": None, "provider_name": None, "health": None, "attempted": attempted}

    # ── Health ────────────────────────────────────────────────────────────────

    def backend_health(self) -> List[dict]:
        results = []
        for provider in self._providers.values():
            for backend in provider.list_backends():
                results.append(backend.health(self._next_seq()).to_dict())
        return results

    def provider_health_summary(self) -> dict:
        health = self.backend_health()
        by_provider: Dict[str, dict] = {}
        for h in health:
            pname = h["provider_name"]
            if pname not in by_provider:
                by_provider[pname] = {"available": 0, "unavailable": 0, "total": 0}
            by_provider[pname]["total"] += 1
            if h["status"] == "AVAILABLE":
                by_provider[pname]["available"] += 1
            else:
                by_provider[pname]["unavailable"] += 1
        return by_provider

    # ── Discovery ─────────────────────────────────────────────────────────────

    def backend_discovery(self) -> dict:
        return {
            provider_name: provider.discover()
            for provider_name, provider in self._providers.items()
        }


# ── Module-level singleton, pre-registered with all 4 providers ───────────────

_REGISTRY = ProviderRegistry()


def _bootstrap() -> None:
    from src.quantum.providers.local_simulator_provider import LocalSimulatorProvider
    from src.quantum.providers.aer_provider import AerProvider
    from src.quantum.providers.ibm_runtime_provider import IBMRuntimeProvider
    from src.quantum.providers.ionq_provider import IonQProvider

    _REGISTRY.register_provider(LocalSimulatorProvider())
    _REGISTRY.register_provider(AerProvider())
    _REGISTRY.register_provider(IBMRuntimeProvider())
    _REGISTRY.register_provider(IonQProvider())


_bootstrap()


def register_provider(provider: QuantumExecutionProvider) -> None:
    _REGISTRY.register_provider(provider)


def deregister_provider(provider_name: str) -> None:
    _REGISTRY.deregister_provider(provider_name)


def list_providers() -> List[str]:
    return _REGISTRY.list_providers()


def get_provider(provider_name: str) -> Optional[QuantumExecutionProvider]:
    return _REGISTRY.get_provider(provider_name)


def negotiate_backend(requirements: BackendRequirements) -> Optional[QuantumExecutionBackend]:
    return _REGISTRY.negotiate_backend(requirements)


def negotiate_with_health(requirements: BackendRequirements) -> dict:
    return _REGISTRY.negotiate_with_health(requirements)


def backend_health() -> List[dict]:
    return _REGISTRY.backend_health()


def provider_health_summary() -> dict:
    return _REGISTRY.provider_health_summary()


def backend_discovery() -> dict:
    return _REGISTRY.backend_discovery()
