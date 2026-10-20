"""Opaque, revocable sessions for the single-process development backend."""
import secrets
import time
from threading import Lock
from fastapi import HTTPException, Request

COOKIE = 'findtunes_session'
TTL = 86400
_sessions = {}
_lock = Lock()


def issue_session(spotify_id):
    with _lock:
        now = time.time()
        for token in list(_sessions):
            if _sessions[token][1] <= now:
                del _sessions[token]
        token = secrets.token_urlsafe(32)
        _sessions[token] = (spotify_id, now + TTL)
        return token


def revoke_session(token):
    with _lock:
        _sessions.pop(token, None)


def current_user(request: Request):
    with _lock:
        value = _sessions.get(request.cookies.get(COOKIE))
    if not value or value[1] <= time.time():
        raise HTTPException(401, 'Please sign in to Spotify again.')
    return value[0]


def require_owner(spotify_id, user):
    if spotify_id != user:
        raise HTTPException(403, 'This profile belongs to another account.')
