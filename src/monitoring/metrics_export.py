# src/monitoring/metrics_export.py
# Metrics Export — structured output for external consumption.
# No external dependencies. Exports to dict (JSON-serialisable),
# Prometheus text format, and OpenTelemetry-compatible span dicts.

import json
import os
from typing import Dict, List


def export_to_dict(metrics: dict) -> dict:
    """Export runtime metrics to a JSON-serialisable dict."""
    return {"format": "marine_quantum_runtime_metrics_v1", "metrics": metrics}


def export_to_jsonl(metrics_records: List[dict], path: str) -> dict:
    """
    Append a list of metric records to a JSONL file.
    Returns {written, path, status}.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            for record in metrics_records:
                f.write(json.dumps(record, separators=(",", ":")) + "\n")
        return {"written": len(metrics_records), "path": path, "status": "OK"}
    except OSError as exc:
        return {"written": 0, "path": path, "status": "ERROR", "error": str(exc)}


def format_as_prometheus(metrics: dict, prefix: str = "marine_runtime") -> str:
    """
    Format capability metrics as Prometheus text exposition format.
    Pure string formatting — no prometheus_client dependency.
    """
    lines = []
    cap_metrics = metrics.get("capability_metrics", {})
    for cid, m in cap_metrics.items():
        safe = cid.replace("-", "_").replace(".", "_")
        lines += [
            f"# HELP {prefix}_{safe}_invocations_total Total invocations",
            f"# TYPE {prefix}_{safe}_invocations_total counter",
            f'{prefix}_{safe}_invocations_total {m.get("total_invocations", 0)}',
            f"# HELP {prefix}_{safe}_success_total Successful invocations",
            f"# TYPE {prefix}_{safe}_success_total counter",
            f'{prefix}_{safe}_success_total {m.get("success_count", 0)}',
            f"# HELP {prefix}_{safe}_failures_total Failed invocations",
            f"# TYPE {prefix}_{safe}_failures_total counter",
            f'{prefix}_{safe}_failures_total {m.get("failure_count", 0)}',
            f"# HELP {prefix}_{safe}_latency_ms_avg Average latency ms",
            f"# TYPE {prefix}_{safe}_latency_ms_avg gauge",
            f'{prefix}_{safe}_latency_ms_avg {m.get("avg_latency_ms", 0.0)}',
            f"# HELP {prefix}_{safe}_latency_ms_max Max latency ms",
            f"# TYPE {prefix}_{safe}_latency_ms_max gauge",
            f'{prefix}_{safe}_latency_ms_max {m.get("max_latency_ms", 0.0)}',
        ]
    return "\n".join(lines)


def format_as_otel_spans(invocation_records: List[dict]) -> List[dict]:
    """
    Format invocation records as OpenTelemetry-compatible span dicts.
    Pure Python — no opentelemetry-sdk dependency.
    """
    spans = []
    for rec in invocation_records:
        span = {
            "trace_id":    rec.get("invocation_id", ""),
            "span_id":     rec.get("invocation_id", "")[:16],
            "name":        f"invoke.{rec.get('capability_id', 'unknown')}",
            "kind":        "SPAN_KIND_SERVER",
            "start_time":  rec.get("seq", 0) * 60_000_000_000,
            "duration_ns": int(rec.get("duration_ms", 0) * 1_000_000),
            "status":      "STATUS_CODE_OK" if rec.get("status") == "SUCCESS"
                           else "STATUS_CODE_ERROR",
            "attributes": {
                "capability.id":     rec.get("capability_id"),
                "invocation.seq":    rec.get("seq"),
                "invocation.status": rec.get("status"),
                "payload.hash":      rec.get("payload_hash", ""),
                "output.hash":       rec.get("output_hash", ""),
            },
        }
        if rec.get("error"):
            span["events"] = [
                {"name": "exception", "attributes": {"message": rec["error"]}}
            ]
        spans.append(span)
    return spans
