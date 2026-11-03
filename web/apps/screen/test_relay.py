"""The relay to the guest panel over real HTTP (a stand-in panel on a free port), and the screen's rarer answers."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from django.test import TestCase, override_settings

from apps.credits import services as credits
from apps.credits.models import Entry, PowerCall
from apps.notes.models import Note
from apps.screen import views
from apps.users.models import User


class Panel:
    """A guest panel that answers what the test says, and keeps what it was sent."""

    def __init__(self):
        self.answer = (200, b'{"ok": true}')
        self.seen = []
        panel = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _reply(self):
                length = int(self.headers.get("Content-Length") or 0)
                panel.seen.append((self.command, self.path, dict(self.headers), self.rfile.read(length)))
                code, body = panel.answer
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = _reply

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class RelayTests(TestCase):
    def setUp(self):
        self.panel = Panel()
        self.addCleanup(self.panel.close)

    def relay(self, *args, key=""):
        with override_settings(GODLING_PANEL_URL=self.panel.url, GODLING_PANEL_KEY=key):
            return views.relay(*args)

    def test_answers_and_the_key(self):
        self.panel.answer = (200, b'{"ok": true, "text": "done"}')
        self.assertEqual(self.relay("POST", "/api/power", {"power": "Stone"}, key="k"), {"ok": True, "text": "done"})
        method, path, headers, body = self.panel.seen[-1]
        self.assertEqual((method, path, headers["X-Godling-Key"], json.loads(body)), ("POST", "/api/power", "k",
                                                                                     {"power": "Stone"}))
        self.panel.answer = (200, b"")
        self.assertEqual(self.relay("GET", "/api/status"), {})
        self.assertNotIn("X-Godling-Key", self.panel.seen[-1][2])

    def test_refusals_errors_and_silence(self):
        self.panel.answer = (403, b'{"ok": false, "text": "no key"}')
        self.assertEqual(self.relay("POST", "/api/note", {}), {"ok": False, "text": "no key"})
        self.panel.answer = (500, b"")
        self.assertIs(self.relay("GET", "/api/status"), views.PANEL_DOWN)
        self.panel.answer = (500, b"<html>broken</html>")
        self.assertIs(self.relay("GET", "/api/status"), views.PANEL_DOWN)
        self.panel.answer = (200, b"not json")
        self.assertIs(self.relay("GET", "/api/status"), views.PANEL_DOWN)
        with override_settings(GODLING_PANEL_URL="http://127.0.0.1:9", GODLING_PANEL_KEY=""):
            self.assertIs(views.relay("GET", "/api/status"), views.PANEL_DOWN)


def make_user(name):
    return User.objects.create_user(username=name, email=f"{name}@example.org", password="an-island-test-pass-4127")


class ScreenEdgeTests(TestCase):
    def setUp(self):
        self.status = {"world": True, "popups": []}
        self.answer = {"ok": True, "text": "done"}

        def fake_relay(method, path, body=None):
            if path.startswith("/api/status"):
                return self.status
            return dict(self.answer)
        patcher = mock.patch("apps.screen.views.relay", side_effect=fake_relay)
        patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, path, body):
        return self.client.post(path, body, content_type="application/json")

    def test_a_body_that_is_not_json_is_empty(self):
        self.client.force_login(make_user("tomv"))
        response = self.client.post("/api/power", b"{broken", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.post("/api/report", [1, 2]).status_code, 404)

    def test_a_panel_that_is_down_shows_an_island_that_is_not_there(self):
        self.status = views.PANEL_DOWN
        self.assertFalse(self.client.get("/api/status").json()["world"])

    def test_pop_ups_that_are_not_notes_stay_beside_hidden_notes(self):
        author = make_user("tomv")
        hidden = Note.objects.create(author=author, text="gone", status=Note.HIDDEN)
        shown = Note.objects.create(author=author, text="hello")
        self.status = {"world": True, "popups": [
            {"kind": "power", "text": "Meteor"}, {"kind": "note", "text": "gone", "ref": hidden.pk},
            {"kind": "note", "text": "hello", "ref": shown.pk}, {"kind": "note", "text": "no ref"}],
            "mind": {"feed": [{"text": "a note said gone today"}, {"text": "plain"}]}}
        status = self.client.get("/api/status").json()
        self.assertEqual([p["text"] for p in status["popups"]], ["Meteor", "hello", "no ref"])
        self.assertEqual(status["popups"][1]["noteId"], shown.pk)
        self.assertEqual(status["mind"]["feed"][0]["text"], "A note drifted down; moderators have hidden it.")

    def test_an_aim_that_is_not_numbers_is_kept_as_none(self):
        user = make_user("tomv")
        credits.change(user, 50, Entry.GRANT, "test")
        self.client.force_login(user)
        self.post("/api/power", {"power": "Stone", "at": ["east", "west"]})
        call = PowerCall.objects.get()
        self.assertIsNone(call.at_x)
        self.assertIsNone(call.at_z)

    def test_a_second_note_too_soon_after_a_turn_was_taken(self):
        user = make_user("tomv")
        self.client.force_login(user)
        with mock.patch("apps.screen.views.note_wait", return_value=0), \
                mock.patch("apps.screen.views.take_turn", return_value=(None, 42)):
            reply = self.post("/api/note", {"text": "hello"}).json()
        self.assertEqual(reply["wait"], 42)
        self.assertIn("0:42", reply["text"])

    def test_a_note_kept_as_the_panel_shows_it(self):
        self.client.force_login(make_user("tomv"))
        self.answer = {"ok": True, "text": "sent", "note": "hello, island"}
        self.post("/api/note", {"text": "hello  island"})
        self.assertEqual(Note.objects.get().text, "hello, island")
