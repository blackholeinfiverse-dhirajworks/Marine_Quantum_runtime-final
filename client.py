"""
client.py — Marine Quantum Runtime Client SDK
==============================================
Lightweight Python client for Platform Runtime integration.
Works in TWO modes:

  MODE 1 — Direct (in-process, no HTTP server needed):
      client = RuntimeClient(mode="direct")
      result = client.signal(node_id="qnode_01", ...)

  MODE 2 — HTTP (calls a deployed or local api_server.py):
      client = RuntimeClient(base_url="http://localhost:8000", api_key="your-key")
      result = client.signal(node_id="qnode_01", ...)

Both modes return IDENTICAL result shapes. Switch between them with one
constructor argument — no other code changes needed.

INSTALL for HTTP mode:
    pip install requests

USAGE EXAMPLE:
    from client import RuntimeClient

    # Local / direct (fastest — zero network overhead)
    c = RuntimeClient(mode="direct")
    r = c.signal(node_id="q1", energy_delta=0.0001,
                 iterations=120, confidence=0.92, variance=0.002)
    print(r.state)          # CONVERGED | SUSPENDED | DIVERGED
    print(r.sigma)          # 0.04472136
    print(r.success)        # True
    print(r.raw)            # full dict
"""

import sys
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ── Result wrappers ────────────────────────────────────────────────────────────

@dataclass
class SignalResult:
    success:    bool
    state:      str             # CONVERGED | SUSPENDED | DIVERGED
    prev:       str             # INITIALISING | ACTIVE
    cause:      str
    confidence: float
    sigma:      float
    seq:        int
    ts:         str
    raw:        dict
    errors:     List[str]

    def __bool__(self) -> bool:
        return self.success


@dataclass
class QuantumResult:
    success:           bool
    provider_name:     str
    backend_name:      str
    measurement_counts: Dict[str, int]
    shots_used:        int
    is_simulator:      bool
    seed:              Optional[int]
    execution_time_ms: float
    raw:               dict
    errors:            List[str]

    def dominant_state(self) -> str:
        if not self.measurement_counts:
            return ""
        return max(self.measurement_counts, key=self.measurement_counts.get)

    def __bool__(self) -> bool:
        return self.success


@dataclass
class GenericResult:
    success:  bool
    status:   str
    output:   Any
    raw:      dict
    errors:   List[str]

    def __bool__(self) -> bool:
        return self.success


# ── Client ─────────────────────────────────────────────────────────────────────

