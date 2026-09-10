# Provenance Model — Marine Intelligence System
**Author:** Dhiraj Chavan | BHIV Core / TANTRA Ecosystem  
**Version:** 1.0.0

---

## The Core Question: What Is Replayable?

Not all executions are replayable. The provenance model makes this distinction explicit rather than assuming it.

| Concept | Definition |
|---|---|
| **Replayable** | Given the same `RuntimeRequest`, the same `RuntimeResponse` will be produced. The function is deterministic. Classical signal participant is replayable. |
| **Reconstructable** | The execution trace can be rebuilt from the lineage record, but the exact output may differ. Quantum simulation with same seed is reconstructable. Real QPU output is not. |
| **Truth** | The original execution result, captured in `output_hash` within the lineage record. Truth is immutable. Replay verifies against truth; it does not replace it. |

---

## Lineage Chain

Every runtime invocation produces a lineage chain:

```
RuntimeRequest
    → ModuleDescriptorContract (descriptor_id)
    → classical ModuleExecutionTrace (REPLAYABLE)
    → quantum ModuleExecutionTrace (RECONSTRUCTABLE)
    → RuntimeLineageRecord (sealed, chain_hash)
    → ExecutionLineage (session store)
```

Each link in the chain is SHA-256 anchored. The `chain_hash` at the end covers all trace IDs in sequence.

---

## Determinism Classes for Traces

| Class | Meaning | Replay Guarantee |
|---|---|---|
| `REPLAYABLE` | Same input → identical output | Full bit-identical replay |
| `RECONSTRUCTABLE` | Same seed/state → structurally equivalent output | Content-equivalent, not bit-identical |
| `NON_DETERMINISTIC` | Output varies per run | No replay guarantee; truth record only |

A `RuntimeLineageRecord.is_replayable` returns `True` only if ALL traces are `REPLAYABLE`. The hybrid lineage record is `False` by design (quantum trace is `RECONSTRUCTABLE`).

---

## Classes

### `ModuleExecutionTrace`
Single-module execution snapshot. Fields: `trace_id`, `module_name`, `request_id`, `response_id`, `input_hash`, `output_hash`, `determinism_class`, `execution_status`, `failure_summary`.

### `RuntimeLineageRecord`
Append-only container for one end-to-end invocation's traces. Sealed with `seal()` to produce `chain_hash`. No mutation after sealing.

### `ExecutionLineage`
Session-level append-only store. One per runtime session. No deletion or overwrite permitted.

---

## What Provenance Does NOT Do

- It does not trigger replay automatically.
- It does not validate that a replay result matches truth (that is the caller's responsibility).
- It does not persist to disk (in-memory by design for this runtime).
- It does not propagate across process restarts.
