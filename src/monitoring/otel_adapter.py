# src/monitoring/otel_adapter.py
# OpenTelemetry-style adapter — stdlib only, no opentelemetry-sdk dependency.
# Provides OTel-compatible span and metric structures for external consumers.

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OtelSpan:
    trace_id:    str
    span_id:     str
    name:        str
    status:      str        # STATUS_CODE_OK | STATUS_CODE_ERROR
    duration_ns: int
    attributes:  Dict[str, Any] = field(default_factory=dict)
    events:      List[dict]     = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "trace_id":    self.trace_id,
            "span_id":     self.span_id,
            "name":        self.name,
            "status":      self.status,
            "duration_ns": self.duration_ns,
            "attributes":  self.attributes,
            "events":      self.events,
        }


@dataclass
class OtelMetric:
    name:        str
    description: str
    unit:        str
    value:       float
    labels:      Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name":        self.name,
            "description": self.description,
            "unit":        self.unit,
            "value":       self.value,
            "labels":      self.labels,
        }


@dataclass
class OtelGauge:
    name:  str
    value: float
    unit:  str
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"name": self.name, "type": "gauge", "value": self.value,
                "unit": self.unit, "labels": self.labels}


class OtelAdapter:
    """
    Converts runtime invocation records into OTel-compatible structures.
    Pure Python — no opentelemetry-sdk required.
    Attach to any monitoring pipeline that accepts OTel-like dicts.
    """

    def invocation_to_span(self, record: dict) -> OtelSpan:
        span = OtelSpan(
            trace_id    = record.get("invocation_id", ""),
            span_id     = record.get("invocation_id", "")[:16],
            name        = f"invoke.{record.get('capability_id', 'unknown')}",
            status      = "STATUS_CODE_OK" if record.get("status") == "SUCCESS"
                          else "STATUS_CODE_ERROR",
            duration_ns = int(record.get("duration_ms", 0) * 1_000_000),
            attributes  = {
                "capability.id":     record.get("capability_id"),
                "invocation.seq":    record.get("seq"),
                "invocation.status": record.get("status"),
                "payload.hash":      record.get("payload_hash", ""),
                "output.hash":       record.get("output_hash", ""),
            },
        )
        if record.get("error"):
            span.events.append(
                {"name": "exception", "attributes": {"message": record["error"]}}
            )
        return span

    def metrics_to_otel(self, capability_metrics: dict) -> List[OtelMetric]:
        out = []
        for cid, m in capability_metrics.items():
            labels = {"capability_id": cid}
            out += [
                OtelMetric("marine.runtime.invocations.total",
                           "Total capability invocations", "1",
                           float(m.get("total_invocations", 0)), labels),
                OtelMetric("marine.runtime.success.total",
                           "Total successful invocations", "1",
                           float(m.get("success_count", 0)), labels),
                OtelMetric("marine.runtime.failures.total",
                           "Total failed invocations", "1",
                           float(m.get("failure_count", 0)), labels),
                OtelMetric("marine.runtime.latency.avg_ms",
                           "Average latency ms", "ms",
                           float(m.get("avg_latency_ms", 0.0)), labels),
                OtelMetric("marine.runtime.latency.max_ms",
                           "Max latency ms", "ms",
                           float(m.get("max_latency_ms", 0.0)), labels),
            ]
        return out

    def export(self, invocation_records: List[dict], capability_metrics: dict) -> dict:
        spans   = [self.invocation_to_span(r).to_dict() for r in invocation_records]
        metrics = [m.to_dict() for m in self.metrics_to_otel(capability_metrics)]
        return {
            "format":  "otel_compatible_v1",
            "spans":   spans,
            "metrics": metrics,
        }

    def export_runtime_health_gauge(self, health: dict) -> List[OtelGauge]:
        gauges = []
        cap_health = health.get("capability_health", {})
        health_map = {"HEALTHY": 1.0, "IDLE": 0.5, "DEGRADED": 0.25, "UNHEALTHY": 0.0}
        for cid, h in cap_health.items():
            gauges.append(OtelGauge(
                name="marine.runtime.capability.health",
                value=health_map.get(h, 0.0),
                unit="1",
                labels={"capability_id": cid, "health_status": h},
            ))
        return gauges


# ── Module-level singleton ─────────────────────────────────────────────────────
_ADAPTER = OtelAdapter()


def invocation_to_span(record: dict) -> dict:
    return _ADAPTER.invocation_to_span(record).to_dict()


def export(invocation_records: List[dict], capability_metrics: dict) -> dict:
    return _ADAPTER.export(invocation_records, capability_metrics)


def export_health_gauges(health: dict) -> List[dict]:
    return [g.to_dict() for g in _ADAPTER.export_runtime_health_gauge(health)]
