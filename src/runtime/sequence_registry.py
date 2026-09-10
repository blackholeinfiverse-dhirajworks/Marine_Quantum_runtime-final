# src/runtime/sequence_registry.py
# Per-capability monotonic sequence counter.
# Isolates sequence namespaces per capability.
# No shared global counter — each capability has its own isolated counter.
# Thread-safety: not thread-safe. Caller must serialize if invoking from multiple threads.

from typing import Dict


class SequenceRegistry:
    """
    Per-capability monotonic sequence counter.

    Fixes the global seq counter bug in capability_runtime.py where
    two different capabilities shared one namespace.
    """

    def __init__(self) -> None:
        self._counters: Dict[str, int] = {}

    def next(self, capability_id: str) -> int:
        """Return next sequence number for this capability. Starts at 1."""
        if capability_id not in self._counters:
            self._counters[capability_id] = 0
        self._counters[capability_id] += 1
        return self._counters[capability_id]

    def current(self, capability_id: str) -> int:
        """Return last issued sequence number. 0 if never issued."""
        return self._counters.get(capability_id, 0)

    def reset(self, capability_id: str) -> None:
        """Reset counter for one capability. For testing only."""
        self._counters[capability_id] = 0

    def reset_all(self) -> None:
        """Reset all counters. For testing only."""
        self._counters.clear()

    def snapshot(self) -> dict:
        return dict(self._counters)
