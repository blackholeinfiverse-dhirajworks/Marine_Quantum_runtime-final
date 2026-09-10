#!/usr/bin/env python3
"""
tests/test_client.py
====================
Standalone test suite for client.py (RuntimeClient SDK).
Tests both direct mode (in-process) and HTTP mode (via FastAPI TestClient).

USAGE:
    python3 tests/test_client.py

EXIT:
    0 — all tests passed
    1 — one or more tests failed
"""

import sys
import os
import json
import types

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
os.environ.setdefault("RUNTIME_API_KEY", "test-key-ci")

from client import RuntimeClient, SignalResult, QuantumResult, GenericResult

PASS_COUNT = 0
FAIL_COUNT = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS_COUNT, FAIL_COUNT
    tag = "✅" if condition else "❌"
    suffix = f"  [{detail}]" if detail else ""
    print(f"  {tag} {label}{suffix}")
    if condition:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1


# ── Helper: HTTP mode backed by TestClient ─────────────────────────────────────

def _make_http_client() -> RuntimeClient:
    try:
        from fastapi.testclient import TestClient as FTC
        from api_server import app
    except ImportError:
        return None

    tc = FTC(app, raise_server_exceptions=True)

    class _MockRequests:
        def __init__(self, t):
            self._t = t
        def _path(self, url):
            parts = url.split("/", 3)
            return "/" + parts[-1] if len(parts) == 4 else url
        def get(self, url, **kw):
            r = self._t.get(self._path(url), headers=kw.get("headers", {}))
            return self._wrap(r)
        def post(self, url, **kw):
            r = self._t.post(self._path(url), headers=kw.get("headers", {}),
                             json=kw.get("json"))
            return self._wrap(r)
        def _wrap(self, r):
            ns = types.SimpleNamespace()
            ns.status_code = r.status_code
            ns.text = r.text
            ns.json = r.json
            ns.raise_for_status = lambda: None
            return ns

    c = RuntimeClient(base_url="http://testserver",
                      api_key="test-key-ci", mode="http")
    c._requests = _MockRequests(tc)
    return c


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_direct_mode() -> None:
    print("\n── Direct Mode ─────────────────────────────────────────")
    c = RuntimeClient(mode="direct")
    check("Client repr contains 'direct'", "direct" in repr(c))

    h = c.health()
    check("health() returns status=ok", h.get("status") == "ok")
    check("health() returns mode=direct", h.get("mode") == "direct")

    # All 3 transition states
    for node_id, conf, energy, expected in [
        ("q1", 0.92, 0.0001, "CONVERGED"),
        ("q2", 0.55, 0.0001, "SUSPENDED"),
        ("q3", 0.92, 0.05,   "DIVERGED"),
    ]:
        r = c.signal(node_id=node_id, energy_delta=energy,
                     iterations=120, confidence=conf, variance=0.002)
        check(f"signal() → {expected}", r.success and r.state == expected,
              f"got {r.state}")
        check(f"signal() returns SignalResult", isinstance(r, SignalResult))
        check(f"signal() bool(result) is True for success", bool(r))

    # sigma correctness
    r = c.signal(node_id="qs", energy_delta=0.0001, iterations=120,
                 confidence=0.92, variance=0.002)
    import math
    check("sigma == sqrt(variance)", abs(r.sigma - math.sqrt(0.002)) < 1e-6,
          f"sigma={r.sigma}")

    # Circuit execute
    ghz = [{"gate":"h","qubits":[0]},{"gate":"cx","qubits":[0,1]},
           {"gate":"cx","qubits":[1,2]}]
    qr = c.execute_circuit(num_qubits=3, gate_sequence=ghz,
                           shots=1024, seed=42, require_simulator=True)
    check("execute_circuit() succeeds", qr.success)
    check("execute_circuit() returns QuantumResult", isinstance(qr, QuantumResult))
    check("GHZ counts only 000 and 111 (real entanglement)",
          set(qr.measurement_counts.keys()).issubset({"000","111"}),
          str(qr.measurement_counts))
    check("dominant_state() works", qr.dominant_state() in ("000","111"))
    check("bool(QuantumResult) is True for success", bool(qr))

    # Provider health
    ph = c.provider_health()
    check("provider_health() returns list", isinstance(ph, list))
    statuses = {b["provider_name"]: b["status"] for b in ph}
    check("local_simulator is AVAILABLE", statuses.get("local_simulator") == "AVAILABLE")
    check("aer is AVAILABLE (qiskit-aer installed)",
          statuses.get("aer") == "AVAILABLE", statuses.get("aer","?"))

    # Generic invoke
    gi = c.invoke("signal", {"node_id":"qg","energy_delta":0.0001,
                             "iterations":50,"confidence":0.91,"variance":0.003})
    check("invoke() succeeds", gi.success)
    check("invoke() returns GenericResult", isinstance(gi, GenericResult))
    check("invoke() output is a dict", isinstance(gi.output, dict))

    # Unknown module
    bad = c.invoke("no_such_module", {})
    check("invoke() unknown module → success=False", not bad.success)
    check("invoke() unknown module → errors non-empty", len(bad.errors) > 0)

    # Validation error
    bad_sig = c.signal(node_id="qv", energy_delta=0.0001, iterations=0,
                       confidence=1.9, variance=0.002)
    check("signal() bad confidence → success=False", not bad_sig.success)
    check("signal() bad confidence → bool(result) is False", not bool(bad_sig))

    # Determinism: same input → same output 3 times
    sigs = [c.signal(node_id="qd", energy_delta=0.0001, iterations=120,
                     confidence=0.92, variance=0.002)
            for _ in range(3)]
    all_same = all(s.state == sigs[0].state and s.sigma == sigs[0].sigma
                   for s in sigs)
    check("signal() is deterministic (3 identical runs)", all_same)


