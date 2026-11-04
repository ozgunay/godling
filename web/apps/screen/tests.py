"""The screen behind accounts: anyone watches; powers cost credits and go to the panel as the signed-in account; notes
are kept and can be reported, and hidden ones vanish from every screen. No request waits on the island for long: the
news is shared, powers are queued for the worker."""
import http.client
import time
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.credits import services as credits
from apps.credits.models import Entry, Power, PowerCall
from apps.notes.models import Note, Report
from apps.rules import words
from apps.rules.models import BlockedWord, Rules
from apps.screen import island, tasks
from apps.screen.views import PANEL_DOWN
from apps.users.models import User

PANEL_STATUS = {"world": True, "watching": 0, "popups": [], "view": "http://localhost:8080/?spectator_token=t"}
REAL_RELAY = island.relay  # the tests below talk to a fake panel; this one is the real thing


def make_user(name, email=None, days_old=0):
    user = User.objects.create_user(username=name, email=email or f"{name}@example.org",
                                    password="an-island-test-pass-4127")
    if days_old:
        User.objects.filter(pk=user.pk).update(date_joined=timezone.now() - timedelta(days=days_old))
    return user


@override_settings(GODLING_PANEL_KEY="secret-test-key")
class ScreenTests(TestCase):
    def setUp(self):
        cache.clear()
        self.calls = []
        self.panel = {"ok": True, "text": "done"}
        self.status = dict(PANEL_STATUS)

        def fake_relay(method, path, body=None, timeout=None):
            self.calls.append((method, path, body))
            return dict(self.status) if path.startswith("/api/status") else dict(self.panel)

        # Each poll fetches afresh here, so a test sees what it just changed (the sharing has its own test), and the
        # watching window never turns over in the middle of a test.
        for patcher in (mock.patch("apps.screen.island.relay", side_effect=fake_relay),
                        mock.patch("apps.screen.island.FRESH", 0), mock.patch("apps.screen.island.WINDOW", 10 ** 6)):
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
        self.assertEqual(status["watching"], 1)  # counted by the site, across its workers (island.watching)
        self.assertFalse(status["account"]["signedIn"])
        self.assertEqual(status["prices"]["Meteor"], 300)
        self.assertEqual(status["powers"]["Meteor"]["kind"], "Disaster")
        self.assertTrue(status["powers"]["Meteor"]["harms"])
        self.assertIn("crater", status["powers"]["Meteor"]["does"])
        self.assertEqual(status["notes"]["limit"], 140)
        self.assertEqual(self.calls[-1][1], "/api/status")  # the panel gives the shared news, not one viewer's
        self.client.get("/api/status?client=user000001")  # a page cannot pass itself off as an account
        self.assertEqual(self.client.get("/api/status?client=abcdef123").json()["watching"], 1)
        self.viewer(credit=25)
        status = self.client.get("/api/status?client=abcdef123").json()
        self.assertEqual((status["account"]["username"], status["account"]["credits"]), ("tomv", 25))
        self.assertEqual(status["watching"], 2)

    def test_the_news_is_fetched_once_for_every_viewer(self):
        """However many pages poll, the panel is asked about once a second (island.shared)."""
        with mock.patch("apps.screen.island.FRESH", 60), mock.patch("apps.screen.island.PER_ADDRESS", 8):
            for n in range(12):
                status = self.client.get(f"/api/status?client=page{n:04d}").json()
            self.assertEqual(len([c for c in self.calls if c[1] == "/api/status"]), 1)
            self.assertEqual(status["watching"], 8)  # all from one address: up to the cap, not a script's thousands
            other = self.client.get("/api/status?client=farpage01", REMOTE_ADDR="198.51.100.9").json()
            self.assertEqual(other["watching"], 9)
            self.viewer()  # an account always counts, whatever address it shares
            self.assertEqual(self.client.get("/api/status").json()["watching"], 10)

    def test_the_first_viewers_wait_for_the_first_copy_of_the_news(self):
        """On a cold start the requests that do not fetch wait for the copy being fetched, rather than say Offline."""
        cache.add(island.STATUS_LOCK, 1, timeout=10)  # another request is fetching
        copy = {"at": 0, "status": {"world": True, "popups": [], "free": False}}
        with mock.patch.object(island.cache, "get", side_effect=[None, copy]), mock.patch("time.sleep"):
            self.assertTrue(island.shared(lambda: {"world": "not fetched here"})["world"])

    def test_a_panel_cut_off_mid_answer_is_out_of_reach(self):
        with mock.patch("urllib.request.urlopen", side_effect=http.client.IncompleteRead(b"{")):
            self.assertIs(REAL_RELAY("GET", "/api/status"), island.PANEL_DOWN)

    @override_settings(ALLAUTH_TRUSTED_PROXY_COUNT=1)
    def test_the_address_is_the_one_caddy_saw(self):
        for n in range(10):
            self.client.get(f"/api/status?client=caddy{n:04d}", REMOTE_ADDR="172.18.0.5",
                            HTTP_X_FORWARDED_FOR=f"203.0.113.{n}")
        self.assertEqual(self.client.get("/api/status").json()["watching"], 10)

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
        self.assertEqual((call.power, call.price, call.at_x, call.at_z, call.ok, call.refunded, call.status),
                         ("Meteor", 300, 1.5, -2.0, True, False, PowerCall.DONE))

    def test_a_queued_power_is_asked_after_and_given_up_when_the_island_never_answers(self):
        """With the worker on its own (Redis), a call is queued; the screen asks after it until it is settled."""
        user = self.viewer(credit=50)
        with mock.patch.object(tasks.call_power, "delay"):  # queued, and the worker is slow to take it
            answer = self.post("/api/power", {"power": "Stone"}).json()
        self.assertTrue(answer["pending"])
        self.assertEqual(answer["credits"], 46)
        url = f"/api/power/{answer['pending']}"
        self.assertTrue(self.client.get(url).json()["pending"])
        self.client.force_login(make_user("nosy"))
        self.assertEqual(self.client.get(url).status_code, 404)  # one viewer's calls are theirs
        self.client.force_login(user)
        PowerCall.objects.update(created=timezone.now() - timedelta(minutes=5))
        later = self.client.get(url).json()
        self.assertFalse(later["ok"])
        self.assertIn("did not answer", later["text"])
        self.assertEqual(later["credits"], 50)
        self.assertEqual(PowerCall.objects.get().status, PowerCall.EXPIRED)
        tasks.call_power(answer["pending"])  # the worker comes round at last: it calls nothing
        self.assertEqual([c for c in self.calls if c[1] == "/api/power"], [])

    def test_powers_nobody_takes_are_refunded_without_the_viewer_looking(self):
        """The reviewer's case: the page closed (or its answer was lost); the server gives the call up on its own."""
        from django.conf import settings

        user = self.viewer(credit=50)
        with mock.patch.object(tasks.call_power, "delay"):  # queued, and its message lost
            self.post("/api/power", {"power": "Stone"})
        self.client.logout()
        tasks.expire_stale_powers()
        self.assertEqual(PowerCall.objects.get().status, PowerCall.QUEUED)  # not stale yet: it may still go
        PowerCall.objects.update(created=timezone.now() - timedelta(minutes=5))
        tasks.expire_stale_powers()
        self.assertEqual(PowerCall.objects.get().status, PowerCall.EXPIRED)
        self.assertEqual(credits.balance_of(user), 50)
        self.assertEqual(settings.CELERY_BEAT_SCHEDULE["expire-stale-powers"]["task"], tasks.expire_stale_powers.name)

    def test_a_late_worker_gives_up_the_call_it_skips(self):
        user = self.viewer(credit=50)
        with mock.patch.object(tasks.call_power, "delay"):
            pending = self.post("/api/power", {"power": "Stone"}).json()["pending"]
        PowerCall.objects.update(created=timezone.now() - timedelta(minutes=5))
        tasks.call_power(pending)
        self.assertEqual(PowerCall.objects.get().status, PowerCall.EXPIRED)
        self.assertEqual(credits.balance_of(user), 50)
        self.assertEqual([c for c in self.calls if c[1] == "/api/power"], [])

    def test_the_worker_settles_a_queued_power(self):
        self.viewer(credit=50)
        with mock.patch.object(tasks.call_power, "delay"):
            pending = self.post("/api/power", {"power": "Log", "at": [3, 4]}).json()["pending"]
        tasks.call_power(pending)
        tasks.call_power(pending)  # delivered twice: called once
        self.assertEqual(len([c for c in self.calls if c[1] == "/api/power"]), 1)
        done = self.client.get(f"/api/power/{pending}").json()
        self.assertTrue(done["ok"])
        self.assertEqual(done["text"], "done")

    def test_the_queue_out_of_reach_gives_the_credits_back(self):
        self.viewer(credit=50)
        with mock.patch.object(tasks.call_power, "delay", side_effect=OSError("no broker")):
            answer = self.post("/api/power", {"power": "Stone"}).json()
        self.assertFalse(answer["ok"])
        self.assertEqual(answer["credits"], 50)
        self.assertEqual(PowerCall.objects.get().status, PowerCall.EXPIRED)

    def test_credits_are_not_taken_unless_the_call_is_kept(self):
        """Spending and keeping the call are one transaction: a failure in between leaves the purse whole."""
        user = self.viewer(credit=50)
        strict = Client(raise_request_exception=False)
        strict.force_login(user)
        with mock.patch("apps.screen.views.PowerCall.objects.create", side_effect=RuntimeError("database gone")):
            response = strict.post("/api/power", {"power": "Stone"}, content_type="application/json")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(credits.balance_of(user), 50)
        self.assertFalse(Entry.objects.filter(user=user, kind=Entry.POWER).exists())

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
        self.client.get("/api/status")  # watching the island
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

        def overlapping(method, path, body=None, timeout=None):  # the island is slow: a second request meanwhile
            if not inner:
                inner.append(None)  # only one overlap, even if the second request got through
                inner[0] = self.post(path, {"power": "Log"} if path == "/api/power" else {"text": "me too"}).json()
            return {"ok": True, "text": "done"}

        with mock.patch("apps.screen.island.relay", side_effect=overlapping):
            self.assertTrue(self.post("/api/power", {"power": "Stone"}).json()["ok"])
        self.assertIn("One power at a time", inner[0]["text"])
        self.assertEqual(credits.balance_of(User.objects.get(username="tomv")), 46)
        self.assertEqual(PowerCall.objects.count(), 1)
        inner.clear()
        with mock.patch("apps.screen.island.relay", side_effect=overlapping):
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
        self.status["mind"] = {"feed": [{"who": "notice", "text": f"A paper glider … It reads: '{note.text}'"},
                                        {"who": "godling", "text": f"Should I {note.text}?"},
                                        {"who": "godling", "about": "learned", "name": "hop", "text": "hops"}],
                               "now": {"time": 1, "text": f"Do as the note says: {note.text}", "step": 1, "of": 2},
                               "needs": f"{note.text}, and logs", "thought": f"Should I {note.text}?"}
        self.client.force_login(author)
        popup = self.client.get("/api/status").json()["popups"][0]
        self.assertEqual(popup["noteId"], note.pk)  # so viewers can report it
        self.assertIn("own note", self.post("/api/report", {"note": note.pk}).json()["text"])
        for name in ("r1", "r2", "r3"):
            self.client.force_login(make_user(name, days_old=2))
            self.client.get("/api/status")
            self.assertTrue(self.post("/api/report", {"note": note.pk, "reason": "spam"}).json()["ok"])
        self.assertIn("already", self.post("/api/report", {"note": note.pk}).json()["text"])
        note.refresh_from_db()
        author.refresh_from_db()
        self.assertEqual(note.status, Note.HIDDEN)
        self.assertTrue(author.notes_muted)
        status = self.client.get("/api/status").json()
        self.assertEqual(status["popups"], [])
        self.assertIn("hidden", status["mind"]["feed"][0]["text"])
        self.assertEqual(status["mind"]["now"], {"time": 1, "text": "…", "step": 1, "of": 2})  # what it does now, too
        # Godling's own words are held back as a replay holds them back, never shown as the note's notice
        self.assertEqual([f["text"] for f in status["mind"]["feed"][1:]], ["…", "hops"])
        self.assertEqual((status["mind"]["needs"], status["mind"]["thought"]), ("…", "…"))

    def report_as(self, user, note):
        self.client.force_login(user)
        self.client.get("/api/status")  # watching the island
        return self.post("/api/report", {"note": note.pk}).json()

    def test_fresh_accounts_and_one_inbox_cannot_hide_a_note(self):
        """Accounts are cheap: only reports from accounts a day old count, and one inbox counts once."""
        author = make_user("mara_k")
        note = Note.objects.create(author=author, text="hello island")
        for name in ("fresh1", "fresh2", "fresh3"):
            self.assertTrue(self.report_as(make_user(name), note)["ok"])  # kept for moderators, but not counted
        for n, email in enumerate(("sam+a@gmail.com", "s.am@gmail.com", "sam+b@googlemail.com")):
            self.assertTrue(self.report_as(make_user(f"sam{n}", email=email, days_old=3), note)["ok"])
        note.refresh_from_db()
        author.refresh_from_db()
        self.assertEqual((note.status, author.notes_muted), (Note.SENT, False))
        self.assertEqual(note.reports.count(), 6)
        self.report_as(make_user("ana", days_old=3), note)
        self.report_as(make_user("ben", days_old=3), note)
        note.refresh_from_db()
        self.assertEqual(note.status, Note.HIDDEN)  # three inboxes, old enough: sam, ana and ben

    def test_reports_come_from_watching_viewers_on_recent_notes_at_a_pace(self):
        author = make_user("mara_k")
        note = Note.objects.create(author=author, text="hello island")
        self.client.force_login(make_user("lurker"))
        self.assertIn("watch the island", self.post("/api/report", {"note": note.pk}).json()["text"])
        old = Note.objects.create(author=author, text="an old note")
        Note.objects.filter(pk=old.pk).update(created=timezone.now() - timedelta(hours=2))
        self.assertIn("left the screen", self.report_as(User.objects.get(username="lurker"), old)["text"])
        Rules.objects.filter(pk=1).update(reports_per_hour=2)
        busy = make_user("busy")
        for n in range(2):
            self.assertTrue(self.report_as(busy, Note.objects.create(author=author, text=f"note {n}"))["ok"])
        answer = self.report_as(busy, Note.objects.create(author=author, text="note 3"))
        self.assertFalse(answer["ok"])
        self.assertIn("this hour", answer["text"])
        self.assertEqual(Report.objects.filter(reporter=busy).count(), 2)

    def test_posts_need_the_csrf_token(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(make_user("ozzy"))
        self.assertEqual(strict.post("/api/power", {"power": "Stone"}, content_type="application/json").status_code, 403)


class ReplayTests(TestCase):
    """The island's past (ADR-016): anyone watches it all; what it says of viewers is looked up when served."""

    def setUp(self):
        cache.clear()
        self.answers, self.asked = {}, []

        def fake_relay(method, path, body=None, timeout=15):
            self.asked.append((path, timeout))
            return self.answers.get(path.split("?")[0], {"ok": False})

        patcher = mock.patch("apps.screen.island.relay", side_effect=fake_relay)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tracks(self, entries, acts, ago_ms=60_000):
        now = int(time.time() * 1000)
        self.answers["/api/replay/tracks"] = {"format": 1, "from": now - ago_ms, "to": now, "lead": [],
                                              "entries": entries, "acts": acts}
        return self.client.get(f"/api/replay/tracks?from={now - ago_ms}&to={now}").json()

    @override_settings(GODLING_REPLAY_URL="https://island.example.org/replay")
    def test_the_index_names_where_the_chunks_are_and_is_shared(self):
        self.answers["/api/replay/index"] = {"format": 1, "segments": [{"id": "a", "start": 1, "end": 2}],
                                             "chunks": "replay", "chunks_url": "https://bucket.example.org/island",
                                             "chunks_url_until": 5}
        index = self.client.get("/api/replay/index").json()
        self.assertEqual(index["chunks"], "https://island.example.org/replay")  # the island's origin
        self.assertEqual((index["chunks_url"], index["chunks_url_until"]), ("https://bucket.example.org/island", 5))
        self.client.get("/api/replay/index")
        self.assertEqual(len(self.asked), 1)  # one copy for every viewer for a few seconds
        self.assertLessEqual(self.asked[0][1], 5)  # and no long wait on the island

    @override_settings(GODLING_REPLAY_URL="", GODLING_PANEL_URL="http://127.0.0.1:8081")
    def test_without_a_setting_the_panel_serves_the_chunks(self):
        self.answers["/api/replay/index"] = {"format": 1, "segments": [], "chunks": "replay"}
        self.assertEqual(self.client.get("/api/replay/index").json()["chunks"], "http://127.0.0.1:8081/replay")

    def test_marks_and_sky_pass_through_and_nothing_else_is_asked(self):
        self.answers["/api/replay/marks"] = [{"t": 5, "m": "rain"}]
        self.assertEqual(self.client.get("/api/replay/marks?from=0&to=10").json(), [{"t": 5, "m": "rain"}])
        self.answers["/api/replay/sky"] = [{"t": 5, "hour": 7}]
        self.client.get("/api/replay/sky?from=0&to=10&every=600000")
        self.assertIn("every=600000", self.asked[-1][0])
        self.assertEqual(self.client.get("/api/replay/chunks").status_code, 404)
        self.assertEqual(self.client.get("/api/replay/tracks?from=x&to=y").status_code, 400)  # the panel's refusal

    def test_hidden_and_deleted_notes_and_gone_accounts_leave_the_past(self):
        mara, sam = make_user("mara"), make_user("sam")
        kept = Note.objects.create(author=mara, text="hello island")
        hidden = Note.objects.create(author=mara, text="buy cheap gold", status=Note.HIDDEN)
        deleted = Note.objects.create(author=sam, text="visit my page soon")
        deleted_id = deleted.pk
        sam.delete()  # the account goes, and its notes with it
        t = time.time()
        tracks = self.tracks(
            [{"time": t, "kind": "event", "sky": "Note", "text": 'A paper glider drifted down. It reads: "buy cheap gold"'},
             {"time": t, "kind": "event", "sky": "Note", "text": 'A paper glider drifted down. It reads: "visit my page soon"'},
             {"time": t, "kind": "event", "sky": "Note", "text": 'A paper glider drifted down. It reads: "hello island"'},
             {"time": t, "kind": "decision", "thought": "The note says Buy Cheap Gold", "needs": "logs"},
             {"time": t, "kind": "decision", "thought": "Someone wants me to visit my page soon", "needs": ""},
             {"time": t, "kind": "learn", "name": "hop", "does": "hop, then buy cheap gold"},
             {"time": t, "kind": "sleep", "dream": "I dreamt someone said: buy cheap gold"}],
            [{"time": t, "id": 1, "kind": "note", "name": "mara", "text": "hello island", "ref": kept.pk},
             {"time": t, "id": 2, "kind": "note", "name": "mara", "text": "buy cheap gold", "ref": hidden.pk},
             {"time": t, "id": 3, "kind": "note", "name": "sam", "text": "visit my page soon", "ref": deleted_id},
             {"time": t, "id": 4, "kind": "power", "name": "gone_viewer", "power": "Stone", "text": "x"}])
        self.assertEqual([a["id"] for a in tracks["acts"]], [1, 4])
        self.assertEqual((tracks["acts"][0]["name"], tracks["acts"][0]["noteId"]), ("mara", kept.pk))
        self.assertNotIn("ref", tracks["acts"][0])
        self.assertEqual(tracks["acts"][1]["name"], "Someone")
        hidden_line = "A note drifted down; moderators have hidden it."
        self.assertEqual([e.get("text") for e in tracks["entries"][:3]],
                         [hidden_line, hidden_line, 'A paper glider drifted down. It reads: "hello island"'])
        self.assertEqual(tracks["entries"][3]["thought"], "…")  # whatever the case
        self.assertEqual(tracks["entries"][3]["needs"], "logs")
        self.assertEqual(tracks["entries"][4]["thought"], "…")  # a deleted note's words too
        self.assertEqual((tracks["entries"][5]["name"], tracks["entries"][5]["does"]), ("hop", "…"))  # what it learned
        self.assertEqual(tracks["entries"][6]["dream"], "…")  # and dreamt

    def test_a_short_hidden_note_hides_no_other_words(self):
        Note.objects.create(author=make_user("mara"), text="no", status=Note.HIDDEN)
        t = time.time()
        tracks = self.tracks([{"time": t, "kind": "decision", "thought": "I know where the stone is", "needs": "no logs"}],
                             [])
        self.assertEqual(tracks["entries"][0]["thought"], "I know where the stone is")
        self.assertEqual(tracks["entries"][0]["needs"], "no logs")

    def test_an_old_note_in_the_past_has_no_report_button(self):
        mara = make_user("mara")
        note = Note.objects.create(author=mara, text="hello island")
        Note.objects.filter(pk=note.pk).update(created=timezone.now() - timedelta(hours=2))
        tracks = self.tracks([], [{"time": time.time(), "id": 1, "kind": "note", "name": "mara", "text": "hello island",
                                   "ref": note.pk}])
        self.assertEqual(tracks["acts"][0]["text"], "hello island")
        self.assertNotIn("noteId", tracks["acts"][0])  # the site takes reports for 30 minutes only

    def test_the_past_out_of_reach_says_so(self):
        with mock.patch("apps.screen.island.relay", return_value=PANEL_DOWN):
            self.assertEqual(self.client.get("/api/replay/index").status_code, 503)
