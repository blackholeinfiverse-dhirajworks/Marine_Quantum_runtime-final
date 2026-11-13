#!/usr/bin/env python3
"""
api_server.py — Marine Quantum Runtime REST API Wrapper
========================================================
Exposes the Python runtime as HTTP endpoints via FastAPI.

INSTALL:
    pip install fastapi uvicorn pydantic

RUN (development):
    uvicorn api_server:app --reload --port 8000

RUN (production):
    uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 4

DOCS (auto-generated Swagger):
    http://localhost:8000/docs
    http://localhost:8000/redoc

ENVIRONMENT VARIABLES:
    RUNTIME_API_KEY     — Required. API key for X-API-Key header auth.
                          Set to a long random string in production.
    IBM_QUANTUM_TOKEN   — Optional. Enables IBM Quantum backend.
    IONQ_API_KEY        — Optional. Enables IonQ backend.
    LOG_LEVEL           — Optional. debug|info|warning. Default: info.

QCG INTEGRATION (trace IDs & instrumentation):
    - Send  X-Trace-ID: <id>  (1-128 chars: letters, digits, . _ : -).
      If omitted, the server generates a UUID4. The effective trace ID is
      echoed in the X-Trace-ID response header, in every JSON body
      (success AND error) and in every log line.
    - Extra endpoints: GET /api/v1/quantum/backend
                       GET /api/v1/quantum/calibration
    - Backend classification: SIMULATED AND TESTED (Qiskit AerSimulator).
      Physical QPU execution has NOT been verified.

QCG COMPATIBILITY ADAPTER (QCG itself is never modified):
    POST /hybrid/submit    — QCG HybridSubmitRequest  -> QCG InvocationResult
    POST /hybrid/dispatch  — QCG CapabilityDispatchRequest -> QCG InvocationResult
    Optional env: QCG_ADAPTER_TIMEOUT_SECONDS (default 25; reports status TIMEOUT)
                  QCG_ADAPTER_MAX_WORKERS     (default 4)
    See docs/QCG_INTEGRATION.md.

ARCHITECTURE NOTE:
    This file is a thin HTTP transport layer over the Python runtime.
    All business logic stays inside src/. This file only handles:
        - HTTP request/response serialization
        - Authentication middleware
        - Error mapping to HTTP status codes
    Do not add business logic here.
"""

import os
import sys
import json
import math
import re
import time
import hashlib
import concurrent.futures
import uuid
import logging
import secrets
import threading
import contextvars
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Make the runtime importable regardless of working directory
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from fastapi import FastAPI, HTTPException, Depends, Security, Request, status
    from fastapi.security import APIKeyHeader
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from fastapi.encoders import jsonable_encoder
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from pydantic import BaseModel, Field, ValidationError
    import uvicorn
except ImportError:
    print("ERROR: FastAPI not installed.")
    print("Run: pip install fastapi uvicorn pydantic")
    sys.exit(1)

# ── Runtime imports ────────────────────────────────────────────────────────────

from invoke_runtime import invoke_runtime
from src.runtime.capability_runtime import (
    invoke_capability,
    get_dashboard_json,
    get_active_capabilities,
    get_replay_statistics,
    get_provenance_status,
)
from src.quantum.providers import provider_registry
from src.quantum.production_runtime import (
    production_execute, queue_status, provider_capabilities,
    get_noise_profile, get_hardware_constraints, ExecutionLimits,
)
from src.quantum.providers.base import BackendRequirements, CircuitSpec
from src.governance.authority_matrix import matrix_snapshot, audit_log
from src.governance.decision_ledger import summary as ledger_summary
from src.governance.doctrine_registry import evaluate_all as evaluate_doctrines
from src.monitoring.observability_v2 import provider_health_report


LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

if LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    LOG_LEVEL = "INFO"


# ── Trace-ID plumbing ──────────────────────────────────────────────────────────
# The trace ID lives in a ContextVar so concurrent requests never share one
# (each request has its own context; sync endpoints run in a copied context).
# A LogRecord factory stamps every log line with the active trace ID, so logs
# emitted anywhere (including src/) carry it without touching that code.

_TRACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]{0,127}$")
_trace_ctx: "contextvars.ContextVar[Optional[str]]" = contextvars.ContextVar(
    "trace_id", default=None
)


def _new_trace_id() -> str:
    return str(uuid.uuid4())


_base_record_factory = logging.getLogRecordFactory()


def _record_factory(*args, **kwargs):
    record = _base_record_factory(*args, **kwargs)
    record.trace_id = _trace_ctx.get() or "-"
    return record


logging.setLogRecordFactory(_record_factory)
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s [trace_id=%(trace_id)s] %(name)s: %(message)s",
)
logger = logging.getLogger("marine_quantum_runtime")


# ── App configuration ──────────────────────────────────────────────────────────

app = FastAPI(
    title="Marine Quantum Runtime API",
    version="1.0.0",
    description=(
        "Sovereign Quantum Runtime Capability — BHIV Ecosystem\n\n"
        "**Integration quick-start:** See `/docs` for Swagger UI or "
        "`/openapi.json` for the machine-readable spec.\n\n"
        "**Auth:** Pass your API key as `X-API-Key` header."
    ),
    contact={
        "name": "Dhiraj Chavan",
        "url": "https://github.com/dhirajchavan-works/Marine-quantum-runtime",
    },
    license_info={"name": "Internal — BHIV Core"},
)

# Trace-ID middleware. Registered BEFORE CORSMiddleware so CORS stays the
# outermost layer and its headers apply to every response, including the 400
# returned for a malformed trace ID.

@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    supplied = request.headers.get("X-Trace-ID")
    if supplied is not None and supplied.strip():
        supplied = supplied.strip()
        if not _TRACE_ID_RE.match(supplied):
            tid = _new_trace_id()
            # Log only the length of the rejected value (avoids log injection).
            logger.warning(
                "Rejected malformed X-Trace-ID (len=%d); issued trace_id=%s",
                len(supplied), tid,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "status": "INVALID_TRACE_ID",
                    "trace_id": tid,
                    "detail": (
                        "X-Trace-ID must be 1-128 characters: letters, digits, "
                        "'.', '_', ':' or '-', starting with a letter or digit."
                    ),
                },
                headers={"X-Trace-ID": tid},
            )
        tid = supplied
    else:
        tid = _new_trace_id()

    request.state.trace_id = tid
    token = _trace_ctx.set(tid)
    try:
        response = await call_next(request)
    finally:
        _trace_ctx.reset(token)
    # An endpoint may adopt a better trace identity (QCG invocation_id).
    tid = getattr(request.state, "trace_id", tid)
    response.headers["X-Trace-ID"] = tid
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Trace-ID"],
)


