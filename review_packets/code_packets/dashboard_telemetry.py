# src/monitoring/dashboard_telemetry.py
# Ecosystem Dashboard Telemetry — Phase 6.
#
# "No UI ownership. Only telemetry production."
#
# Six named functions, one per dashboard named in the brief. Each returns a
# JSON-serialisable dict scoped to what that dashboard needs. None of these
# render anything. This module is intentionally thin — it reshapes data that
# already exists in capability_runtime, observability_v2, and provider_registry
# into the specific slices each downstream dashboard consumer would want.

from typing import Any, Dict, List, Optional


def replay_dashboard_telemetry(replay_authority_stats: dict, recent_decisions: List[dict]) -> dict:
    """For the Replay Dashboard — owned by Pritesh's replay authority team."""
    return {
        "dashboard": "REPLAY",
        "statistics": replay_authority_stats,
        "recent_decisions": recent_decisions[-20:],
    }


def runtime_dashboard_telemetry(runtime_health: dict, active_capabilities: List[dict]) -> dict:
    """For the general Runtime Dashboard — capability-level health and activity."""
    return {
        "dashboard": "RUNTIME",
        "health": runtime_health,
        "active_capabilities": active_capabilities,
    }


def quantum_dashboard_telemetry(provider_health: dict, backend_discovery: dict, recent_jobs: List[dict]) -> dict:
    """For the Quantum Dashboard — provider/backend status and recent quantum jobs."""
    return {
        "dashboard": "QUANTUM",
        "provider_health": provider_health,
        "backend_discovery": backend_discovery,
        "recent_jobs": recent_jobs[-20:],
    }


def operations_dashboard_telemetry(
    queue_statistics: dict, resource_utilization: dict, success_failure_trends: dict
) -> dict:
    """For the Operations Dashboard — queue depth, node load, success/failure rates."""
    return {
        "dashboard": "OPERATIONS",
        "queue_statistics": queue_statistics,
        "resource_utilization": resource_utilization,
        "success_failure_trends": success_failure_trends,
    }


def health_dashboard_telemetry(runtime_heartbeat: dict, capability_health: dict, provider_health: dict) -> dict:
    """For the Health Dashboard — aggregated liveness across capabilities and providers."""
    return {
        "dashboard": "HEALTH",
        "runtime_heartbeat": runtime_heartbeat,
        "capability_health": capability_health,
        "provider_health": provider_health,
    }


def governance_dashboard_telemetry(
    decision_ledger_summary: dict, doctrine_results: dict, authority_audit_log: List[dict]
) -> dict:
    """For the Governance Dashboard — owned by Raj's governance team. This runtime
    only produces the telemetry; it does not interpret or act on governance decisions."""
    return {
        "dashboard": "GOVERNANCE",
        "decision_ledger": decision_ledger_summary,
        "doctrine_results": doctrine_results,
        "recent_authority_checks": authority_audit_log[-20:],
    }


def all_dashboard_telemetry(**kwargs) -> Dict[str, dict]:
    """
    Convenience aggregator. Pass through whatever sub-payloads are available;
    dashboards not provided data simply get an empty/partial payload rather
    than raising — telemetry production should never crash the runtime.
    """
    out = {}
    try:
        out["replay"] = replay_dashboard_telemetry(
            kwargs.get("replay_authority_stats", {}), kwargs.get("recent_decisions", []))
    except Exception as exc:
        out["replay"] = {"error": str(exc)}
    try:
        out["runtime"] = runtime_dashboard_telemetry(
            kwargs.get("runtime_health", {}), kwargs.get("active_capabilities", []))
    except Exception as exc:
        out["runtime"] = {"error": str(exc)}
    try:
        out["quantum"] = quantum_dashboard_telemetry(
            kwargs.get("provider_health", {}), kwargs.get("backend_discovery", {}),
            kwargs.get("recent_jobs", []))
    except Exception as exc:
        out["quantum"] = {"error": str(exc)}
    try:
        out["operations"] = operations_dashboard_telemetry(
            kwargs.get("queue_statistics", {}), kwargs.get("resource_utilization", {}),
            kwargs.get("success_failure_trends", {}))
    except Exception as exc:
        out["operations"] = {"error": str(exc)}
    try:
        out["health"] = health_dashboard_telemetry(
            kwargs.get("runtime_heartbeat", {}), kwargs.get("capability_health", {}),
            kwargs.get("provider_health", {}))
    except Exception as exc:
        out["health"] = {"error": str(exc)}
    try:
        out["governance"] = governance_dashboard_telemetry(
            kwargs.get("decision_ledger_summary", {}), kwargs.get("doctrine_results", {}),
            kwargs.get("authority_audit_log", []))
    except Exception as exc:
        out["governance"] = {"error": str(exc)}
    return out
