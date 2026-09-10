# Hybrid Participation Model — Marine Intelligence System
**Author:** Dhiraj Chavan | BHIV Core / TANTRA Ecosystem  
**Version:** 1.0.0

---

## What Makes a Participant "Hybrid Compliant"

A participant is hybrid compliant if and only if:

1. It has a registered `QAppDescriptor` with `capability_class` in `("CLASSICAL", "QUANTUM", "HYBRID")`.
2. It accepts a `RuntimeRequest` envelope as its invocation surface.
3. It returns a `RuntimeResponse` envelope as its result surface.
4. It declares a `determinism_class` for its `ModuleExecutionTrace`.
5. Its `authority_ceiling` is `RUNTIME_PARTICIPATE` or higher.
6. It declares its `known_limitations` explicitly — no silent capability claims.

---

## Minimum Hybrid Runtime Requirements

A hybrid execution requires:
- **At least one CLASSICAL participant** — deterministic, REPLAYABLE.
- **At least one QUANTUM participant** — simulation or hardware, RECONSTRUCTABLE or NON_DETERMINISTIC.
- **Shared `RuntimeRequest`** — both participants receive the same request envelope.
- **Shared lineage record** — both participants' traces are captured in one `RuntimeLineageRecord`.

---

## What Surfaces Are Shared

| Surface | Shared |
|---|---|
| `RuntimeRequest` envelope | ✅ Shared — same request_id for both participants |
| `RuntimeResponse` envelope format | ✅ Shared — same schema |
| `ModuleExecutionTrace` format | ✅ Shared — same fields |
| `RuntimeLineageRecord` | ✅ Shared — both traces appended |
| Internal computation logic | ❌ Producer-specific |
| Optimiser selection | ❌ Producer-specific |
| Hardware backend | ❌ Producer-specific |
| Internal state management | ❌ Producer-specific |

---

## What Remains Producer-Specific

The hybrid contract governs the **surface** — not the internals. Each participant owns:
- Its computation algorithm (VQE, transition table, drift detection, etc.)
- Its optimiser choices (COBYLA, L-BFGS-B, etc.)
- Its hardware backend selection (AerSimulator, real QPU, classical CPU)
- Its internal state (the classical participant maintains no state between calls; the quantum stub is stateless)

This is intentional. Hybrid compliance is an interface contract, not an implementation mandate.

---

## We Are NOT Claiming

- Real quantum supremacy over classical methods.
- That the quantum participant provides better results than a classical equivalent.
- That the two participants are synchronised in time.
- That the hybrid execution is faster than classical-only execution.

We ARE proving:
- Both participants share a runtime contract.
- Both produce contract-compliant results.
- Both traces are captured in a sealed, auditable lineage record.
- The boundary between classical determinism and quantum reconstruction is explicitly declared.
