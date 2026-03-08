# event_bus.py
# ─────────────────────────────────────────────────────────────────────────────
# Shared SSE event bus for Fan360 Control Room
# Both orchestrator.py and webhook_server.py import from here — no circular deps
#
# BROADCAST model — each SSE client gets its own queue so every client
# receives every event (solves the single-consumer problem).
# ─────────────────────────────────────────────────────────────────────────────

import json, time, queue, threading

# Set of per-client queues — protected by a lock
_clients: set[queue.Queue] = set()
_lock = threading.Lock()


def subscribe() -> queue.Queue:
    """Register a new SSE client and return its personal queue."""
    q = queue.Queue()
    with _lock:
        _clients.add(q)
    return q


def unsubscribe(q: queue.Queue):
    """Remove a client queue when the SSE connection closes."""
    with _lock:
        _clients.discard(q)


def push_event(event_type: str, message: str, agent: str = None, data: dict = None):
    """
    Broadcast an event to ALL connected SSE clients.
    event_type: THINKING | ROUTING | A2A | RESULT | WRITEBACK | ERROR
    """
    event = {
        "type":      event_type,
        "message":   message,
        "agent":     agent,
        "data":      data or {},
        "timestamp": time.strftime("%H:%M:%S"),
    }
    payload = json.dumps(event, default=str)
    with _lock:
        for q in _clients:
            q.put(payload)