def test_http_mode() -> None:
    print("\n── HTTP Mode (via FastAPI TestClient) ───────────────────")
    c = _make_http_client()
    if c is None:
        print("  ⚠️  Skipped — fastapi not installed")
        return

    h = c.health()
    check("HTTP health() returns status=ok", h.get("status") == "ok")

    r = c.signal(node_id="qhttp_01", energy_delta=0.0001,
                 iterations=120, confidence=0.92, variance=0.002)
    check("HTTP signal() → CONVERGED", r.success and r.state == "CONVERGED")
    check("HTTP sigma matches direct mode", abs(r.sigma - 0.04472136) < 1e-5,
          f"sigma={r.sigma}")

    r2 = c.signal(node_id="qhttp_02", energy_delta=0.0001,
                  iterations=80, confidence=0.55, variance=0.003)
    check("HTTP signal() → SUSPENDED", r2.success and r2.state == "SUSPENDED")

    ghz = [{"gate":"h","qubits":[0]},{"gate":"cx","qubits":[0,1]},
           {"gate":"cx","qubits":[1,2]}]
    qr = c.execute_circuit(num_qubits=3, gate_sequence=ghz,
                           shots=512, seed=42, require_simulator=True)
    check("HTTP execute_circuit() succeeds", qr.success,
          f"provider={qr.provider_name}")
    check("HTTP result schema identical to direct mode",
          hasattr(qr, "measurement_counts") and hasattr(qr, "provider_name"))

    ph = c.provider_health()
    check("HTTP provider_health() returns list", isinstance(ph, list))

    gi = c.invoke("signal", {"node_id":"qhttp_g","energy_delta":0.0001,
                             "iterations":50,"confidence":0.91,"variance":0.003})
    check("HTTP invoke() succeeds", gi.success)

    dash = c.dashboard()
    check("HTTP dashboard() returns dict with expected keys",
          isinstance(dash, dict) and "runtime_health" in dash)


def test_mode_parity() -> None:
    print("\n── Mode Parity (direct vs HTTP produce same results) ───")
    http_client = _make_http_client()
    if http_client is None:
        print("  ⚠️  Skipped — fastapi not installed")
        return

    direct = RuntimeClient(mode="direct")
    payload = dict(node_id="qparity", energy_delta=0.0001,
                   iterations=120, confidence=0.92, variance=0.002)

    rd = direct.signal(**payload)
    rh = http_client.signal(**payload)

    check("state matches across modes",
          rd.state == rh.state, f"direct={rd.state} http={rh.state}")
    check("sigma matches across modes",
          abs(rd.sigma - rh.sigma) < 1e-8, f"direct={rd.sigma} http={rh.sigma}")
    check("cause matches across modes", rd.cause == rh.cause)

    # Circuit determinism across modes with same seed
    ghz = [{"gate":"h","qubits":[0]},{"gate":"cx","qubits":[0,1]},
           {"gate":"cx","qubits":[1,2]}]
    qd = direct.execute_circuit(num_qubits=3, gate_sequence=ghz,
                                shots=1024, seed=42, require_simulator=True)
    qh = http_client.execute_circuit(num_qubits=3, gate_sequence=ghz,
                                     shots=1024, seed=42, require_simulator=True)
    check("measurement_counts identical across modes (same seed)",
          qd.measurement_counts == qh.measurement_counts,
          f"direct={qd.measurement_counts} http={qh.measurement_counts}")


def run() -> int:
    w = 60
    print(f"\n{'='*w}")
    print(f"  RuntimeClient SDK — Test Suite")
    print(f"{'='*w}")

    test_direct_mode()
    test_http_mode()
    test_mode_parity()

    print(f"\n{'='*w}")
    verdict = "ALL PASS ✅" if not FAIL_COUNT else f"{FAIL_COUNT} FAILURE(S) ❌"
    print(f"  {PASS_COUNT}/{PASS_COUNT+FAIL_COUNT} passed  |  {verdict}")
    print(f"{'='*w}\n")
    return 0 if not FAIL_COUNT else 1


if __name__ == "__main__":
    sys.exit(run())
