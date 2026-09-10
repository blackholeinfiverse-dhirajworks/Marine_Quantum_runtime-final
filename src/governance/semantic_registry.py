# src/governance/semantic_registry.py
# Semantic Registry — domain meaning of capability outputs.
# Not what a capability does. What its outputs mean in the hull-corrosion domain.
# Invariant checking is advisory, not halting.

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SemanticDescriptor:
    capability_id:      str
    domain:             str
    output_semantics:   Dict[str, str]
    invariants:         List[str]
    assumptions:        List[str]
    known_limitations:  List[str]

    def to_dict(self) -> dict:
        return {
            "capability_id":     self.capability_id,
            "domain":            self.domain,
            "output_semantics":  self.output_semantics,
            "invariants":        self.invariants,
            "assumptions":       self.assumptions,
            "known_limitations": self.known_limitations,
        }


class SemanticRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, SemanticDescriptor] = {}

    def register(self, descriptor: SemanticDescriptor) -> None:
        if descriptor.capability_id in self._registry:
            raise ValueError(
                f"Semantic descriptor for '{descriptor.capability_id}' already registered."
            )
        self._registry[descriptor.capability_id] = descriptor

    def get(self, capability_id: str) -> Optional[SemanticDescriptor]:
        return self._registry.get(capability_id)

    def list_all(self) -> List[dict]:
        return [d.to_dict() for d in self._registry.values()]

    def check_invariant(self, capability_id: str, output: dict) -> dict:
        """Advisory invariant check. Does not raise. Returns violations list."""
        desc = self.get(capability_id)
        if not desc:
            return {"valid": True, "violations": [],
                    "note": f"No semantic descriptor for '{capability_id}'"}
        violations = []
        # confidence invariant
        ue = output.get("uncertainty_envelope", {})
        if "confidence" in ue:
            if not (0.0 <= ue["confidence"] <= 1.0):
                violations.append("confidence out of [0.0, 1.0]")
        if "sigma" in ue:
            if ue["sigma"] < 0:
                violations.append("sigma < 0")
        # transition state invariant
        t = output.get("transition", {})
        if "next" in t:
            if t["next"] not in ("CONVERGED", "SUSPENDED", "DIVERGED"):
                violations.append(f"transition.next='{t['next']}' not in valid set")
        return {"valid": len(violations) == 0, "violations": violations}


# ── Module-level singleton ─────────────────────────────────────────────────────
_REGISTRY = SemanticRegistry()

_REGISTRY.register(SemanticDescriptor(
    capability_id="signal",
    domain="marine.quantum.node.state",
    output_semantics={
        "transition.next":              "Quantum node convergence state: CONVERGED=stable, SUSPENDED=uncertain, DIVERGED=unstable",
        "uncertainty_envelope.sigma":   "Standard deviation of quantum state variance (sqrt of input variance)",
        "uncertainty_envelope.confidence": "Operator confidence in node state [0,1]",
        "transition.ts":                "Synthetic timestamp: anchor + (iterations * 60s). NOT wall-clock.",
    },
    invariants=[
        "sigma = sqrt(variance) always",
        "confidence in [0.0, 1.0] always",
        "sigma >= 0.0 always",
        "transition.next in {CONVERGED, SUSPENDED, DIVERGED} always",
        "transition.prev in {INITIALISING, ACTIVE} always",
    ],
    assumptions=[
        "iterations=0 implies node is in first execution cycle",
        "energy_delta=0.0 implies no energy change since last timestep",
        "confidence and variance are externally computed, not derived here",
    ],
    known_limitations=[
        "ts is synthetic — not wall-clock time",
        "seq monotonicity is caller-managed, not enforced by signal layer",
        "iterations=0 + CONVERGED is semantically inconsistent in real physics",
        "VQE pipeline upstream is design-only — parameters are externally supplied",
    ],
))

_REGISTRY.register(SemanticDescriptor(
    capability_id="quantum_pipeline",
    domain="marine.corrosion.quantum.assessment",
    output_semantics={
        "degradation_probability":            "Hull material degradation probability [0,1] — Hamming-weighted from quantum measurement",
        "confidence_score":                   "Entropy-based confidence in measurement [0,1] — 1=peaked distribution",
        "recommended_anode_current":          "Cathodic protection anode current in mA",
        "dominant_state":                     "Most probable quantum measurement bitstring",
        "deterministic_event.risk_level":     "Threshold-classified risk: LOW/MODERATE/ELEVATED/CRITICAL",
        "deterministic_event.signal":         "Actuator signal: HOLD or INCREASE_ANODE_CURRENT",
    },
    invariants=[
        "degradation_probability in [0.0, 1.0] always",
        "confidence_score in [0.0, 1.0] always",
        "confidence_score >= 0.5 required for valid output (contract rule R4)",
        "recommended_anode_current >= 0 always",
        "measurement_distribution sums to 1.0 (±0.01)",
    ],
    assumptions=[
        "seed=42 produces deterministic simulation output",
        "Classical simulation stub used — not real quantum hardware",
    ],
    known_limitations=[
        "Classical simulation stub — not real quantum execution",
        "HEA circuit topology not fitted to electrochemical Hamiltonian",
        "Real QPU output would be NON_DETERMINISTIC",
    ],
))


def get(capability_id: str) -> Optional[SemanticDescriptor]:
    return _REGISTRY.get(capability_id)


def list_all() -> List[dict]:
    return _REGISTRY.list_all()


def check_invariant(capability_id: str, output: dict) -> dict:
    return _REGISTRY.check_invariant(capability_id, output)
