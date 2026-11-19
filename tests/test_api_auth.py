import asyncio
import base64
import json
import os
import unittest
from unittest.mock import patch
from urllib.parse import quote, urlencode

from src.app import activities, app, teacher_sessions


def make_request(method, path, *, query="", credentials=None, cookie=None):
    headers = [(b"host", b"testserver")]
    if credentials:
        token = base64.b64encode(
            f"{credentials[0]}:{credentials[1]}".encode("utf-8")
        ).decode("ascii")
        headers.append((b"authorization", f"Basic {token}".encode("ascii")))
    if cookie:
        headers.append((b"cookie", cookie.encode("ascii")))

    messages = []
    request_message = {
        "type": "http.request",
        "body": b"",
        "more_body": False,
    }

    async def receive():
        nonlocal request_message
        if request_message is not None:
            message = request_message
            request_message = None
            return message
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": quote(path, safe="/").encode("ascii"),
        "query_string": query.encode("ascii"),
        "root_path": "",
        "headers": headers,
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "state": {},
        "extensions": {},
    }
    asyncio.run(app(scope, receive, send))

    response_start = next(
        message for message in messages if message["type"] == "http.response.start"
    )
    response_body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return (
        response_start["status"],
        dict(response_start["headers"]),
        json.loads(response_body),
    )


class TeacherAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "TEACHER_USERNAME": "test-teacher",
                "TEACHER_PASSWORD": "test-password",
            },
        )
        self.environment.start()
        self.original_participants = activities["Chess Club"]["participants"][:]
        teacher_sessions.clear()

    def tearDown(self):
        activities["Chess Club"]["participants"][:] = self.original_participants
        teacher_sessions.clear()
        self.environment.stop()

    def login(self):
        status, headers, response = make_request(
            "POST",
            "/auth/login",
            credentials=("test-teacher", "test-password"),
        )
        self.assertEqual(status, 200)
        self.assertEqual(response["expires_in"], 3600)
        return headers[b"set-cookie"].split(b";", 1)[0].decode("ascii")

    def test_activity_list_remains_public(self):
        status, _, response = make_request("GET", "/activities")

        self.assertEqual(status, 200)
        self.assertIn("Chess Club", response)

    def test_signup_rejects_missing_session(self):
        email = "unauthorized@mergington.edu"
        status, _, _ = make_request(
            "POST",
            "/activities/Chess Club/signup",
            query=urlencode({"email": email}),
        )

        self.assertEqual(status, 401)
        self.assertNotIn(email, activities["Chess Club"]["participants"])

    def test_signup_rejects_invalid_session(self):
        email = "invalid-session@mergington.edu"
        status, _, _ = make_request(
            "POST",
            "/activities/Chess Club/signup",
            query=urlencode({"email": email}),
            cookie="teacher_session=not-a-valid-session",
        )

        self.assertEqual(status, 401)
        self.assertNotIn(email, activities["Chess Club"]["participants"])

    def test_unregister_rejects_missing_session(self):
        email = self.original_participants[0]
        status, _, _ = make_request(
            "DELETE",
            "/activities/Chess Club/unregister",
            query=urlencode({"email": email}),
        )

        self.assertEqual(status, 401)
        self.assertIn(email, activities["Chess Club"]["participants"])

    def test_teacher_can_login_and_manage_signups(self):
        status, headers, _ = make_request(
            "POST",
            "/auth/login",
            credentials=("test-teacher", "test-password"),
        )
        cookie = headers[b"set-cookie"].split(b";", 1)[0].decode("ascii")
        email = "teacher-added@mergington.edu"

        signup_status, _, _ = make_request(
            "POST",
            "/activities/Chess Club/signup",
            query=urlencode({"email": email}),
            cookie=cookie,
        )
        unregister_status, _, _ = make_request(
            "DELETE",
            "/activities/Chess Club/unregister",
            query=urlencode({"email": email}),
            cookie=cookie,
        )

        self.assertEqual(status, 200)
        self.assertIn(b"httponly", headers[b"set-cookie"].lower())
        self.assertIn(b"secure", headers[b"set-cookie"].lower())
        self.assertIn(b"samesite=strict", headers[b"set-cookie"].lower())
        self.assertEqual(signup_status, 200)
        self.assertEqual(unregister_status, 200)
        self.assertNotIn(email, activities["Chess Club"]["participants"])

    def test_expired_session_is_rejected(self):
        with patch("src.app.current_time", return_value=1000):
            cookie = self.login()

        with patch("src.app.current_time", return_value=4601):
            status, _, _ = make_request(
                "POST",
                "/activities/Chess Club/signup",
                query=urlencode({"email": "expired@mergington.edu"}),
                cookie=cookie,
            )

        self.assertEqual(status, 401)
        self.assertNotIn(
            "expired@mergington.edu",
            activities["Chess Club"]["participants"],
        )

    def test_login_rejects_invalid_credentials(self):
        status, headers, _ = make_request(
            "POST",
            "/auth/login",
            credentials=("test-teacher", "wrong-password"),
        )

        self.assertEqual(status, 401)
        self.assertEqual(headers[b"www-authenticate"], b'Basic realm="teacher"')

    def test_login_fails_if_credentials_are_unconfigured(self):
        with patch.dict(
            os.environ,
            {"TEACHER_USERNAME": "", "TEACHER_PASSWORD": ""},
        ):
            status, _, _ = make_request(
                "POST",
                "/auth/login",
                credentials=("test-teacher", "test-password"),
            )

        self.assertEqual(status, 503)
