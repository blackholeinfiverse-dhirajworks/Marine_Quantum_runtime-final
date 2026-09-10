# src/runtime/distributed_runtime_manager.py
# Distributed Quantum Runtime Manager — Phase 3.
#
# Generalizes the existing 3-node propagation pattern (Node_A/B/C in
# src/runtime/nodes.py, built for Task 9's classical signal propagation)
# into an N-node job execution manager for quantum circuits routed through
# the provider abstraction (Phase 1).
#
# Supports: multiple execution nodes, distributed routing, backend selection,
# provider failover, execution scheduling, execution queues, circuit routing,
# job lifecycle, execution cancellation, status monitoring, retry policy.
#
# No real network — this is an in-process, deterministic multi-node simulation,
# the same honest pattern as the existing Node_A/B/C propagation layer. Declared
# explicitly in KNOWN_LIMITATIONS.md, not hidden.

import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Deque, Dict, List, Optional

from src.quantum.providers.base import BackendRequirements, CircuitSpec, JobStatus
from src.quantum.providers.quantum_execution_router import route_and_execute

_ANCHOR = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _sha256(d: str) -> str:
    return hashlib.sha256(d.encode("utf-8")).hexdigest()


def _ts(seq: int) -> str:
    return (_ANCHOR + timedelta(seconds=seq * 60)).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RetryPolicy:
    max_retries:        int = 2
    backoff_seconds:    float = 0.0   # deterministic — not real sleep in tests

    def to_dict(self) -> dict:
        return {"max_retries": self.max_retries, "backoff_seconds": self.backoff_seconds}


@dataclass
class RuntimeNode:
    """A logical execution node. In-process, not a real network host."""
    node_id:        str
    max_concurrent:  int = 4
    active_jobs:     int = 0

    def can_accept(self) -> bool:
        return self.active_jobs < self.max_concurrent

    def to_dict(self) -> dict:
        return {"node_id": self.node_id, "max_concurrent": self.max_concurrent,
                "active_jobs": self.active_jobs}


@dataclass
class Job:
    job_id:          str
    circuit:          CircuitSpec
    requirements:      BackendRequirements
    status:            JobStatus
    node_id:           Optional[str]
    retry_policy:       RetryPolicy
    retries_used:       int = 0
    result:             Optional[dict] = None
    error:              Optional[str] = None
    submitted_seq:      int = 0
    completed_seq:      Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "job_id":        self.job_id,
            "status":        self.status.value,
            "node_id":       self.node_id,
            "retries_used":  self.retries_used,
            "result":        self.result,
            "error":         self.error,
            "submitted_ts":  _ts(self.submitted_seq),
            "completed_ts":  _ts(self.completed_seq) if self.completed_seq else None,
        }