# ── Auth ───────────────────────────────────────────────────────────────────────
#
# Uses fastapi.security.APIKeyHeader (not a plain Header()+Depends()) so that
# FastAPI registers a real OpenAPI `securitySchemes` entry and attaches it to
# every protected operation. That's what makes Swagger UI show the
# "Authorize" button and auto-attach X-API-Key to requests after the user
# authorizes once — a plain Header() parameter is invisible to the OpenAPI
# security model even though it works fine at the HTTP level.

_RUNTIME_API_KEY = os.environ.get("RUNTIME_API_KEY")
if not _RUNTIME_API_KEY:
    logger.warning(
        "RUNTIME_API_KEY not set — the server will reject all authenticated "
        "requests with 500 until this environment variable is configured. "
        "Set a real, random key before any production deployment."
    )

_api_key_scheme = APIKeyHeader(
    name="X-API-Key",
    scheme_name="APIKeyHeader",
    description="API key issued for this deployment. Required on all protected endpoints.",
    auto_error=False,  # let verify_api_key control the exact error response/body
)


def verify_api_key(api_key: Optional[str] = Security(_api_key_scheme)) -> str:
    if not _RUNTIME_API_KEY:
        # Fail closed: never silently accept requests when the server itself
        # has no configured key. This is a deployment misconfiguration, not
        # a client error, so it's reported as 500, not 401.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API authentication is not configured",
        )
    if not api_key or not secrets.compare_digest(api_key, _RUNTIME_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key


Auth = Security(verify_api_key)


# ── Limits & backend identity (single source of truth) ────────────────────────

MAX_QUBITS    = 29
MIN_SHOTS     = 100
MAX_SHOTS     = 100_000
DEFAULT_SHOTS = 4096
DEFAULT_SEED  = 42

# What has actually been verified for this deployment. Do NOT change these
# unless a different backend has been executed and verified end-to-end.
VERIFIED_PROVIDER      = "aer"
VERIFIED_BACKEND       = "aer_simulator"
BACKEND_CLASSIFICATION = "SIMULATED AND TESTED"


# ── Request / Response Models ──────────────────────────────────────────────────

class SignalPayload(BaseModel):
    node_id:      str   = Field(..., description="Quantum node identifier, non-empty")
    energy_delta: float = Field(..., ge=0.0, description="Energy delta ≥ 0.0")
    iterations:   int   = Field(..., ge=0, description="Iteration count ≥ 0")
    confidence:   float = Field(..., ge=0.0, le=1.0, description="Confidence in [0.0, 1.0]")
    variance:     float = Field(..., ge=0.0, description="Variance ≥ 0.0")

    class Config:
        json_schema_extra = {
            "example": {
                "node_id": "qnode_01", "energy_delta": 0.0001,
                "iterations": 120, "confidence": 0.92, "variance": 0.002,
            }
        }


class QuantumPipelinePayload(BaseModel):
    salinity:                    float = Field(..., ge=0.0,  le=50.0)
    temperature_celsius:         float = Field(..., ge=-5.0, le=45.0)
    pH:                          float = Field(..., ge=0.0,  le=14.0)
    material_oxidation_potential: float = Field(..., ge=-2.0, le=2.0)
    dissolved_oxygen_mgl:        float = Field(..., ge=0.0,  le=20.0)
    current_density_mAcm2:       float = Field(..., ge=0.0,  le=10.0)

    class Config:
        json_schema_extra = {
            "example": {
                "salinity": 35.2, "temperature_celsius": 18.5, "pH": 7.8,
                "material_oxidation_potential": 0.44, "dissolved_oxygen_mgl": 6.5,
                "current_density_mAcm2": 0.12,
            }
        }


class CircuitExecuteRequest(BaseModel):
    num_qubits:    int               = Field(..., ge=1, le=MAX_QUBITS)
    gate_sequence: List[Dict[str, Any]]
    shots:         int               = Field(DEFAULT_SHOTS, ge=MIN_SHOTS, le=MAX_SHOTS)
    seed:          int               = Field(DEFAULT_SEED)
    preferred_provider: Optional[str]= Field(None, description="aer|local_simulator|ibm_runtime|ionq")
    require_simulator:  bool         = Field(True)
    require_real_hardware: bool      = Field(False)

    class Config:
        json_schema_extra = {
            "example": {
                "num_qubits": 3, "shots": 1024, "seed": 42,
                "gate_sequence": [
                    {"gate": "h",  "qubits": [0]},
                    {"gate": "cx", "qubits": [0, 1]},
                    {"gate": "cx", "qubits": [1, 2]},
                ],
                "require_simulator": True,
            }
        }


class GenericInvokeRequest(BaseModel):
    payload: Dict[str, Any]


class QCGHybridSubmitRequest(BaseModel):
    """QCG POST /hybrid/submit request body (field names/defaults mirror QCG's HybridSubmitRequest)."""
    workload: Dict[str, Any]
    workload_type: str = "GENERAL"
    problem_size: int = Field(0, ge=0)
    is_qubo_compatible: bool = False
    requires_entanglement: bool = False
    requires_live_hardware: bool = False
    classical_fallback_acceptable: bool = True


class QCGCapabilityDispatchRequest(BaseModel):
    """QCG POST /hybrid/dispatch request body (mirrors QCG's CapabilityDispatchRequest)."""
    service_id: str = "QCG-HYBRID-RUNTIME"
    operation: str = "hybrid_submit"
    payload: Dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0.0"
    invocation_id: str = ""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _runtime_status_to_http(status_str: str) -> int:
    return {
        "SUCCESS":              200,
        "VALIDATION_ERROR":     422,
        "DEPENDENCY_ERROR":     409,
        "AUTHORITY_DENIED":     403,
        "REPLAY_DENIED":        409,
        "CAPABILITY_NOT_FOUND": 404,
        "MODULE_NOT_FOUND":     404,
        "LIMIT_EXCEEDED":       422,
        "NO_BACKEND_AVAILABLE": 503,
        "ROUTING_FAILED":       503,
        "EXECUTION_FAILED":     503,
        "FAILED":               500,
    }.get(status_str, 500)


# ── QCG integration helpers ───────────────────────────────────────────────────
# Transport-level only: tracing, structural circuit checks, instrumentation.
# No execution logic lives here — production_execute() stays the only pipeline.

def _trace_id_for(request: Optional[Request]) -> str:
    """Effective trace ID for this request (set by trace_id_middleware)."""
    tid = getattr(getattr(request, "state", None), "trace_id", None)
    return tid or _trace_ctx.get() or _new_trace_id()


def _new_execution_id() -> str:
    return f"EXEC-{uuid.uuid4().hex[:12].upper()}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# Bounded, in-memory, per-process record of recent executions. Resets on
# restart / redeploy. Holds metadata only — never payloads or credentials.
_EXEC_LOG_MAX = 100
_exec_log: "deque[Dict[str, Any]]" = deque(maxlen=_EXEC_LOG_MAX)
_exec_log_lock = threading.Lock()


def _record_execution(record: Dict[str, Any]) -> None:
    with _exec_log_lock:
        _exec_log.append(record)


def _execution_log_snapshot() -> List[Dict[str, Any]]:
    with _exec_log_lock:
        return list(_exec_log)


def _logical_depth(gate_sequence: List[Dict[str, Any]]) -> int:
    """
    Pre-transpilation depth estimate from the gate list (each gate occupies the
    next free layer on all of its qubits). Not the transpiled circuit depth.
    """
    layer: Dict[int, int] = {}
    depth = 0
    for g in gate_sequence:
        qs = g.get("qubits") if isinstance(g, dict) else None
        if not isinstance(qs, list):
            continue
        qs = [q for q in qs if isinstance(q, int) and not isinstance(q, bool)]
        if not qs:
            continue
        d = max(layer.get(q, 0) for q in qs) + 1
        for q in qs:
            layer[q] = d
        depth = max(depth, d)
    return depth


def _validate_circuit(num_qubits: int, gate_sequence: List[Dict[str, Any]]) -> List[str]:
    """
    Structural checks only. Gate NAMES are not whitelisted here — the provider
    layer owns the supported-gate set, and an unsupported gate comes back from
    production_execute() as a structured, trace-tagged error. Extra gate keys
    (e.g. params) are allowed, and a gate with no "qubits" key is passed through
    to the runtime unchanged (keeps existing gate-sequence compatibility).
    """
    problems: List[str] = []
    for i, g in enumerate(gate_sequence):
        name = g.get("gate")
        if not isinstance(name, str) or not name.strip():
            problems.append(f"gate_sequence[{i}]: 'gate' must be a non-empty string")
        if "qubits" not in g:
            continue
        qs = g["qubits"]
        if (not isinstance(qs, list) or not qs
                or any(not isinstance(q, int) or isinstance(q, bool) for q in qs)):
            problems.append(f"gate_sequence[{i}] ({name!r}): 'qubits' must be a non-empty list of integers")
            continue
        bad = [q for q in qs if q < 0 or q >= num_qubits]
        if bad:
            problems.append(
                f"gate_sequence[{i}] ({name!r}): qubit index {bad} out of range "
                f"for num_qubits={num_qubits} (valid: 0..{num_qubits - 1})"
            )
        if len(set(qs)) != len(qs):
            problems.append(f"gate_sequence[{i}] ({name!r}): duplicate qubit index in {qs}")
        if len(problems) >= 20:
            problems.append("... further problems omitted")
            break
    return problems


_NESTED_KEYS = ("result", "execution", "output", "backend_info", "details", "metrics")


def _pick(result: Dict[str, Any], *keys: str, kind: Optional[type] = None) -> Any:
    """First matching value from the result (top level, then common sub-dicts)."""
    containers = [result] + [result[n] for n in _NESTED_KEYS if isinstance(result.get(n), dict)]
    for c in containers:
        for k in keys:
            v = c.get(k)
            if v is None:
                continue
            if kind is None or (isinstance(v, kind) and not (kind is int and isinstance(v, bool))):
                return v
    return None


def _find_key(obj: Any, key: str, _depth: int = 0) -> Any:
    """Locate `key` (as dict key, or as a list item's backend_name) in a nested structure."""
    if _depth > 6:
        return None
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_key(v, key, _depth + 1)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict) and item.get("backend_name") == key:
                return item
            r = _find_key(item, key, _depth + 1)
            if r is not None:
                return r
    return None


