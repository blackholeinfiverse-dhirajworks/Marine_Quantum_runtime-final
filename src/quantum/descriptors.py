# src/quantum/descriptors.py
# QApp Descriptor layer — Phase 4: Quantum Hybrid Readiness
#
# Minimal QAppDescriptor structure for future QApp/QDApp formation.
# One descriptor registered: marine_corrosion_qapp.
#
# Purpose:
#   Prepare future QApp/QDApp formation.
#   Begin movement toward hybrid quantum-classical runtime participation.

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Any


@dataclass
class QAppDescriptor:
    """
    Minimal descriptor for a QApp module.

    Fields
    ------
    name            : str      — human-readable QApp identifier
    version         : str      — semantic version string
    input_schema    : dict     — JSON-serialisable input contract
    output_schema   : dict     — JSON-serialisable output contract
    run_fn          : Callable — entry function run(payload: dict) -> dict
    description     : str      — optional human description
    tags            : list     — optional classification tags
    """
    name:          str
    version:       str
    input_schema:  dict
    output_schema: dict
    run_fn:        Callable
    description:   str = ""
    tags:          list = field(default_factory=list)

    def run(self, payload: dict) -> dict:
        """Invoke the QApp with a validated payload."""
        return self.run_fn(payload)

    def to_dict(self) -> dict:
        return {
            "name":         self.name,
            "version":      self.version,
            "description":  self.description,
            "tags":         self.tags,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }

    def __repr__(self) -> str:
        return f"QAppDescriptor(name={self.name!r}, version={self.version!r})"


# ── Registry ───────────────────────────────────────────────────────────────────

_REGISTRY: Dict[str, QAppDescriptor] = {}


def register(descriptor: QAppDescriptor) -> None:
    """Register a QApp descriptor in the global registry."""
    if descriptor.name in _REGISTRY:
        raise ValueError(f"QApp '{descriptor.name}' is already registered.")
    _REGISTRY[descriptor.name] = descriptor
    print(f"  [REGISTRY] Registered QApp: {descriptor.name} v{descriptor.version}")


def get(name: str) -> Optional[QAppDescriptor]:
    """Retrieve a registered QApp descriptor by name."""
    return _REGISTRY.get(name)


def list_registered() -> list:
    """Return list of all registered QApp names."""
    return sorted(_REGISTRY.keys())


def invoke(name: str, payload: dict) -> dict:
    """Invoke a registered QApp by name."""
    descriptor = get(name)
    if descriptor is None:
        return {
            "status": "ERROR",
            "error":  f"QApp '{name}' not found in registry. Registered: {list_registered()}",
            "result": None,
        }
    try:
        result = descriptor.run(payload)
        return {"status": "SUCCESS", "qapp": name, "version": descriptor.version, "result": result}
    except Exception as exc:
        return {"status": "ERROR", "qapp": name, "error": str(exc), "result": None}


# ── marine_corrosion_qapp descriptor ──────────────────────────────────────────

def _marine_corrosion_run(payload: dict) -> dict:
    """
    Runtime entry for the marine corrosion signal assessment QApp.

    This is a stdlib-only implementation. When qiskit and pydantic are
    available, this delegates to the full quantum execution pipeline.
    For the canonical runtime, it delegates to the signal module.
    """
    from src.signal.signal_generator import run as signal_run
    signal_result = signal_run(payload)

    # Map signal output to corrosion intelligence envelope
    if signal_result["status"] != "SUCCESS":
        return signal_result

    event = signal_result["result"]
    transition = event.get("transition", {})
    ue         = event.get("uncertainty_envelope", {})
    next_state = transition.get("next", "UNKNOWN")

    degradation_proxy = 1.0 - ue.get("confidence", 0.5)

    return {
        "qapp_id":               "marine_corrosion_qapp",
        "contract_version":      "qapp-v1.0",
        "node_ref":              event.get("node_ref"),
        "transition_state":      next_state,
        "degradation_proxy":     round(degradation_proxy, 6),
        "sigma":                 ue.get("sigma"),
        "confidence":            ue.get("confidence"),
        "risk_level":            _map_risk(degradation_proxy),
        "action_required":       degradation_proxy >= 0.4,
        "signal":                "INCREASE_ANODE_CURRENT" if degradation_proxy >= 0.4 else "HOLD",
        "ts":                    transition.get("ts"),
        "engine_event_version":  event.get("engine_event_version"),
    }


def _map_risk(p: float) -> str:
    if p >= 0.7:  return "CRITICAL"
    if p >= 0.4:  return "ELEVATED"
    if p >= 0.2:  return "MODERATE"
    return "LOW"


MARINE_CORROSION_QAPP = QAppDescriptor(
    name="marine_corrosion_qapp",
    version="1.0.0",
    description=(
        "Quantum-assisted marine hull corrosion risk assessment. "
        "Consumes quantum node state signals and produces corrosion intelligence "
        "metrics for BHIV Core ingestion."
    ),
    tags=["marine", "corrosion", "quantum", "hull", "bhiv"],
    input_schema={
        "node_id":      {"type": "str",   "required": True,  "description": "Quantum node identifier"},
        "energy_delta": {"type": "float", "required": True,  "bounds": ">= 0.0"},
        "iterations":   {"type": "int",   "required": True,  "bounds": ">= 0"},
        "confidence":   {"type": "float", "required": True,  "bounds": "[0.0, 1.0]"},
        "variance":     {"type": "float", "required": True,  "bounds": ">= 0.0"},
    },
    output_schema={
        "qapp_id":           {"type": "str"},
        "contract_version":  {"type": "str"},
        "node_ref":          {"type": "str"},
        "transition_state":  {"type": "str",   "values": ["CONVERGED", "SUSPENDED", "DIVERGED"]},
        "degradation_proxy": {"type": "float", "bounds": "[0.0, 1.0]"},
        "sigma":             {"type": "float", "bounds": ">= 0.0"},
        "confidence":        {"type": "float", "bounds": "[0.0, 1.0]"},
        "risk_level":        {"type": "str",   "values": ["LOW", "MODERATE", "ELEVATED", "CRITICAL"]},
        "action_required":   {"type": "bool"},
        "signal":            {"type": "str",   "values": ["HOLD", "INCREASE_ANODE_CURRENT"]},
        "ts":                {"type": "str",   "format": "ISO 8601 UTC"},
    },
    run_fn=_marine_corrosion_run,
)

# Auto-register on import
register(MARINE_CORROSION_QAPP)
