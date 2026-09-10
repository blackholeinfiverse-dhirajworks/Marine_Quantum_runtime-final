# src/governance/doctrine_registry.py
# Doctrine Registry — immutable design rules enforced at runtime boundary.
# Each doctrine is a named, versioned, checkable rule.
# evaluate_all(context) -> {all_passed, violations, results}

from dataclasses import dataclass
from typing import Callable, Dict, List


@dataclass(frozen=True)
class Doctrine:
    name:              str
    version:           str
    description:       str
    check:             Callable[[dict], bool]
    violation_message: str

    def evaluate(self, context: dict) -> dict:
        try:
            passed = self.check(context)
        except Exception as exc:
            return {"doctrine": self.name, "passed": False, "version": self.version,
                    "reason": f"Doctrine check raised exception: {exc}"}
        return {
            "doctrine": self.name,
            "passed":   passed,
            "version":  self.version,
            "reason":   "OK" if passed else self.violation_message,
        }


class DoctrineRegistry:
    def __init__(self) -> None:
        self._doctrines: Dict[str, Doctrine] = {}

    def register(self, doctrine: Doctrine) -> None:
        if doctrine.name in self._doctrines:
            raise ValueError(f"Doctrine '{doctrine.name}' already registered.")
        self._doctrines[doctrine.name] = doctrine

    def evaluate_all(self, context: dict) -> dict:
        results    = [d.evaluate(context) for d in self._doctrines.values()]
        all_passed = all(r["passed"] for r in results)
        violations = [r for r in results if not r["passed"]]
        return {
            "all_passed": all_passed,
            "violations": violations,
            "results":    results,
            "total":      len(results),
        }

    def evaluate_one(self, name: str, context: dict) -> dict:
        if name not in self._doctrines:
            return {"error": f"Doctrine '{name}' not registered"}
        return self._doctrines[name].evaluate(context)

    def list_doctrines(self) -> List[dict]:
        return [
            {"name": d.name, "version": d.version, "description": d.description}
            for d in self._doctrines.values()
        ]


# ── Module-level singleton + built-in doctrines ────────────────────────────────
_REGISTRY = DoctrineRegistry()

_REGISTRY.register(Doctrine(
    name="NO_DATETIME_NOW",
    version="1.0.0",
    description="Timestamps must be deterministic anchor+offset. Never wall-clock.",
    check=lambda ctx: ctx.get("timestamp_posture", "DETERMINISTIC") != "WALL_CLOCK",
    violation_message="timestamp_posture=WALL_CLOCK detected. Use anchor + (iterations × 60s).",
))

_REGISTRY.register(Doctrine(
    name="NO_SILENT_FAILURE",
    version="1.0.0",
    description="All failures must surface explicitly. No silent catch-and-continue.",
    check=lambda ctx: ctx.get("silent_failure", False) is False,
    violation_message="silent_failure=True detected. All failures must propagate.",
))

_REGISTRY.register(Doctrine(
    name="NEGATIVE_AUTHORITY_REQUIRED",
    version="1.0.0",
    description="Every capability descriptor must declare at least one negative authority.",
    check=lambda ctx: len(ctx.get("negative_authority", [])) > 0,
    violation_message="No negative_authority declared. At least one entry required.",
))

_REGISTRY.register(Doctrine(
    name="SHA256_IDS_ONLY",
    version="1.0.0",
    description="All IDs must be SHA-256 derived. No UUID, no OS entropy, no random.",
    check=lambda ctx: ctx.get("id_generation", "SHA256") == "SHA256",
    violation_message="Non-SHA-256 ID generation detected.",
))

_REGISTRY.register(Doctrine(
    name="APPEND_ONLY_LOGS",
    version="1.0.0",
    description="All event logs and ledgers must be append-only. No mutation or deletion.",
    check=lambda ctx: ctx.get("log_type", "append_only") == "append_only",
    violation_message="Non-append-only log detected.",
))

_REGISTRY.register(Doctrine(
    name="STUBS_MUST_BE_DECLARED",
    version="1.0.0",
    description="Every stub must appear in STUBS_REGISTRY.md. Undeclared stubs are defects.",
    check=lambda ctx: ctx.get("stub_declared", True) is True,
    violation_message="Undeclared stub detected. Add to STUBS_REGISTRY.md before merging.",
))

_REGISTRY.register(Doctrine(
    name="TYPED_ATTACHMENT_REQUIRED",
    version="1.0.0",
    description="Attachment validation must check types and bounds, not only key presence.",
    check=lambda ctx: ctx.get("attachment_typed", True) is True,
    violation_message="Key-only attachment validation detected. Types and bounds must be checked.",
))

_REGISTRY.register(Doctrine(
    name="DEPENDENCY_GRAPH_ENFORCED",
    version="1.0.0",
    description="All declared capability dependencies must be registered before invocation.",
    check=lambda ctx: ctx.get("dependency_graph_enforced", True) is True,
    violation_message="Dependency graph not enforced. Undeclared dependencies may cause silent failures.",
))


def evaluate_all(context: dict) -> dict:
    return _REGISTRY.evaluate_all(context)


def evaluate_one(name: str, context: dict) -> dict:
    return _REGISTRY.evaluate_one(name, context)


def list_doctrines() -> List[dict]:
    return _REGISTRY.list_doctrines()