class RuntimeClient:
    """
    Marine Quantum Runtime client.
    Supports direct (in-process) and HTTP modes transparently.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key:  Optional[str] = None,
        mode:     str = "auto",
        timeout:  int = 30,
    ) -> None:
        """
        Args:
            base_url: HTTP base URL (e.g. "http://localhost:8000").
                      If provided, forces HTTP mode.
            api_key:  API key for X-API-Key header (HTTP mode only).
            mode:     "auto" | "direct" | "http"
                      "auto" uses direct mode if no base_url is given.
            timeout:  HTTP request timeout in seconds.
        """
        self._timeout = timeout
        self._base_url = base_url
        self._api_key  = api_key or os.environ.get("RUNTIME_API_KEY", "")

        if mode == "http" or (mode == "auto" and base_url):
            self._mode = "http"
            self._setup_http()
        else:
            self._mode = "direct"
            self._setup_direct()

    def _setup_direct(self) -> None:
        """Add repo root to sys.path so direct imports work from anywhere."""
        _root = os.path.dirname(os.path.abspath(__file__))
        if _root not in sys.path:
            sys.path.insert(0, _root)
        try:
            from invoke_runtime import invoke_runtime as _ir
            self._invoke_runtime = _ir
        except ImportError as exc:
            raise RuntimeError(
                f"Direct mode: cannot import invoke_runtime from {_root}. "
                f"Ensure the repo is cloned and you're running from the repo root. "
                f"Error: {exc}"
            )

    def _setup_http(self) -> None:
        try:
            import requests as _req
            self._requests = _req
        except ImportError:
            raise RuntimeError(
                "HTTP mode requires 'requests'. Run: pip install requests"
            )
        if not self._base_url:
            raise ValueError("HTTP mode requires base_url (e.g. 'http://localhost:8000')")

    def _http(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        url     = self._base_url.rstrip("/") + path
        headers = {"X-API-Key": self._api_key, "Content-Type": "application/json"}
        try:
            if method == "GET":
                r = self._requests.get(url, headers=headers, timeout=self._timeout)
            else:
                r = self._requests.post(url, headers=headers, json=body, timeout=self._timeout)
            r.raise_for_status()
            return r.json()
        except self._requests.exceptions.ConnectionError:
            raise RuntimeError(f"Cannot connect to {self._base_url}. Is the server running?")
        except self._requests.exceptions.Timeout:
            raise RuntimeError(f"Request timed out after {self._timeout}s")
        except self._requests.exceptions.HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}")

    # ── Public API ─────────────────────────────────────────────────────────────

    def signal(
        self,
        node_id:      str,
        energy_delta: float,
        iterations:   int,
        confidence:   float,
        variance:     float,
    ) -> SignalResult:
        """
        Classify a quantum node's state.

        Returns:
            SignalResult with .state (CONVERGED|SUSPENDED|DIVERGED),
            .sigma, .confidence, .success, .errors
        """
        payload = {
            "node_id":      node_id,
            "energy_delta": energy_delta,
            "iterations":   iterations,
            "confidence":   confidence,
            "variance":     variance,
        }
        if self._mode == "direct":
            raw = self._invoke_runtime("signal", payload)
            out = raw.get("output") or raw.get("result") or {}
        else:
            raw = self._http("POST", "/api/v1/invoke/signal",
                             {"payload": payload})
            out = raw.get("output") or {}

        ok         = raw.get("status") == "SUCCESS"
        transition = out.get("transition", {})
        ue         = out.get("uncertainty_envelope", {})

        return SignalResult(
            success    = ok,
            state      = transition.get("next", ""),
            prev       = transition.get("prev", ""),
            cause      = transition.get("cause", ""),
            confidence = ue.get("confidence", 0.0),
            sigma      = ue.get("sigma", 0.0),
            seq        = transition.get("seq", 0),
            ts         = transition.get("ts", ""),
            raw        = raw,
            errors     = raw.get("errors", []),
        )

    def execute_circuit(
        self,
        gate_sequence:       List[Dict[str, Any]],
        num_qubits:          int,
        shots:               int  = 4096,
        seed:                int  = 42,
        preferred_provider:  Optional[str] = None,
        require_simulator:   bool = True,
        require_real_hardware: bool = False,
    ) -> QuantumResult:
        """
        Execute a quantum circuit via the provider abstraction.

        Gate format: [{"gate": "h", "qubits": [0]}, {"gate": "cx", "qubits": [0, 1]}]
        Supported gates: h, x, y, z, cx, cz, swap, rx, ry, rz

        Returns:
            QuantumResult with .measurement_counts, .provider_name, .success
        """
        if self._mode == "direct":
            from src.quantum.production_runtime import production_execute
            from src.quantum.providers.base import CircuitSpec, BackendRequirements
            circuit = CircuitSpec(
                num_qubits=num_qubits, gate_sequence=gate_sequence,
                shots=shots, seed=seed,
            )
            req = BackendRequirements(
                min_qubits=num_qubits, min_shots=shots,
                preferred_provider=preferred_provider,
                require_simulator=require_simulator,
                require_real_hardware=require_real_hardware,
            )
            raw = production_execute(circuit, req)
            result = raw.get("result") or {}
        else:
            body = {
                "num_qubits": num_qubits, "gate_sequence": gate_sequence,
                "shots": shots, "seed": seed, "require_simulator": require_simulator,
                "require_real_hardware": require_real_hardware,
            }
            if preferred_provider:
                body["preferred_provider"] = preferred_provider
            raw    = self._http("POST", "/api/v1/quantum/execute", body)
            result = raw.get("result") or {}

        ok = raw.get("status") == "SUCCESS"
        return QuantumResult(
            success           = ok,
            provider_name     = result.get("provider_name", ""),
            backend_name      = result.get("backend_name", ""),
            measurement_counts= result.get("measurement_counts", {}),
            shots_used        = result.get("shots_used", 0),
            is_simulator      = result.get("is_simulator", True),
            seed              = result.get("seed"),
            execution_time_ms = result.get("execution_time_ms", 0.0),
            raw               = raw,
            errors            = raw.get("errors", []),
        )

    def invoke(self, module: str, payload: dict) -> GenericResult:
        """
        Generic invocation — any module, any payload.
        Returns the raw result wrapped in GenericResult.
        """
        if self._mode == "direct":
            raw = self._invoke_runtime(module, payload)
            out = raw.get("output") or raw.get("result")
        else:
            raw = self._http("POST", f"/api/v1/invoke/{module}", {"payload": payload})
            out = raw.get("output")

        return GenericResult(
            success = raw.get("status") == "SUCCESS",
            status  = raw.get("status", ""),
            output  = out,
            raw     = raw,
            errors  = raw.get("errors", []),
        )

    def health(self) -> dict:
        """Liveness check — no auth required in HTTP mode."""
        if self._mode == "direct":
            return {"status": "ok", "mode": "direct", "runtime": "marine-quantum-runtime"}
        return self._http("GET", "/health")

    def provider_health(self) -> List[dict]:
        """Backend availability across all 4 providers."""
        if self._mode == "direct":
            from src.quantum.providers import provider_registry
            return provider_registry.backend_health()
        return self._http("GET", "/health/providers")

    def dashboard(self) -> dict:
        """All 6 ecosystem telemetry dashboard feeds."""
        if self._mode == "direct":
            from src.runtime.capability_runtime import get_dashboard_json
            return get_dashboard_json()
        return self._http("GET", "/api/v1/dashboard")

    def __repr__(self) -> str:
        if self._mode == "direct":
            return "RuntimeClient(mode='direct')"
        return f"RuntimeClient(base_url='{self._base_url}', mode='http')"
