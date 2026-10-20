import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from starlette.requests import Request
from app.sessions import COOKIE, issue_session, revoke_session, current_user, require_owner
from services import sync_state
from app.db.schemas import UserResponse


def request(token=''):
    return Request({'type': 'http', 'headers': [(b'cookie', f'{COOKIE}={token}'.encode())]})


class AuthTests(unittest.TestCase):
    def test_logout_revokes_session(self):
        token = issue_session('alice')
        self.assertEqual(current_user(request(token)), 'alice')
        revoke_session(token)
        with self.assertRaises(HTTPException) as error:
            current_user(request(token))
        self.assertEqual(error.exception.status_code, 401)

    def test_id_is_not_a_session(self):
        with self.assertRaises(HTTPException):
            current_user(request('alice'))

    def test_session_expiration(self):
        with patch('app.sessions.time.time', return_value=100):
            token = issue_session('alice')
        with patch('app.sessions.time.time', return_value=1000000):
            with self.assertRaises(HTTPException):
                current_user(request(token))

    def test_other_account_is_forbidden(self):
        require_owner('alice', 'alice')
        with self.assertRaises(HTTPException) as error:
            require_owner('bob', 'alice')
        self.assertEqual(error.exception.status_code, 403)

    def test_profile_excludes_tokens(self):
        value = UserResponse(spotify_id='alice', display_name='Alice', followers_count=0,
            access_token='secret', refresh_token='secret', raw_data='secret')
        self.assertFalse({'access_token', 'refresh_token', 'raw_data'} & value.model_dump().keys())

    def test_concurrent_syncs_are_deduplicated(self):
        user = 'concurrent-test'
        sync_state.release(user, False)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: sync_state.reserve(user), range(20)))
        self.assertEqual(results.count('queued'), 1)
        self.assertEqual(results.count('already_running'), 19)
        sync_state.release(user, False)
        self.assertEqual(sync_state.reserve(user), 'queued')
        sync_state.release(user, True)
        self.assertEqual(sync_state.reserve(user), 'recently_completed')


if __name__ == '__main__':
    unittest.main()