class DistributedRuntimeManager:
    """
    Manages job submission, queueing, node routing, and lifecycle for
    circuit execution requests across N logical nodes.
    """

    def __init__(self, node_ids: Optional[List[str]] = None) -> None:
        node_ids = node_ids or ["node_1", "node_2", "node_3"]
        self._nodes: Dict[str, RuntimeNode] = {nid: RuntimeNode(node_id=nid) for nid in node_ids}
        self._queue: Deque[str]            = deque()
        self._jobs:  Dict[str, Job]        = {}
        self._seq:   int                   = 0
        self._events: List[dict]           = []
        self._rr_index: int                = 0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _emit_event(self, event_type: str, **kwargs) -> None:
        self._events.append({"event_type": event_type, "seq": self._seq, **kwargs})

    def add_node(self, node_id: str, max_concurrent: int = 4) -> None:
        self._nodes[node_id] = RuntimeNode(node_id=node_id, max_concurrent=max_concurrent)

    def remove_node(self, node_id: str) -> None:
        if node_id in self._nodes:
            del self._nodes[node_id]

    def list_nodes(self) -> List[dict]:
        return [n.to_dict() for n in self._nodes.values()]

    def _select_node(self) -> Optional[RuntimeNode]:
        """
        Deterministic round-robin across nodes that can accept work.
        Advances a persistent index so consecutive submissions visibly
        distribute across nodes rather than always landing on the first
        node with equal (zero) active_jobs in this synchronous model.
        """
        node_list = list(self._nodes.values())
        if not node_list:
            return None
        n = len(node_list)
        for offset in range(n):
            idx = (self._rr_index + offset) % n
            candidate = node_list[idx]
            if candidate.can_accept():
                self._rr_index = (idx + 1) % n
                return candidate
        return None

    def submit_job(
        self,
        circuit: CircuitSpec,
        requirements: Optional[BackendRequirements] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> str:
        seq = self._next_seq()
        job_id = _sha256(f"job:{seq}:{json.dumps(circuit.to_dict(), sort_keys=True)}")
        job = Job(
            job_id=job_id, circuit=circuit,
            requirements=requirements or BackendRequirements(min_qubits=circuit.num_qubits),
            status=JobStatus.QUEUED, node_id=None,
            retry_policy=retry_policy or RetryPolicy(), submitted_seq=seq,
        )
        self._jobs[job_id] = job
        self._queue.append(job_id)
        self._emit_event("JOB_SUBMITTED", job_id=job_id)
        return job_id

    def cancel_job(self, job_id: str) -> dict:
        job = self._jobs.get(job_id)
        if not job:
            return {"status": "NOT_FOUND", "job_id": job_id}
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return {"status": "ALREADY_TERMINAL", "job_id": job_id, "current_status": job.status.value}
        job.status = JobStatus.CANCELLED
        job.completed_seq = self._next_seq()
        if job_id in self._queue:
            self._queue.remove(job_id)
        self._emit_event("JOB_CANCELLED", job_id=job_id)
        return {"status": "CANCELLED", "job_id": job_id}

    def get_job_status(self, job_id: str) -> Optional[dict]:
        job = self._jobs.get(job_id)
        return job.to_dict() if job else None

    def process_queue(self) -> List[dict]:
        """
        Process all currently queued jobs: route each to a node, execute via
        the provider abstraction, apply retry policy on failure, record
        outcome. Returns list of processed job results.
        """
        processed = []
        # Snapshot the queue — new submissions during processing go to next batch
        batch = list(self._queue)
        self._queue.clear()

        for job_id in batch:
            job = self._jobs[job_id]
            if job.status == JobStatus.CANCELLED:
                continue

            node = self._select_node()
            if node is None:
                # No capacity — requeue for next process_queue() call
                self._queue.append(job_id)
                self._emit_event("JOB_REQUEUED_NO_CAPACITY", job_id=job_id)
                continue

            job.status = JobStatus.ROUTING
            job.node_id = node.node_id
            node.active_jobs += 1
            self._emit_event("JOB_ROUTED", job_id=job_id, node_id=node.node_id)

            job.status = JobStatus.RUNNING
            self._emit_event("JOB_RUNNING", job_id=job_id, node_id=node.node_id)

            outcome = self._execute_with_retry(job)
            node.active_jobs -= 1

            if outcome["status"] == "SUCCESS":
                job.status = JobStatus.COMPLETED
                job.result = outcome["result"]
                self._emit_event("JOB_COMPLETED", job_id=job_id, node_id=node.node_id)
            else:
                job.status = JobStatus.FAILED
                job.error = "; ".join(outcome.get("errors", ["unknown failure"]))
                self._emit_event("JOB_FAILED", job_id=job_id, node_id=node.node_id, error=job.error)

            job.completed_seq = self._next_seq()
            processed.append(job.to_dict())

        return processed

    def _execute_with_retry(self, job: Job) -> dict:
        last_outcome = None
        for attempt in range(job.retry_policy.max_retries + 1):
            outcome = route_and_execute(job.circuit, job.requirements)
            last_outcome = outcome
            if outcome["status"] == "SUCCESS":
                return outcome
            job.retries_used = attempt
            self._emit_event("JOB_RETRY", job_id=job.job_id, attempt=attempt,
                             reason=outcome.get("errors"))
        return last_outcome

    def queue_statistics(self) -> dict:
        statuses: Dict[str, int] = {}
        for job in self._jobs.values():
            statuses[job.status.value] = statuses.get(job.status.value, 0) + 1
        return {
            "queued":           len(self._queue),
            "total_jobs":       len(self._jobs),
            "by_status":        statuses,
            "nodes":            self.list_nodes(),
        }

    def event_log(self, limit: Optional[int] = None) -> List[dict]:
        return self._events[-limit:] if limit else list(self._events)