def _availability_label(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        for k in ("availability", "status", "health", "state"):
            if isinstance(entry.get(k), str):
                return entry[k]
    return "UNKNOWN"


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"], summary="Liveness check — no auth required")
def health():
    """Returns 200 immediately. Used by load balancer / k8s probes."""
    return {"status": "ok", "runtime": "marine-quantum-runtime", "version": "1.0.0"}


@app.get("/health/providers", tags=["Health"], dependencies=[Auth],
         summary="Per-backend health status across all 4 providers")
def provider_health():
    """
    Returns health status for every registered backend.
    `AVAILABLE` = ready to execute.
    `CREDENTIALS_REQUIRED` = SDK installed but credentials not configured.
    `UNAVAILABLE` = SDK not installed.
    """
    return provider_registry.backend_health()


@app.get("/health/detailed", tags=["Health"], dependencies=[Auth],
         summary="Full provider + capability health report")
def detailed_health():
    return provider_health_report()


# ── Signal ─────────────────────────────────────────────────────────────────────

@app.post("/api/v1/signal", tags=["Signal"], dependencies=[Auth],
          summary="Classify quantum node state → CONVERGED | SUSPENDED | DIVERGED")
def signal_classify(payload: SignalPayload):
    """
    Validates the quantum node snapshot and classifies its state.
    Deterministic: same input always produces the same output.
    No quantum hardware required.
    """
    result = invoke_runtime("signal", payload.model_dump())
    http_code = _runtime_status_to_http(result["status"])
    return JSONResponse(status_code=http_code, content=result)


# ── Quantum Pipeline ───────────────────────────────────────────────────────────

@app.post("/api/v1/quantum/corrosion", tags=["Quantum"], dependencies=[Auth],
          summary="Assess marine corrosion risk via quantum simulation")
def quantum_corrosion(payload: QuantumPipelinePayload):
    """
    Runs the Hardware-Efficient Ansatz (HEA) corrosion assessment.
    Uses AerSimulator if installed, falls back to local classical simulator.
    Returns: degradation_probability, risk_level, recommended_anode_current.
    """
    result = invoke_runtime("quantum_pipeline", payload.model_dump())
    return JSONResponse(status_code=_runtime_status_to_http(result["status"]), content=result)


def _execute_circuit(request: CircuitExecuteRequest, trace_id: str,
                     execution_id: Optional[str] = None) -> Tuple[int, Dict[str, Any]]:
    """
    Shared execution path used by POST /api/v1/quantum/execute and the QCG
    adapter. Returns (http_status, body). Validation, backend selection,
    compilation, execution, instrumentation and error handling all live here
    exactly once; production_execute() remains the only execution pipeline.
    """
    started_at    = _utc_now_iso()
    t0            = time.perf_counter()
    instrumentation: Dict[str, Any] = {
        "trace_id":            trace_id,
        "execution_id":        execution_id or _new_execution_id(),
        "execution_timestamp": started_at,
        "num_qubits":          request.num_qubits,
        "shots":               request.shots,
        "seed":                request.seed,
        "gate_count":          len(request.gate_sequence),
        "logical_depth":       _logical_depth(request.gate_sequence),  # pre-transpile estimate
        "circuit_depth":       None,   # filled only if the runtime reports it
        "backend_name":        None,
        "duration_ms":         None,
        "execution_status":    None,
    }

    def _close(status_str: str) -> None:
        instrumentation["duration_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        instrumentation["execution_status"] = status_str
        _record_execution(dict(instrumentation))
        logger.info(
            "quantum.execute execution_id=%s status=%s backend=%s qubits=%s shots=%s "
            "seed=%s duration_ms=%s",
            instrumentation["execution_id"], status_str, instrumentation["backend_name"],
            request.num_qubits, request.shots, request.seed, instrumentation["duration_ms"],
        )

    # 1) Structural validation (cheap, before touching any backend)
    problems = _validate_circuit(request.num_qubits, request.gate_sequence)
    if problems:
        _close("VALIDATION_ERROR")
        return 422, {
            "status":          "VALIDATION_ERROR",
            "trace_id":        trace_id,
            "execution_id":    instrumentation["execution_id"],
            "errors":          problems,
            "instrumentation": dict(instrumentation),
        }

    # 2) Existing execution pipeline (backend selection, compilation, execution,
    #    result retrieval all happen inside production_execute — unchanged).
    try:
        circuit = CircuitSpec(
            num_qubits    = request.num_qubits,
            gate_sequence = request.gate_sequence,
            shots         = request.shots,
            seed          = request.seed,
        )
        req = BackendRequirements(
            min_qubits            = request.num_qubits,
            min_shots             = request.shots,
            preferred_provider    = request.preferred_provider,
            require_simulator     = request.require_simulator,
            require_real_hardware = request.require_real_hardware,
        )
        result = production_execute(circuit, req)
    except Exception as exc:
        logger.exception("quantum.execute unhandled error execution_id=%s", instrumentation["execution_id"])
        _close("INTERNAL_ERROR")
        return 500, {
            "status":          "INTERNAL_ERROR",
            "trace_id":        trace_id,
            "execution_id":    instrumentation["execution_id"],
            "detail":          f"Execution failed with {type(exc).__name__}. "
                               f"See server logs for trace_id={trace_id}.",
            "instrumentation": dict(instrumentation),
        }

    status_str = str(result.get("status", "FAILED"))
    http_code  = _runtime_status_to_http(status_str)

    # 3) Preserve every runtime field; add trace/instrumentation on top.
    body = dict(result)
    if "trace_id" in body and body["trace_id"] != trace_id:
        body["runtime_trace_id"] = body["trace_id"]
    body["trace_id"] = trace_id
    body.setdefault("execution_id", instrumentation["execution_id"])
    instrumentation["execution_id"] = body["execution_id"]

    backend_name  = _pick(result, "backend_name", "backend", kind=str)
    provider_name = _pick(result, "provider_name", "provider", kind=str)
    counts        = _pick(result, "measurement_counts", "counts", kind=dict)
    is_sim        = _pick(result, "is_simulator", kind=bool)
    if is_sim is None and backend_name == VERIFIED_BACKEND:
        is_sim = True   # grounded in the verified classification of this backend
    if backend_name and "backend_name" not in body:
        body["backend_name"] = backend_name
    if provider_name and "provider_name" not in body:
        body["provider_name"] = provider_name
    if counts is not None and "measurement_counts" not in body:
        body["measurement_counts"] = counts
    if is_sim is not None and "is_simulator" not in body:
        body["is_simulator"] = is_sim

    instrumentation["backend_name"]  = backend_name
    instrumentation["circuit_depth"] = _pick(result, "circuit_depth", kind=int)
    _close(status_str)
    body["instrumentation"] = dict(instrumentation)
    return http_code, body


@app.post("/api/v1/quantum/execute", tags=["Quantum"], dependencies=[Auth],
          summary="Execute an arbitrary quantum circuit via provider abstraction")
def circuit_execute(request: CircuitExecuteRequest, http_request: Request):
    """
    Accepts a provider-agnostic circuit spec and routes to the best
    available healthy backend. Supports automatic failover.

    Gate format: `{"gate": "h", "qubits": [0]}` — see Appendix A in the docs.

    Optional header `X-Trace-ID` is propagated end-to-end; the effective ID is
    returned in the `trace_id` body field and the `X-Trace-ID` response header.
    All fields returned by the runtime are preserved; `trace_id`, `execution_id`
    and `instrumentation` are added (plus `backend_name`, `provider_name`,
    `is_simulator`, `measurement_counts` where the runtime result lets them be
    derived without guessing).
    """
    http_status, body = _execute_circuit(request, _trace_id_for(http_request))
    return JSONResponse(status_code=http_status, content=body)


# ── QCG compatibility adapter (Marine Runtime only) ───────────────────────────
# QCG's web_server.py is an external system and is NOT modified. These endpoints
# accept QCG's request envelopes and return QCG's 9-key InvocationResult shape:
#   invocation_id, service_id, operation, status, response, duration_ms,
#   trust_method, evidence, error
# Circuit workloads are mapped onto the existing CircuitExecuteRequest and run
# through the shared _execute_circuit() helper (the same code path as
# POST /api/v1/quantum/execute). This adapter does NOT implement QCG
# orchestration, QUBO solving, network coordination, evidence-ledger writes or
# hybrid routing.
#
# Honest labeling: a run on AerSimulator is reported as QUANTUM_SIMULATED /
# SIMULATED / trust_method CLASSICAL. Marine never reports QUANTUM_LIVE: physical
# QPU execution has not been verified for this deployment.

QCG_DEFAULT_TIMEOUT_SECONDS = 25.0

# Fields interpreted as circuit instructions.
_QCG_CIRCUIT_KEYS = ("num_qubits", "gate_sequence", "shots", "seed", "preferred_provider")
# QCG WorkloadMetadata fields (carried inside the dispatch payload by QCG).
_QCG_METADATA_KEYS = (
    "workload_id", "workload_type", "problem_size", "is_qubo_compatible",
    "requires_entanglement", "requires_live_hardware", "classical_fallback_acceptable",
)


class QCGWorkloadError(ValueError):
    """The QCG workload cannot be mapped onto a Marine circuit request."""


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _qcg_timeout_seconds() -> float:
    """QCG_ADAPTER_TIMEOUT_SECONDS (default 25). Invalid/non-positive values fall back to the default."""
    raw = os.environ.get("QCG_ADAPTER_TIMEOUT_SECONDS")
    if raw is None or not raw.strip():
        return QCG_DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Ignoring non-numeric QCG_ADAPTER_TIMEOUT_SECONDS")
        return QCG_DEFAULT_TIMEOUT_SECONDS
    if not math.isfinite(value) or value <= 0:
        logger.warning("Ignoring non-positive QCG_ADAPTER_TIMEOUT_SECONDS")
        return QCG_DEFAULT_TIMEOUT_SECONDS
    return value


# Bounded worker pool. A timed-out Aer run cannot be killed, so it keeps its
# worker until it finishes; the bound stops timed-out jobs from piling up.
_qcg_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=max(1, _env_int("QCG_ADAPTER_MAX_WORKERS", 4)),
    thread_name_prefix="qcg-exec",
)


def _adopt_invocation_trace(request: Request, invocation_id: str) -> str:
    """
    Trace identity precedence:
      1. a valid X-Trace-ID header (already applied by the middleware),
      2. a valid QCG invocation_id (adopted as the trace ID),
      3. the UUID the middleware generated.
    The caller's invocation_id is always echoed back unchanged.
    """
    if request.headers.get("X-Trace-ID", "").strip():
        return _trace_id_for(request)
    candidate = (invocation_id or "").strip()
    if candidate and _TRACE_ID_RE.match(candidate):
        request.state.trace_id = candidate   # middleware stamps the response header from this
        _trace_ctx.set(candidate)            # log lines for the rest of this call carry it
        return candidate
    return _trace_id_for(request)


def _qcg_metadata(workload: Dict[str, Any]) -> Dict[str, Any]:
    """Typed view of QCG WorkloadMetadata fields found inside a dispatch payload."""
    def _flag(key: str, default: bool) -> bool:
        value = workload.get(key, default)
        if not isinstance(value, bool):
            raise QCGWorkloadError(f"workload.{key} must be a boolean")
        return value

    problem_size = workload.get("problem_size", 0)
    if isinstance(problem_size, bool) or not isinstance(problem_size, int) or problem_size < 0:
        raise QCGWorkloadError("workload.problem_size must be a non-negative integer")
    workload_type = workload.get("workload_type", "GENERAL")
    if not isinstance(workload_type, str):
        raise QCGWorkloadError("workload.workload_type must be a string")
    return {
        "workload_type": workload_type,
        "problem_size": problem_size,
        "is_qubo_compatible": _flag("is_qubo_compatible", False),
        "requires_entanglement": _flag("requires_entanglement", False),
        "requires_live_hardware": _flag("requires_live_hardware", False),
        "classical_fallback_acceptable": _flag("classical_fallback_acceptable", True),
    }


def _qcg_circuit_request(
    workload: Dict[str, Any], meta: Dict[str, Any]
) -> Tuple[CircuitExecuteRequest, List[str]]:
    """
    Map a QCG workload carrying a Marine-compatible circuit onto CircuitExecuteRequest.

    Supported workload keys: num_qubits, gate_sequence, shots, seed,
    preferred_provider. QCG metadata keys are accepted and echoed. Any other key
    is not interpreted and is returned in `ignored_fields` (never silently used).
    Only `requires_live_hardware` changes backend selection;
    `classical_fallback_acceptable` is echoed but does not decide it.
    """
    if not isinstance(workload, dict):
        raise QCGWorkloadError("workload must be a JSON object")
    if "num_qubits" not in workload or "gate_sequence" not in workload:
        raise QCGWorkloadError(
            "Marine Runtime requires workload.num_qubits and workload.gate_sequence. "
            "QUBO or other abstract workloads must be compiled into this circuit "
            "format before submission."
        )
    hardware_only = meta["requires_live_hardware"]
    data = {k: workload[k] for k in _QCG_CIRCUIT_KEYS if k in workload}
    data["require_simulator"] = not hardware_only
    data["require_real_hardware"] = hardware_only
    try:
        circuit_request = CircuitExecuteRequest(**data)
    except ValidationError as exc:
        # loc + message only: never echo submitted values back.
        problems = [
            "workload." + ".".join(str(p) for p in err.get("loc", ())) + ": " + str(err.get("msg", "invalid"))
            for err in exc.errors()
        ]
        raise QCGWorkloadError("; ".join(problems) or "invalid workload")
    ignored = sorted(k for k in workload if k not in _QCG_CIRCUIT_KEYS and k not in _QCG_METADATA_KEYS)
    return circuit_request, ignored


def _qcg_envelope(
    *, invocation_id: str, service_id: str, operation: str, status_str: str,
    response: Any, started_at: float, trust_method: str = "CLASSICAL",
    evidence: Optional[Dict[str, Any]] = None, error: Optional[str] = None,
) -> Dict[str, Any]:
    """Exactly QCG's nine InvocationResult keys (retry_count/timestamp are added by QCG's SDK, not here)."""
    return {
        "invocation_id": invocation_id,
        "service_id":    service_id,
        "operation":     operation,
        "status":        status_str,
        "response":      response,
        "duration_ms":   round((time.perf_counter() - started_at) * 1000, 2),
        "trust_method":  trust_method,
        "evidence":      evidence,
        "error":         error,
    }


def _qcg_counts_hash(counts: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(counts, dict):
        return None
    canonical = json.dumps(counts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _qcg_execution_envelope(
    *, invocation_id: str, service_id: str, operation: str, trace_id: str,
    execution_body: Dict[str, Any], http_status: int, started_at: float,
    request_metadata: Dict[str, Any], ignored_fields: List[str],
    timed_out: bool = False, background_note: Optional[str] = None,
) -> Dict[str, Any]:
    backend_name  = _pick(execution_body, "backend_name", "backend", kind=str)
    provider_name = _pick(execution_body, "provider_name", "provider", kind=str)
    counts        = _pick(execution_body, "measurement_counts", "counts", kind=dict)
    is_sim        = _pick(execution_body, "is_simulator", kind=bool)
    if is_sim is False and backend_name == VERIFIED_BACKEND:
        is_sim = None   # contradictory: AerSimulator is never a physical QPU

    runtime_status = str(execution_body.get("status", "FAILED")).upper()
    succeeded = (not timed_out) and 200 <= http_status < 300 and runtime_status == "SUCCESS"

    if succeeded and is_sim is True:
        classification, path, environment = "QUANTUM_SIMULATED", "SIMULATED", "SIMULATOR"
    elif succeeded:
        # Runtime did not positively identify a simulator. Never claim live hardware.
        classification, path, environment = "UNVERIFIED", "UNVERIFIED", "UNVERIFIED"
    else:
        # QCG block rule: nothing (usable) executed -> CLASSICAL / BLOCKED.
        classification, path, environment = "CLASSICAL", "BLOCKED", "NONE"
    trust_method = "CLASSICAL"   # QCG maps simulators to CLASSICAL; Marine never emits HYBRID trust

    if timed_out:
        status_str = "TIMEOUT"
    else:
        status_str = "SUCCESS" if succeeded else "FAILED"

    error_text: Optional[str] = None
    if not succeeded:
        error_value = execution_body.get("detail") or execution_body.get("errors")
        if isinstance(error_value, list):
            error_value = "; ".join(str(item) for item in error_value)
        error_text = str(error_value or runtime_status)

    result_hash = _qcg_counts_hash(counts) if succeeded else None
    response_payload = {
        "trace_id":                        trace_id,
        "classification":                  classification,
        "execution_path":                  path,
        "execution_environment":           environment,
        "is_simulator":                    is_sim if succeeded else None,
        "physical_qpu_execution_verified": False,
        "provider_id":                     provider_name,
        "backend_name":                    backend_name,
        "measurement_counts":              counts if succeeded else None,
        "confidence":                      None,
        "result_hash":                     result_hash,
        "bhex_ready":                      None,
        "provenance_available":            False,
        "request_metadata":                request_metadata,
        "ignored_fields":                  ignored_fields,
        "marine_execution_result":         None if timed_out else execution_body,
    }
    if background_note:
        response_payload["background_execution"] = background_note
    return _qcg_envelope(
        invocation_id=invocation_id, service_id=service_id, operation=operation,
        status_str=status_str, response=response_payload, started_at=started_at,
        trust_method=trust_method, error=error_text,
        evidence={
            "trace_id":             trace_id,
            "execution_id":         execution_body.get("execution_id"),
            "classification":       classification,
            "execution_path":       path,
            "backend_name":         backend_name,
            "result_hash":          result_hash,
            "provenance_available": False,
        },
    )


def _qcg_failure_envelope(
    *, invocation_id: str, service_id: str, operation: str, trace_id: str,
    started_at: float, error: str, status_str: str = "FAILED",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    response = {
        "trace_id": trace_id, "classification": "CLASSICAL", "execution_path": "BLOCKED",
        "execution_environment": "NONE", "physical_qpu_execution_verified": False,
    }
    response.update(extra or {})
    return _qcg_envelope(
        invocation_id=invocation_id, service_id=service_id, operation=operation,
        status_str=status_str, response=response, started_at=started_at, error=error,
        evidence={"trace_id": trace_id, "classification": "CLASSICAL",
                  "execution_path": "BLOCKED", "provenance_available": False},
    )


def _run_qcg_hybrid_workload(
    workload: Any, http_request: Request, *, trace_id: str, invocation_id: str,
    service_id: str, operation: str, meta: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    started_at = time.perf_counter()

    # 1) Map the QCG workload -> CircuitExecuteRequest (no execution yet).
    try:
        if not isinstance(workload, dict):
            raise QCGWorkloadError("workload must be a JSON object")
        meta = meta if meta is not None else _qcg_metadata(workload)
        circuit_request, ignored = _qcg_circuit_request(workload, meta)
    except QCGWorkloadError as exc:
        return JSONResponse(status_code=422, content=_qcg_failure_envelope(
            invocation_id=invocation_id, service_id=service_id, operation=operation,
            trace_id=trace_id, started_at=started_at, error=str(exc),
        ))

    # 2) Run the shared execution helper under a timeout.
    execution_id = _new_execution_id()
    timeout_s = _qcg_timeout_seconds()
    ctx = contextvars.copy_context()   # carries the trace ID into the worker thread
    future = _qcg_executor.submit(ctx.run, _execute_circuit, circuit_request, trace_id, execution_id)
    try:
        http_status, execution_body = future.result(timeout=timeout_s)
    except concurrent.futures.TimeoutError:
        if future.done():
            raise   # the worker itself raised TimeoutError; not an adapter timeout
        cancelled = future.cancel()   # only succeeds if it has not started yet
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 3)
        logger.warning("qcg.dispatch TIMEOUT execution_id=%s after %.1fs cancelled_before_start=%s",
                       execution_id, timeout_s, cancelled)
        _record_execution({
            "trace_id": trace_id, "execution_id": execution_id,
            "execution_timestamp": _utc_now_iso(),
            "num_qubits": circuit_request.num_qubits, "shots": circuit_request.shots,
            "seed": circuit_request.seed, "gate_count": len(circuit_request.gate_sequence),
            "logical_depth": _logical_depth(circuit_request.gate_sequence),
            "circuit_depth": None, "backend_name": None,
            "duration_ms": elapsed_ms, "execution_status": "TIMEOUT",
        })
        note = ("CANCELLED_BEFORE_START" if cancelled else
                "MAY_STILL_BE_RUNNING: the run could not be cancelled and may finish in the "
                "background; its result is discarded and is NOT reported as successful.")
        envelope = _qcg_execution_envelope(
            invocation_id=invocation_id, service_id=service_id, operation=operation,
            trace_id=trace_id,
            execution_body={"status": "TIMEOUT", "execution_id": execution_id,
                            "detail": f"Execution exceeded the {timeout_s:g}s adapter timeout."},
            http_status=504, started_at=started_at, request_metadata=meta,
            ignored_fields=ignored, timed_out=True, background_note=note,
        )
        return JSONResponse(status_code=504, content=envelope)
    except Exception as exc:
        logger.exception("qcg.dispatch unexpected worker failure execution_id=%s", execution_id)
        return JSONResponse(status_code=500, content=_qcg_failure_envelope(
            invocation_id=invocation_id, service_id=service_id, operation=operation,
            trace_id=trace_id, started_at=started_at,
            error=f"Execution failed with {type(exc).__name__}. See server logs for trace_id={trace_id}.",
        ))

    envelope = _qcg_execution_envelope(
        invocation_id=invocation_id, service_id=service_id, operation=operation,
        trace_id=trace_id, execution_body=execution_body, http_status=http_status,
        started_at=started_at, request_metadata=meta, ignored_fields=ignored,
    )
    return JSONResponse(status_code=http_status, content=envelope)


def _qcg_simple_operation(
    fn, *, trace_id: str, invocation_id: str, service_id: str, operation: str,
) -> JSONResponse:
    """health_check / list_providers: read-only, no execution."""
    started_at = time.perf_counter()
    try:
        result = fn()
    except Exception as exc:
        logger.exception("qcg.dispatch operation=%s failed", operation)
        return JSONResponse(status_code=500, content=_qcg_failure_envelope(
            invocation_id=invocation_id, service_id=service_id, operation=operation,
            trace_id=trace_id, started_at=started_at,
            error=f"Operation failed with {type(exc).__name__}. See server logs for trace_id={trace_id}.",
        ))
    return JSONResponse(content=_qcg_envelope(
        invocation_id=invocation_id, service_id=service_id, operation=operation,
        status_str="SUCCESS", response=jsonable_encoder(result), started_at=started_at,
        evidence={"trace_id": trace_id, "provenance_available": False},
    ))


@app.post("/hybrid/submit", tags=["QCG Compatibility"], dependencies=[Auth],
          summary="QCG-compatible hybrid workload submission")
def qcg_hybrid_submit(payload: QCGHybridSubmitRequest, http_request: Request):
    """
    Accepts QCG's HybridSubmitRequest. `workload` must carry a Marine circuit
    (`num_qubits`, `gate_sequence`, optional `shots`/`seed`/`preferred_provider`).
    Returns a QCG InvocationResult. Simulator runs are labeled QUANTUM_SIMULATED.
    """
    trace_id = _trace_id_for(http_request)
    meta = {
        "workload_type": payload.workload_type,
        "problem_size": payload.problem_size,
        "is_qubo_compatible": payload.is_qubo_compatible,
        "requires_entanglement": payload.requires_entanglement,
        "requires_live_hardware": payload.requires_live_hardware,
        "classical_fallback_acceptable": payload.classical_fallback_acceptable,
    }
    return _run_qcg_hybrid_workload(
        payload.workload, http_request, trace_id=trace_id, invocation_id=trace_id,
        service_id="MARINE-QUANTUM-RUNTIME", operation="hybrid_submit", meta=meta,
    )


@app.post("/hybrid/dispatch", tags=["QCG Compatibility"], dependencies=[Auth],
          summary="QCG-compatible capability dispatch")
def qcg_hybrid_dispatch(payload: QCGCapabilityDispatchRequest, http_request: Request):
    """
    Accepts QCG's CapabilityDispatchRequest. Supported operations:
    `hybrid_submit` (circuit execution), `health_check`, `list_providers`.
    Any other operation returns status SERVICE_NOT_FOUND.
    Trace identity: X-Trace-ID header, else `invocation_id`, else a generated UUID.
    """
    trace_id = _adopt_invocation_trace(http_request, payload.invocation_id)
    invocation_id = payload.invocation_id or trace_id
    operation = payload.operation
    common = dict(trace_id=trace_id, invocation_id=invocation_id, service_id=payload.service_id)

    if operation == "hybrid_submit":
        return _run_qcg_hybrid_workload(
            payload.payload, http_request, operation=operation, **common,
        )
    if operation == "health_check":
        return _qcg_simple_operation(health, operation=operation, **common)
    if operation == "list_providers":
        return _qcg_simple_operation(
            lambda: {"providers": provider_capabilities(),
                     "backend_health": provider_registry.backend_health()},
            operation=operation, **common,
        )

    started_at = time.perf_counter()
    envelope = _qcg_failure_envelope(
        invocation_id=invocation_id, service_id=payload.service_id, operation=operation,
        trace_id=trace_id, started_at=started_at, status_str="SERVICE_NOT_FOUND",
        error=f"Unsupported operation in Marine Runtime: {operation}",
    )
    envelope["response"] = None
    return JSONResponse(status_code=404, content=envelope)


@app.get("/api/v1/quantum/providers", tags=["Quantum"], dependencies=[Auth],
         summary="All providers, backends, capabilities, and noise profiles")
def quantum_providers():
    caps = provider_capabilities()
    # Enrich with noise profiles and hardware constraints
    enriched = {}
    for provider_name, data in caps.items():
        enriched[provider_name] = {**data, "backends_detail": []}
        for backend in data.get("backends", []):
            backend_name = backend["backend_name"]
            noise = get_noise_profile(backend_name)
            constraints = get_hardware_constraints(backend_name)
            enriched[provider_name]["backends_detail"].append({
                **backend,
                "noise_profile":       noise.to_dict() if noise else None,
                "hardware_constraints": constraints.to_dict() if constraints else None,
            })
    return enriched


@app.get("/api/v1/quantum/backend", tags=["Quantum"], dependencies=[Auth],
         summary="Backend identity, availability and honest classification")
def quantum_backend(http_request: Request):
    """
    Reports the verified backend (Qiskit AerSimulator), its live availability
    as seen by the provider registry, and the registry's view of other
    providers. Physical QPU execution is reported as NOT verified.
    """
    trace_id = _trace_id_for(http_request)
    errors: List[str] = []

    health = None
    try:
        health = provider_registry.backend_health()
    except Exception as exc:
        logger.exception("quantum.backend: backend_health() failed")
        errors.append(f"backend_health unavailable: {type(exc).__name__}")

    caps = None
    try:
        caps = provider_capabilities()
    except Exception as exc:
        logger.exception("quantum.backend: provider_capabilities() failed")
        errors.append(f"provider_capabilities unavailable: {type(exc).__name__}")

    entry = _find_key(health, VERIFIED_BACKEND) if health is not None else None
    return {
        "status":               "SUCCESS" if not errors else "PARTIAL",
        "trace_id":             trace_id,
        "provider_name":        VERIFIED_PROVIDER,
        "backend_name":         VERIFIED_BACKEND,
        "backend_availability": _availability_label(entry),
        "classification":       BACKEND_CLASSIFICATION,
        "is_simulator":         True,
        "hardware": {
            "physical_qpu_execution_verified": False,
            "availability": "NOT_VERIFIED",
            "note": "No physical quantum hardware execution has been verified. "
                    "Registry entries for IBM/IonQ below are configuration status only.",
        },
        "supported_configuration": {
            "num_qubits":          {"min": 1, "max": MAX_QUBITS},
            "shots":               {"min": MIN_SHOTS, "max": MAX_SHOTS, "default": DEFAULT_SHOTS},
            "seed":                {"type": "integer", "default": DEFAULT_SEED},
            "gate_sequence_item":  {"gate": "<name>", "qubits": ["<int>", "..."]},
            "tested_configuration": {"num_qubits": 3, "shots": 1024, "seed": 42},
        },
        "registry_health":       health,
        "provider_capabilities": _find_key(caps, VERIFIED_PROVIDER) if caps is not None else None,
        "errors":                errors,
    }


@app.get("/api/v1/quantum/calibration", tags=["Quantum"], dependencies=[Auth],
         summary="Calibration status and execution instrumentation")
def quantum_calibration(http_request: Request):
    """
    AerSimulator is a simulator: no physical calibration data exists, and none
    is fabricated here. Also exposes the instrumentation recorded per execution
    (in-memory, bounded to the most recent executions, resets on restart).
    """
    trace_id = _trace_id_for(http_request)
    errors: List[str] = []

    noise_profile = None
    try:
        p = get_noise_profile(VERIFIED_BACKEND)
        noise_profile = p.to_dict() if p else None
    except Exception as exc:
        logger.exception("quantum.calibration: get_noise_profile() failed")
        errors.append(f"noise_profile unavailable: {type(exc).__name__}")

    constraints = None
    try:
        c = get_hardware_constraints(VERIFIED_BACKEND)
        constraints = c.to_dict() if c else None
    except Exception as exc:
        logger.exception("quantum.calibration: get_hardware_constraints() failed")
        errors.append(f"hardware_constraints unavailable: {type(exc).__name__}")

    log = _execution_log_snapshot()
    by_status: Dict[str, int] = {}
    for rec in log:
        k = str(rec.get("execution_status"))
        by_status[k] = by_status.get(k, 0) + 1

    return {
        "status":               "SUCCESS" if not errors else "PARTIAL",
        "trace_id":             trace_id,
        "provider_name":        VERIFIED_PROVIDER,
        "backend_name":         VERIFIED_BACKEND,
        "classification":       BACKEND_CLASSIFICATION,
        "is_simulator":         True,
        "calibration_available": False,
        "calibration_status":   "NOT_APPLICABLE",
        "calibration_note": "Physical calibration (T1/T2, gate/readout error) does not apply to a "
                            "simulator and is not reported. No calibration values are fabricated.",
        "backend_metadata": {
            "noise_profile": noise_profile,
            "noise_profile_note": "As returned by the runtime's get_noise_profile(); not evidence "
                                  "of a physical device calibration.",
            "hardware_constraints": constraints,
        },
        "instrumentation": {
            "fields_recorded": [
                "trace_id", "execution_id", "execution_timestamp", "num_qubits", "shots",
                "seed", "gate_count", "logical_depth", "circuit_depth (if reported by runtime)",
                "backend_name", "duration_ms", "execution_status",
            ],
            "storage": "in-memory, per-process, bounded; resets on restart",
            "executions_recorded": len(log),
            "by_status":           by_status,
            "last_execution":      log[-1] if log else None,
        },
        "errors": errors,
    }


# ── Capability Platform ────────────────────────────────────────────────────────

@app.get("/api/v1/capabilities", tags=["Capability Platform"], dependencies=[Auth],
         summary="List all registered capabilities with health")
def capabilities():
    return get_active_capabilities()


@app.post("/api/v1/capability/{capability_id}", tags=["Capability Platform"], dependencies=[Auth],
          summary="Invoke a capability through the full platform stack")
def capability_invoke(capability_id: str, request: GenericInvokeRequest):
    """
    Full invocation pipeline:
    dependency check → authority check → typed validation
    → replay authority → execution → evidence → observability.

    Valid capability_ids: `signal`, `quantum_pipeline`,
    `distributed_qapp`, `operational_monitor`.
    """
    result = invoke_capability(capability_id, request.payload)
    return JSONResponse(status_code=_runtime_status_to_http(result["status"]), content=result)


# ── Generic Module Invoke (legacy / convenience) ───────────────────────────────

@app.post("/api/v1/invoke/{module_name}", tags=["Modules"], dependencies=[Auth],
          summary="Invoke any runtime module directly (lighter stack than /capability)")
def module_invoke(module_name: str, request: GenericInvokeRequest):
    """
    Calls the root `invoke_runtime` gateway. Skips authority matrix,
    dependency graph, and replay authority checks.
    Use `/capability/{id}` for the full governance-aware stack.

    Valid module names: `signal`, `quantum_pipeline`,
    `distributed_qapp`, `operational_monitor`.
    """
    result = invoke_runtime(module_name, request.payload)
    # Root invoke_runtime returns "FAILED" with an "UnknownModule:" error for
    # unrecognised module names (status-string inconsistency with src/invoke_runtime.py
    # which returns "MODULE_NOT_FOUND"). Normalise both to HTTP 404.
    status_str = result["status"]
    errors     = result.get("errors", [])
    is_unknown = (
        status_str == "MODULE_NOT_FOUND"
        or any("UnknownModule" in str(e) for e in errors)
    )
    http_code = 404 if is_unknown else _runtime_status_to_http(status_str)
    if is_unknown:
        result["status"] = "MODULE_NOT_FOUND"   # normalise for API consumers
    return JSONResponse(status_code=http_code, content=result)


# ── Observability ──────────────────────────────────────────────────────────────

@app.get("/api/v1/dashboard", tags=["Observability"], dependencies=[Auth],
         summary="Full dashboard JSON (all 6 telemetry feeds)")
def dashboard():
    """
    Returns telemetry for all 6 ecosystem dashboards:
    Replay, Runtime, Quantum, Operations, Health, Governance.
    Production: no UI ownership — this runtime only produces the data.
    """
    return get_dashboard_json()


@app.get("/api/v1/queue", tags=["Observability"], dependencies=[Auth],
         summary="Queue depth and backend availability status")
def queue():
    return queue_status()


# ── Governance ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/governance/authority-matrix", tags=["Governance"], dependencies=[Auth],
         summary="Capability authority ceilings and permitted/denied actions")
def authority_matrix_endpoint():
    return matrix_snapshot()


@app.get("/api/v1/governance/decision-ledger", tags=["Governance"], dependencies=[Auth],
         summary="Governance decision ledger summary")
def decision_ledger_endpoint():
    return ledger_summary()


@app.get("/api/v1/governance/doctrines", tags=["Governance"], dependencies=[Auth],
         summary="Evaluate all runtime design doctrines against current context")
def doctrine_check():
    context = {
        "timestamp_posture": "DETERMINISTIC",
        "silent_failure": False,
        "negative_authority": ["placeholder"],
        "id_generation": "SHA256",
        "log_type": "append_only",
        "stub_declared": True,
        "attachment_typed": True,
        "dependency_graph_enforced": True,
    }
    return evaluate_doctrines(context)


@app.get("/api/v1/governance/replay-stats", tags=["Governance"], dependencies=[Auth],
         summary="Replay authority permit / deny statistics")
def replay_stats():
    return get_replay_statistics()


@app.get("/api/v1/governance/provenance", tags=["Governance"], dependencies=[Auth],
         summary="Evidence ledger status and record count")
def provenance():
    return get_provenance_status()


# ── Dev / debug (disable in production) ───────────────────────────────────────

@app.get("/api/v1/debug/authority-audit", tags=["Debug"], dependencies=[Auth],
         summary="Recent authority check audit log (last 50 entries)")
def authority_audit():
    return audit_log()[-50:]


# ── Error handlers ─────────────────────────────────────────────────────────────
# Every application-generated error carries trace_id (body + X-Trace-ID header).
# Existing `detail` fields are preserved for backward compatibility.

_HTTP_STATUS_NAMES = {
    400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED", 409: "CONFLICT", 422: "VALIDATION_ERROR",
}


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    tid = _trace_id_for(request)
    headers = dict(exc.headers or {})
    headers["X-Trace-ID"] = tid
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status":   _HTTP_STATUS_NAMES.get(exc.status_code, "ERROR"),
            "detail":   exc.detail,
            "trace_id": tid,
        },
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    tid = _trace_id_for(request)
    return JSONResponse(
        status_code=422,
        content={
            "status":   "VALIDATION_ERROR",
            "detail":   jsonable_encoder(exc.errors()),
            "trace_id": tid,
        },
        headers={"X-Trace-ID": tid},
    )


@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    tid = _trace_id_for(request)
    # Full traceback goes to the server log (tagged with the trace ID);
    # the client only gets the exception type, never internals.
    logger.error("Unhandled exception on %s [trace_id=%s]", request.url.path, tid, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "status":   "INTERNAL_ERROR",
            "detail":   f"Internal server error ({type(exc).__name__}). "
                        f"Quote trace_id={tid} when reporting.",
            "trace_id": tid,
        },
        headers={"X-Trace-ID": tid},
    )


# ── Entry point ────────────────────────────────────────────────────────────────
@app.get("/")
def home():
    return {
        "project": "Marine Quantum Runtime API",
        "status": "Running",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    reload = os.environ.get("ENV", "development") == "development"
    logger.info(f"Starting Marine Quantum Runtime API on port {port}")
    logger.info(f"Swagger UI: http://localhost:{port}/docs")
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )
