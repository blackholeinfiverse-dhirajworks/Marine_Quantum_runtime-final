# src/contracts/typed_attachment.py
# Typed Attachment Validation — checks types, bounds, and constraints.
# Fixes the key-presence-only bug in runtime_capability_registry.validate_attachment().
#
# validate_typed(capability_id, payload) -> {valid, errors, missing}

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type


@dataclass
class FieldSpec:
    """Typed specification for a single input field."""
    name:        str
    type_:       Type
    required:    bool                         = True
    bounds:      Optional[tuple]              = None     # (min, max) inclusive
    validator:   Optional[Callable[[Any], bool]] = None
    description: str                          = ""

    def check(self, value: Any) -> List[str]:
        errors = []
        # Numeric coercion (int/float cross-compatibility)
        if not isinstance(value, self.type_):
            if self.type_ in (float, int) and isinstance(value, (int, float)):
                try:
                    value = self.type_(value)
                except (TypeError, ValueError):
                    errors.append(
                        f"Cannot coerce {type(value).__name__} to {self.type_.__name__}"
                    )
                    return errors
            else:
                errors.append(
                    f"Expected {self.type_.__name__}, got {type(value).__name__}"
                )
                return errors
        # Bounds check
        if self.bounds is not None:
            lo, hi = self.bounds
            if lo is not None and value < lo:
                errors.append(f"Value {value} below minimum {lo}")
            if hi is not None and value > hi:
                errors.append(f"Value {value} above maximum {hi}")
        # Custom validator
        if self.validator is not None:
            try:
                if not self.validator(value):
                    errors.append(f"Failed custom validation for '{self.name}'")
            except Exception as exc:
                errors.append(f"Validator raised: {exc}")
        return errors


# ── Built-in typed schemas ─────────────────────────────────────────────────────

SIGNAL_SCHEMA: Dict[str, FieldSpec] = {
    "node_id": FieldSpec(
        name="node_id", type_=str, required=True,
        validator=lambda v: len(v.strip()) > 0,
        description="Non-empty quantum node identifier",
    ),
    "energy_delta": FieldSpec(
        name="energy_delta", type_=float, required=True,
        bounds=(0.0, None),
        description="Energy delta >= 0.0",
    ),
    "iterations": FieldSpec(
        name="iterations", type_=int, required=True,
        bounds=(0, 1_000_000),
        description="Iteration count >= 0",
    ),
    "confidence": FieldSpec(
        name="confidence", type_=float, required=True,
        bounds=(0.0, 1.0),
        description="Confidence in [0.0, 1.0]",
    ),
    "variance": FieldSpec(
        name="variance", type_=float, required=True,
        bounds=(0.0, None),
        description="Variance >= 0.0",
    ),
}

DISTRIBUTED_QAPP_SCHEMA: Dict[str, FieldSpec] = {
    "qapp_id": FieldSpec(
        name="qapp_id", type_=str, required=True,
        validator=lambda v: len(v.strip()) > 0,
        description="Non-empty QApp identifier",
    ),
    "node_origin": FieldSpec(
        name="node_origin", type_=str, required=True,
        validator=lambda v: len(v.strip()) > 0,
        description="Origin node identifier",
    ),
    "sequence_id": FieldSpec(
        name="sequence_id", type_=int, required=True,
        bounds=(1, 1_000_000),
        description="Sequence ID >= 1",
    ),
    "data": FieldSpec(
        name="data", type_=dict, required=True,
        description="Signal payload dict",
    ),
}

QUANTUM_PIPELINE_SCHEMA: Dict[str, FieldSpec] = {
    "salinity": FieldSpec(
        name="salinity", type_=float, required=True,
        bounds=(0.0, 50.0), description="Salinity in [0, 50] ppt",
    ),
    "temperature_celsius": FieldSpec(
        name="temperature_celsius", type_=float, required=True,
        bounds=(-5.0, 45.0), description="Temperature in [-5, 45] °C",
    ),
    "pH": FieldSpec(
        name="pH", type_=float, required=True,
        bounds=(0.0, 14.0), description="pH in [0, 14]",
    ),
    "material_oxidation_potential": FieldSpec(
        name="material_oxidation_potential", type_=float, required=True,
        bounds=(-2.0, 2.0), description="Oxidation potential in [-2, 2] V",
    ),
    "dissolved_oxygen_mgl": FieldSpec(
        name="dissolved_oxygen_mgl", type_=float, required=True,
        bounds=(0.0, 20.0), description="Dissolved oxygen in [0, 20] mg/L",
    ),
    "current_density_mAcm2": FieldSpec(
        name="current_density_mAcm2", type_=float, required=True,
        bounds=(0.0, 10.0), description="Current density in [0, 10] mA/cm²",
    ),
}

_SCHEMAS: Dict[str, Dict[str, FieldSpec]] = {
    "signal":            SIGNAL_SCHEMA,
    "distributed_qapp":  DISTRIBUTED_QAPP_SCHEMA,
    "quantum_pipeline":  QUANTUM_PIPELINE_SCHEMA,
}


def validate_typed(capability_id: str, payload: dict) -> dict:
    """
    Full typed validation of a capability payload.
    Returns {valid, errors, missing}.
    
    Supersedes key-presence-only checks.
    """
    schema = _SCHEMAS.get(capability_id)
    if not schema:
        return {
            "valid":   True,
            "errors":  [],
            "missing": [],
            "note":    f"No typed schema for '{capability_id}' — key-presence check only",
        }
    errors  = []
    missing = []
    for field_name, spec in schema.items():
        if field_name not in payload:
            if spec.required:
                missing.append(field_name)
            continue
        for err in spec.check(payload[field_name]):
            errors.append(f"Field '{field_name}': {err}")
    return {
        "valid":   len(errors) == 0 and len(missing) == 0,
        "errors":  errors,
        "missing": missing,
    }


def register_schema(capability_id: str, schema: Dict[str, FieldSpec]) -> None:
    """Register a typed schema for a capability not in the built-in set."""
    _SCHEMAS[capability_id] = schema


def get_schema(capability_id: str) -> Optional[Dict[str, FieldSpec]]:
    return _SCHEMAS.get(capability_id)
