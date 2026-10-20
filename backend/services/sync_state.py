"""Process-local admission control for catalog ingestion."""
from threading import Lock
import time

worker_lock = Lock()
_lock = Lock()
_active = set()
_completed = {}


def reserve(user):
    with _lock:
        if user in _active:
            return 'already_running'
        if time.monotonic() - _completed.get(user, float('-inf')) < 3600:
            return 'recently_completed'
        _active.add(user)
        return 'queued'


def release(user, success):
    with _lock:
        _active.discard(user)
        if success:
            _completed[user] = time.monotonic()
