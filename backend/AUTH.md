# Spotify sessions

Sign-in creates a random HTTP-only `findtunes_session` cookie, valid for 24 hours.
The backend resolves it to an account; local storage is no longer authentication.
Profile and sync routes require the matching session. Spotify tokens stay server-side.
Log out revokes the session. Switch account logs out, then starts Spotify authorization
with `show_dialog=true`. This forces consent, not global Spotify logout: use Spotify's
account-switch option or sign out on Spotify if its browser session selects the old account.

Use the hostname configured in `NEXT_SPOTIFY_REDIRECT_URI` consistently. Sign-in
canonicalizes to that origin before setting the state cookie. `NEXT_PUBLIC_DOMAIN`
must use the same hostname for the backend, and `SPOTIFY_REDIRECT_URI` must exactly
match the frontend redirect URI and Spotify dashboard entry.
Set `SESSION_COOKIE_SECURE=true` for HTTPS deployment.

Sessions and ingestion admission are currently process-local: use one backend worker.
Backend restarts invalidate sessions and interrupt background work. A durable shared
session store and task queue are needed for multiple workers or reliable resumable jobs.
Logout leaves shared catalog ingestion running. Duplicate syncs for an account are
suppressed while queued/running and for one hour after a completed traversal. Bulk
ingestion is serialized across accounts; individual provider failures may still be
handled internally by ingestion. The cooldown does not certify every song was indexed.

Checks: `python -m unittest discover -s tests -p test_auth_sessions.py` from backend;
`node frontend/scripts/check_auth_routes.cjs` from the repository root.
