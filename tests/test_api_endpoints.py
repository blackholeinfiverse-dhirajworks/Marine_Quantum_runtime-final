#!/usr/bin/env python3
"""
tests/test_api_endpoints.py
===========================
Independent 27-endpoint test suite for api_server.py.
Runs against a FastAPI TestClient — no real HTTP server or network needed.

USAGE:
    # Quick (uses RUNTIME_API_KEY env var or falls back to test key)
    python3 tests/test_api_endpoints.py

    # With make
    make test-api

    # Explicit key
    RUNTIME_API_KEY=my-key python3 tests/test_api_endpoints.py

EXIT CODES:
    0 — all tests passed
    1 — one or more tests failed

For Vinayak (independent validation):
    1. Clone the repo
    2. pip install fastapi uvicorn pydantic httpx2 qiskit qiskit-aer
    3. python3 tests/test_api_endpoints.py
    4. Confirm exit 0 and 27/27 in the summary line
"""

import os
import sys

# Make repo importable from tests/ subdirectory
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

os.environ.setdefault("RUNTIME_API_KEY", "test-key-ci")
_API_KEY = os.environ["RUNTIME_API_KEY"]

try:
    from fastapi.testclient import TestClient
except ImportError:
    print("ERROR: fastapi or httpx2 not installed.")
    print("Run: pip install fastapi uvicorn pydantic httpx2")
    sys.exit(1)

try:
    import api_server
    from api_server import app
except ImportError as exc:
    print(f"ERROR: Could not import api_server: {exc}")
    print("Ensure you are running from the repo root or tests/ directory.")
    sys.exit(1)

client  = TestClient(app, raise_server_exceptions=True)
headers = {"X-API-Key": _API_KEY}

# ── Payloads ──────────────────────────────────────────────────────────────────

SIGNAL_VALID = {
    "node_id": "qnode_01", "energy_delta": 0.0001,
    "iterations": 120, "confidence": 0.92, "variance": 0.002,
}
SIGNAL_SUSPENDED = {**SIGNAL_VALID, "confidence": 0.55}
SIGNAL_DIVERGED  = {**SIGNAL_VALID, "energy_delta": 0.05}
SIGNAL_BAD_CONF  = {**SIGNAL_VALID, "confidence": 1.9}   # > 1.0 — invalid
SIGNAL_MISSING   = {k: v for k, v in SIGNAL_VALID.items() if k != "energy_delta"}

CORROSION_VALID = {
    "salinity": 35.2, "temperature_celsius": 18.5, "pH": 7.8,
    "material_oxidation_potential": 0.44, "dissolved_oxygen_mgl": 6.5,
    "current_density_mAcm2": 0.12,
}
CORROSION_BAD = {**CORROSION_VALID, "salinity": 999.0}

GHZ_CIRCUIT = {
    "num_qubits": 3, "shots": 1024, "seed": 42, "require_simulator": True,
    "gate_sequence": [
        {"gate": "h",  "qubits": [0]},
        {"gate": "cx", "qubits": [0, 1]},
        {"gate": "cx", "qubits": [1, 2]},
    ],
}

# ── Test definitions ──────────────────────────────────────────────────────────
# (method, path, headers, body, expected_http_status, description)

