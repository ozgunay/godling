"""The screen behind accounts: anyone watches; powers cost credits and go to the panel as the signed-in account; notes
are kept and can be reported, and hidden ones vanish from every screen."""
from unittest import mock

from django.test import Client, TestCase, override_settings

from apps.credits import services as credits
from apps.credits.models import Entry, Power, PowerCall
from apps.notes.models import Note, Report
from apps.rules import words
from apps.rules.models import BlockedWord, Rules
from apps.users.models import User

PANEL_STATUS = {"world": True, "watching": 3, "popups": [], "view": "http://localhost:8080/?spectator_token=t"}


def make_user(name):
    return User.objects.create_user(username=name, email=f"{name}@example.org", password="an-island-test-pass-4127")


@override_settings(GODLING_PANEL_KEY="secret-test-key")
class ScreenTests(TestCase):
    def setUp(self):
        self.calls = []
        self.panel = {"ok": True, "text": "done"}
        self.status = dict(PANEL_STATUS)

        def fake_relay(method, path, body=None):
            self.calls.append((method, path, body))
            return dict(self.status) if path.startswith("/api/status") else dict(self.panel)

        patcher = mock.patch("apps.screen.views.relay", side_effect=fake_relay)
        patcher.start()
        self.addCleanup(patcher.stop)

    def viewer(self, name="tomv", credit=0):
        user = make_user(name)
        if credit:
            credits.change(user, credit, Entry.GRANT, "test")
        self.client.force_login(user)
        return user

    def post(self, path, body):
        return self.client.post(path, body, content_type="application/json")

    def test_the_page_is_served_with_a_csrf_cookie(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)
        self.assertEqual(self.client.get("/viewer.js")["Content-Type"], "text/javascript")
        self.assertEqual(self.client.get("/../web/manage.py").status_code, 404)

    def test_anyone_watches_and_the_status_carries_the_account_and_prices(self):
        status = self.client.get("/api/status?client=abcdef123").json()
        self.assertEqual(status["watching"], 3)
        self.assertFalse(status["account"]["signedIn"])
        self.assertEqual(status["prices"]["Meteor"], 300)
        self.assertEqual(status["powers"]["Meteor"]["kind"], "Disaster")
        self.assertTrue(status["powers"]["Meteor"]["harms"])
        self.assertIn("crater", status["powers"]["Meteor"]["does"])
        self.assertEqual(status["notes"]["limit"], 140)
        self.assertEqual(self.calls[-1][1], "/api/status?client=abcdef123")
        self.client.get("/api/status?client=user000001")  # a page cannot pass itself off as an account
        self.assertEqual(self.calls[-1][1], "/api/status?client=")
        user = self.viewer(credit=25)
        status = self.client.get("/api/status?client=abcdef123").json()
        self.assertEqual((status["account"]["username"], status["account"]["credits"]), ("tomv", 25))
        self.assertEqual(self.calls[-1][1], f"/api/status?client={user.client_id}")

    def test_prices_and_words_come_from_the_admin(self):
        Power.objects.filter(key="Stone").update(price=7, description="A test stone.", did="threw a stone")
        Power.objects.filter(key="Lightning").update(enabled=False)
        status = self.client.get("/api/status").json()
        self.assertEqual(status["prices"]["Stone"], 7)
        self.assertEqual((status["powers"]["Stone"]["does"], status["powers"]["Stone"]["did"]),
                         ("A test stone.", "threw a stone"))
        self.assertNotIn("Lightning", status["powers"])
        self.viewer(credit=50)
        self.assertEqual(self.post("/api/power", {"power": "Lightning"}).status_code, 400)

    @override_settings(GODLING_VIEW_URL="https://godling.example/island/?spectator_token=t")
    def test_the_public_island_link_replaces_the_panels(self):
        self.assertEqual(self.client.get("/api/status").json()["view"],
                         "https://godling.example/island/?spectator_token=t")

    def test_signed_out_viewers_cannot_call_powers_send_notes_or_report(self):
        for path, body in (("/api/power", {"power": "Stone"}), ("/api/note", {"text": "hello"}),
                           ("/api/report", {"note": 1})):
            response = self.post(path, body)
            self.assertEqual(response.status_code, 401)
            self.assertTrue(response.json()["signIn"])
        self.assertEqual(self.calls, [])

    def test_a_power_costs_its_price_and_goes_to_the_panel_as_the_account(self):
        user = self.viewer(credit=310)
        answer = self.post("/api/power", {"power": "Meteor", "at": [1.5, -2], "name": "someone else"}).json()
        self.assertTrue(answer["ok"])
        self.assertEqual(answer["credits"], 10)
        self.assertEqual(self.calls[-1], ("POST", "/api/power", {"client": user.client_id, "name": "tomv",
                                                                 "power": "Meteor", "at": [1.5, -2]}))
        call = PowerCall.objects.get()
        self.assertEqual((call.power, call.price, call.at_x, call.at_z, call.ok, call.refunded),
                         ("Meteor", 300, 1.5, -2.0, True, False))

    def test_one_power_at_a_time_as_the_rules_say(self):
        self.viewer(credit=50)
        self.assertTrue(self.post("/api/power", {"power": "Stone"}).json()["ok"])
        self.assertIn("One power at a time", self.post("/api/power", {"power": "Log"}).json()["text"])
        self.assertEqual(credits.balance_of(User.objects.get(username="tomv")), 46)  # the second was not charged
        Rules.objects.filter(pk=1).update(power_every=0)
        self.assertTrue(self.post("/api/power", {"power": "Log"}).json()["ok"])

    def test_too_few_credits_and_nothing_reaches_the_island(self):
        self.viewer(credit=3)
        answer = self.post("/api/power", {"power": "Stone"}).json()
        self.assertFalse(answer["ok"])
        self.assertTrue(answer["needCredits"])
        self.assertEqual(answer["credits"], 3)
        self.assertEqual(self.calls, [])

    def test_the_credits_come_back_when_the_world_refuses(self):
        user = self.viewer(credit=40)
        self.panel = {"ok": False, "text": "No clear spot near Godling right now."}
        answer = self.post("/api/power", {"power": "Lightning"}).json()
        self.assertFalse(answer["ok"])
        self.assertEqual(answer["credits"], 40)
        self.assertEqual(list(Entry.objects.filter(user=user).values_list("kind", flat=True)),
                         ["refund", "power", "grant"])
        self.assertTrue(PowerCall.objects.get().refunded)

    def test_test_mode_from_the_rules_makes_powers_free(self):
        Rules.objects.filter(pk=1).update(free_powers=True)
        self.viewer()
        self.assertTrue(self.client.get("/api/status").json()["account"]["free"])
        self.assertTrue(self.post("/api/power", {"power": "Earthquake"}).json()["ok"])
        self.assertEqual(PowerCall.objects.get().price, 0)

    def test_a_note_goes_as_the_account_and_is_kept_as_the_panel_shows_it(self):
        user = self.viewer()
        self.panel = {"ok": True, "text": "Folded into a glider.", "note": "Say 'hi' to the palms"}
        self.assertTrue(self.post("/api/note", {"text": 'Say "hi"\nto the​ palms'}).json()["ok"])
        note = Note.objects.get()
        self.assertEqual(self.calls[-1], ("POST", "/api/note", {"client": user.client_id, "name": "tomv",
                                                                "text": "Say 'hi' to the palms", "ref": note.pk}))
        self.assertEqual(note.text, "Say 'hi' to the palms")

    def test_a_report_reaches_the_note_that_was_shown(self):
        """Pop-ups carry the note's id from the site through the panel; names and words never pick the note."""
        mine, theirs = make_user("mara+foo"), make_user("marafoo")
        shown = Note.objects.create(author=mine, text="hello island")
        Note.objects.create(author=theirs, text="hello island")  # the same words from another account
        self.status["popups"] = [{"id": 1, "kind": "note", "name": "mara+foo", "text": "hello island", "ref": shown.pk},
                                 {"id": 2, "kind": "note", "name": "marafoo", "text": "hello island"}]
        popups = self.client.get("/api/status").json()["popups"]
        self.assertEqual(popups[0]["noteId"], shown.pk)
        self.assertNotIn("ref", popups[0])
        self.assertNotIn("noteId", popups[1])  # no id came with it: nothing to report
        self.client.force_login(make_user("r1"))
        self.post("/api/report", {"note": popups[0]["noteId"]})
        self.assertEqual(list(Report.objects.values_list("note__author__username", flat=True)), ["mara+foo"])

    def test_a_note_the_island_refuses_is_not_kept(self):
        self.viewer()
        self.panel = {"ok": False, "text": "The sky is full of notes right now. Try again in a minute."}
        self.assertFalse(self.post("/api/note", {"text": "hello"}).json()["ok"])
        self.assertFalse(Note.objects.exists())

    def test_note_pace_length_and_blocked_words_come_from_the_rules(self):
        self.viewer()
        Rules.objects.filter(pk=1).update(note_limit=20, note_every=60)
        self.assertIn("20 characters", self.post("/api/note", {"text": "x" * 21}).json()["text"])
        BlockedWord.objects.create(word="gold coins", applies_to=BlockedWord.NOTES)
        self.assertIn("not be kind", self.post("/api/note", {"text": "buy GOLD COINS"}).json()["text"])
        self.assertTrue(self.post("/api/note", {"text": "hello Godling"}).json()["ok"])
        again = self.post("/api/note", {"text": "hello again"}).json()
        self.assertFalse(again["ok"])
        self.assertGreater(again["wait"], 50)
        self.assertGreater(self.client.get("/api/status").json()["notes"]["wait"], 50)
        self.assertEqual(len([c for c in self.calls if c[1] == "/api/note"]), 1)

    def test_lookalike_letters_do_not_slip_past_the_blocked_words(self):
        self.viewer()
        BlockedWord.objects.create(word="cheap gold", applies_to=BlockedWord.NOTES)
        for text in ("ｃｈｅａｐ ｇｏｌｄ", "che​ap gold", "cheap\ngold"):  # fullwidth, a zero-width space, a line break
            self.assertIn("not be kind", self.post("/api/note", {"text": text}).json()["text"])
        self.assertEqual(self.calls, [])
        BlockedWord.objects.create(word="sky lord", applies_to=BlockedWord.USERNAMES)
        self.assertTrue(words.username_blocked("ＳｋｙＬｏｒｄ"))

    def test_two_requests_at_once_take_one_turn(self):
        """A second power or note sent while the first is still with the island finds the turn taken (no race)."""
        self.viewer(credit=50)
        inner = []

        def overlapping(method, path, body=None):  # the island is slow: a second request arrives meanwhile
            if not inner:
                inner.append(None)  # only one overlap, even if the second request got through
                inner[0] = self.post(path, {"power": "Log"} if path == "/api/power" else {"text": "me too"}).json()
            return {"ok": True, "text": "done"}

        with mock.patch("apps.screen.views.relay", side_effect=overlapping):
            self.assertTrue(self.post("/api/power", {"power": "Stone"}).json()["ok"])
        self.assertIn("One power at a time", inner[0]["text"])
        self.assertEqual(credits.balance_of(User.objects.get(username="tomv")), 46)
        self.assertEqual(PowerCall.objects.count(), 1)
        inner.clear()
        with mock.patch("apps.screen.views.relay", side_effect=overlapping):
            self.assertTrue(self.post("/api/note", {"text": "hello Godling"}).json()["ok"])
        self.assertFalse(inner[0]["ok"])
        self.assertGreater(inner[0]["wait"], 100)
        self.assertEqual(Note.objects.count(), 1)

    def test_a_turn_nothing_came_of_is_given_back(self):
        self.viewer(credit=3)
        self.assertTrue(self.post("/api/power", {"power": "Stone"}).json()["needCredits"])
        credits.change(User.objects.get(username="tomv"), 10, Entry.GRANT, "test")
        self.assertTrue(self.post("/api/power", {"power": "Stone"}).json()["ok"])  # no wait after too few credits
        self.panel = {"ok": False, "text": "The sky is full of notes; try again soon."}
        self.assertFalse(self.post("/api/note", {"text": "hello"}).json()["ok"])
        self.panel = {"ok": True, "text": "Folded into a glider."}
        self.assertTrue(self.post("/api/note", {"text": "hello"}).json()["ok"])  # no wait after the island refused

    def test_a_muted_account_sends_no_notes(self):
        user = self.viewer()
        user.notes_muted = True
        user.save()
        answer = self.post("/api/note", {"text": "hello"}).json()
        self.assertFalse(answer["ok"])
        self.assertIn("paused", answer["text"])
        self.assertEqual(self.calls, [])

    def test_three_reports_hide_a_note_and_pause_its_author(self):
        author = make_user("mara_k")
        note = Note.objects.create(author=author, text="buy cheap gold at the beach")
        self.status["popups"] = [{"id": 7, "kind": "note", "name": "mara_k", "text": note.text, "time": 0,
                                  "ref": note.pk}]
        self.status["mind"] = {"feed": [{"who": "notice", "text": f"A paper glider … It reads: '{note.text}'"}]}
        self.client.force_login(author)
        self.assertIn("own note", self.post("/api/report", {"note": note.pk}).json()["text"])
        popup = self.client.get("/api/status").json()["popups"][0]
        self.assertEqual(popup["noteId"], note.pk)  # so viewers can report it
        for name in ("r1", "r2", "r3"):
            self.client.force_login(make_user(name))
            self.assertTrue(self.post("/api/report", {"note": note.pk, "reason": "spam"}).json()["ok"])
        self.assertIn("already", self.post("/api/report", {"note": note.pk}).json()["text"])
        note.refresh_from_db()
        author.refresh_from_db()
        self.assertEqual(note.status, Note.HIDDEN)
        self.assertTrue(author.notes_muted)
        status = self.client.get("/api/status").json()
        self.assertEqual(status["popups"], [])
        self.assertIn("hidden", status["mind"]["feed"][0]["text"])

    def test_posts_need_the_csrf_token(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(make_user("ozzy"))
        self.assertEqual(strict.post("/api/power", {"power": "Stone"}, content_type="application/json").status_code, 403)
