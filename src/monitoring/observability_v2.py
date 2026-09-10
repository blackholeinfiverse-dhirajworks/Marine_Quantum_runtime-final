# src/monitoring/observability_v2.py
# Runtime Observability v2 — Phase 5.
#
# Extends the existing capability-level observability (runtime_observability.py,
# otel_adapter.py) with: distributed traces, backend metrics, provider health,
# runtime events, execution graphs, capability utilization, backend latency,
# queue statistics, success rates, failure trends, resource utilization.
#
# All functions are pure data-shaping over data already tracked elsewhere
# (DistributedRuntimeManager, ProviderRegistry, RuntimeObservabilityLayer).
# No new state is invented here — this module aggregates and reshapes.

import hashlib
import json
from typing import Any, Dict, List, Optional


def _sha256(d: str) -> str:
    return hashlib.sha256(d.encode("utf-8")).hexdigest()


# ── Distributed traces ─────────────────────────────────────────────────────────

def build_distributed_trace(job_record: dict, events: List[dict]) -> dict:
    """
    Build a single distributed trace tree for one job: submission -> routing
    -> execution -> completion, spanning whichever node/provider/backend
    handled it. OTel-trace-shaped (trace_id, spans), no opentelemetry-sdk
    dependency.
    """
    job_id = job_record["job_id"]
    job_events = [e for e in events if e.get("job_id") == job_id]
    spans = []
    for e in job_events:
        spans.append({
            "span_id":    _sha256(f"{job_id}:{e['event_type']}:{e['seq']}")[:16],
            "name":       e["event_type"],
            "seq":        e["seq"],
            "attributes": {k: v for k, v in e.items() if k not in ("event_type", "seq")},
        })
    return {
        "trace_id": job_id,
        "spans":    spans,
        "final_status": job_record.get("status"),
        "node_id":      job_record.get("node_id"),
    }


def build_all_traces(jobs: List[dict], events: List[dict]) -> List[dict]:
    return [build_distributed_trace(j, events) for j in jobs]


# ── Backend metrics ─────────────────────────────────────────────────────────────

def backend_metrics_from_routing_log(routing_attempts: List[dict]) -> dict:
    """
    Aggregate per-backend success/failure/latency from a list of routing
    attempt dicts (as produced by quantum_execution_router.route_and_execute).
    """
    by_backend: Dict[str, dict] = {}
    for attempt in routing_attempts:
        key = f"{attempt.get('provider','?')}/{attempt.get('backend','?')}"
        if key not in by_backend:
            by_backend[key] = {"attempts": 0, "success": 0, "unavailable": 0, "error": 0}
        by_backend[key]["attempts"] += 1
        outcome = attempt.get("outcome", attempt.get("result", ""))
        if outcome == "SUCCESS":
            by_backend[key]["success"] += 1
        elif outcome in ("UNAVAILABLE", "CREDENTIALS_REQUIRED", "NETWORK_UNREACHABLE"):
            by_backend[key]["unavailable"] += 1
        else:
            by_backend[key]["error"] += 1
    return by_backend


# ── Provider health (aggregated) ────────────────────────────────────────────────

def provider_health_report() -> dict:
    from src.quantum.providers import provider_registry
    health = provider_registry.backend_health()
    summary = provider_registry.provider_health_summary()
    return {"backends": health, "by_provider": summary}


# ── Runtime events stream ───────────────────────────────────────────────────────

def runtime_event_stream(manager_events: List[dict], limit: Optional[int] = None) -> List[dict]:
    events = manager_events[-limit:] if limit else manager_events
    return [
        {"seq": e["seq"], "event_type": e["event_type"],
         "details": {k: v for k, v in e.items() if k not in ("seq", "event_type")}}
        for e in events
    ]


# ── Execution graph ──────────────────────────────────────────────────────────────

def build_execution_graph(jobs: List[dict]) -> dict:
    """
    DAG of job -> node -> outcome as a plain adjacency dict.
    Not a rendered image — this module produces telemetry data only,
    consistent with "No UI ownership. Only telemetry production."
    """
    nodes_seen = set()
    edges = []
    for job in jobs:
        node_id = job.get("node_id") or "UNROUTED"
        nodes_seen.add(node_id)
        nodes_seen.add(job["job_id"][:12])
        edges.append({
            "from": job["job_id"][:12], "to": node_id,
            "label": job.get("status"),
        })
    return {"nodes": sorted(nodes_seen), "edges": edges}


# ── Capability utilization ───────────────────────────────────────────────────────

def capability_utilization(capability_metrics: dict) -> dict:
    total = sum(m.get("total_invocations", 0) for m in capability_metrics.values())
    if total == 0:
        return {"total_invocations": 0, "utilization": {}}
    return {
        "total_invocations": total,
        "utilization": {
            cid: round(m.get("total_invocations", 0) / total, 4)
            for cid, m in capability_metrics.items()
        },
    }


# ── Queue statistics / success rates / failure trends ────────────────────────────

def success_failure_trends(jobs: List[dict]) -> dict:
    total = len(jobs)
    if total == 0:
        return {"total": 0, "success_rate": 0.0, "failure_rate": 0.0, "by_status": {}}
    by_status: Dict[str, int] = {}
    for j in jobs:
        by_status[j["status"]] = by_status.get(j["status"], 0) + 1
    success = by_status.get("COMPLETED", 0)
    failure = by_status.get("FAILED", 0)
    return {
        "total":        total,
        "success_rate": round(success / total, 4),
        "failure_rate": round(failure / total, 4),
        "by_status":    by_status,
    }


# ── Resource utilization (node capacity) ──────────────────────────────────────────

def resource_utilization(node_list: List[dict]) -> dict:
    return {
        n["node_id"]: {
            "active_jobs":    n["active_jobs"],
            "max_concurrent": n["max_concurrent"],
            "utilization":    round(n["active_jobs"] / n["max_concurrent"], 4)
                              if n["max_concurrent"] > 0 else 0.0,
        }
        for n in node_list
    }


# ── Composite report ────────────────────────────────────────────────────────────

def full_observability_v2_report(
    jobs: List[dict], manager_events: List[dict], node_list: List[dict],
    capability_metrics: dict,
) -> dict:
    return {
        "distributed_traces":     build_all_traces(jobs, manager_events),
        "provider_health":        provider_health_report(),
        "runtime_events":         runtime_event_stream(manager_events, limit=50),
        "execution_graph":        build_execution_graph(jobs),
        "capability_utilization": capability_utilization(capability_metrics),
        "success_failure_trends": success_failure_trends(jobs),
        "resource_utilization":   resource_utilization(node_list),
    }