TESTS = [
    # ── Health (3 tests) ──────────────────────────────────────────────────────
    ("GET",  "/health",                 {},      None,             200, "Liveness — no auth required"),
    ("GET",  "/health/providers",       headers, None,             200, "Provider health — all 4 backends"),
    ("GET",  "/health/detailed",        headers, None,             200, "Detailed health + provider report"),

    # ── Signal — happy paths (3 tests) ───────────────────────────────────────
    ("POST", "/api/v1/signal",          headers, SIGNAL_VALID,     200, "Signal → CONVERGED"),
    ("POST", "/api/v1/signal",          headers, SIGNAL_SUSPENDED, 200, "Signal → SUSPENDED (low confidence)"),
    ("POST", "/api/v1/signal",          headers, SIGNAL_DIVERGED,  200, "Signal → DIVERGED (high energy_delta)"),

    # ── Signal — validation errors (2 tests) ─────────────────────────────────
    ("POST", "/api/v1/signal",          headers, SIGNAL_BAD_CONF,  422, "Signal validation error: confidence > 1.0"),
    ("POST", "/api/v1/signal",          headers, SIGNAL_MISSING,   422, "Signal missing required field"),

    # ── Quantum pipeline (2 tests) ────────────────────────────────────────────
    ("POST", "/api/v1/quantum/corrosion", headers, CORROSION_VALID, 200, "Quantum corrosion assessment"),
    ("POST", "/api/v1/quantum/corrosion", headers, CORROSION_BAD,   422, "Corrosion out-of-range salinity"),

    # ── Circuit execute (1 test) ──────────────────────────────────────────────
    ("POST", "/api/v1/quantum/execute", headers, GHZ_CIRCUIT,     200, "GHZ circuit via Aer (real qiskit)"),

    # ── Provider info (1 test) ────────────────────────────────────────────────
    ("GET",  "/api/v1/quantum/providers", headers, None,           200, "Provider capabilities + noise + HW constraints"),

    # ── Capability platform (3 tests) ─────────────────────────────────────────
    ("GET",  "/api/v1/capabilities",    headers, None,             200, "List registered capabilities"),
    ("POST", "/api/v1/capability/signal", headers,
             {"payload": SIGNAL_VALID},                            200, "Capability platform full stack"),
    ("POST", "/api/v1/capability/no_such_capability", headers,
             {"payload": {}},                                      404, "Unknown capability → 404"),

    # ── Legacy module invoke (2 tests) ───────────────────────────────────────
    ("POST", "/api/v1/invoke/signal",   headers,
             {"payload": SIGNAL_VALID},                            200, "Legacy module invoke — signal"),
    ("POST", "/api/v1/invoke/bad_mod",  headers,
             {"payload": {}},                                      404, "Unknown module → 404 (not 500)"),

    # ── Observability (2 tests) ───────────────────────────────────────────────
    ("GET",  "/api/v1/dashboard",       headers, None,             200, "Dashboard — all 6 telemetry feeds"),
    ("GET",  "/api/v1/queue",            headers, None,             200, "Queue status"),

    # ── Governance (5 tests) ─────────────────────────────────────────────────
    ("GET",  "/api/v1/governance/authority-matrix", headers, None, 200, "Authority matrix (ceilings + negative authority)"),
    ("GET",  "/api/v1/governance/decision-ledger",  headers, None, 200, "Decision ledger summary"),
    ("GET",  "/api/v1/governance/doctrines",        headers, None, 200, "Doctrine evaluation"),
    ("GET",  "/api/v1/governance/replay-stats",     headers, None, 200, "Replay authority statistics"),
    ("GET",  "/api/v1/governance/provenance",       headers, None, 200, "Provenance / evidence status"),

    # ── Auth (2 tests) ────────────────────────────────────────────────────────
    ("GET",  "/api/v1/capabilities",    {},      None,             401, "Missing API key → 401"),
    ("POST", "/api/v1/signal", {"X-API-Key": "wrong-key"},
             SIGNAL_VALID,                                         401, "Wrong API key → 401"),
]


# ── Runner ────────────────────────────────────────────────────────────────────

def _extract_note(resp) -> str:
    try:
        rj  = resp.json()
        out = rj.get("output", rj.get("result", {}))
        if isinstance(out, dict):
            if "transition" in out:
                return f"→ {out['transition']['next']}"
            if "deterministic_event" in out:
                return f"→ risk={out['deterministic_event']['risk_level']}"
        if "measurement_counts" in rj.get("result", {}):
            counts = rj["result"]["measurement_counts"]
            dominant = max(counts, key=counts.get)
            return f"→ dominant={dominant}"
        if "status" in rj and rj["status"] not in ("SUCCESS", "ok"):
            return f"→ {rj['status']}"
    except Exception:
        pass
    return ""


def run() -> int:
    w = 72
    print(f"\n{'='*w}")
    print(f"  Marine Quantum Runtime — API Endpoint Test Suite")
    print(f"  {len(TESTS)} tests | key={_API_KEY[:8]}...")
    print(f"{'='*w}")

    pass_count = fail_count = 0

    for method, path, hdrs, body, expected, label in TESTS:
        try:
            if method == "GET":
                resp = client.get(path, headers=hdrs)
            else:
                resp = client.post(path, headers=hdrs, json=body)
            ok = resp.status_code == expected
        except Exception as exc:
            ok   = False
            resp = type("R", (), {"status_code": 0, "json": lambda: {"error": str(exc)}})()

        tag  = "✅" if ok else "❌"
        note = _extract_note(resp) if ok else f"→ got {resp.status_code}"
        print(f"  {tag} {resp.status_code:3} (want {expected:3})  {label:<50} {note}")

        if ok:
            pass_count += 1
        else:
            fail_count += 1
            try:
                body_text = str(resp.json())[:120]
                print(f"       BODY: {body_text}")
            except Exception:
                pass

    print(f"\n{'='*w}")
    verdict = "ALL PASS ✅" if not fail_count else f"{fail_count} FAILURE(S) ❌"
    print(f"  {pass_count}/{pass_count + fail_count} passed  |  {verdict}")
    print(f"{'='*w}\n")

    return 0 if not fail_count else 1


if __name__ == "__main__":
    sys.exit(run())
