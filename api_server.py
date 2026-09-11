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
import logging
from typing import Any, Dict, List, Optional

# Make the runtime importable regardless of working directory
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from fastapi import FastAPI, HTTPException, Header, Depends, Request, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
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

logging.basicConfig(level=LOG_LEVEL)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Auth ───────────────────────────────────────────────────────────────────────

_RUNTIME_API_KEY = os.environ.get("RUNTIME_API_KEY", "dev-insecure-key")
if _RUNTIME_API_KEY == "dev-insecure-key":
    logger.warning(
        "RUNTIME_API_KEY not set — using insecure dev default. "
        "Set a real key before any production deployment."
    )


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if not x_api_key or x_api_key != _RUNTIME_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key


Auth = Depends(verify_api_key)


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
    num_qubits:    int               = Field(..., ge=1, le=29)
    gate_sequence: List[Dict[str, Any]]
    shots:         int               = Field(4096, ge=100, le=100_000)
    seed:          int               = Field(42)
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


@app.post("/api/v1/quantum/execute", tags=["Quantum"], dependencies=[Auth],
          summary="Execute an arbitrary quantum circuit via provider abstraction")
def circuit_execute(request: CircuitExecuteRequest):
    """
    Accepts a provider-agnostic circuit spec and routes to the best
    available healthy backend. Supports automatic failover.

    Gate format: `{"gate": "h", "qubits": [0]}` — see Appendix A in the docs.
    """
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
    return JSONResponse(status_code=_runtime_status_to_http(result["status"]), content=result)


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

@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"status": "INTERNAL_ERROR", "detail": str(exc)},
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

