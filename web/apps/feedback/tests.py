"""The bottle: a signed-in viewer's bug report, question or idea is kept for staff with only the screen facts the
screen sends; viewers send a few an hour at most; staff get an email when the site rules name an inbox, and read and
mark them in the admin."""
import json
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import Client, TestCase

from apps.feedback.models import Feedback
from apps.notes.tests import code_entered, two_factor
from apps.rules.models import Rules
from apps.users.models import User

FACTS = {"view": "replay", "moment": 1_793_000_000_000, "day": 3, "hour": 14.5, "camera": "follow", "stream": "live",
         "size": "1600x900", "pixels": 2, "touch": False, "browser": "Chrome 142", "system": "Windows"}


class SendingTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(username="tomv", email="tomv@example.org", password="x-test-pass-0001")
        self.client.force_login(self.viewer)

    def send(self, client=None, **body):
        body = {"kind": "bug", "text": "The hotbar hides behind the purse on my phone.", **body}
        return (client or self.client).post("/api/feedback", json.dumps(body), content_type="application/json")

    def test_a_signed_in_viewer_sends_a_bug_with_its_screen(self):
        answer = self.send(text="  The log fell ‮through‬ the​ wall.\r\nTwice.\x07  ", screen=FACTS)
        self.assertEqual(answer.status_code, 200)
        self.assertTrue(answer.json()["ok"])
        kept = Feedback.objects.get()
        self.assertEqual((kept.author, kept.kind, kept.status), (self.viewer, "bug", Feedback.NEW))
        self.assertEqual(kept.text, "The log fell through the wall.\nTwice.")  # hidden and control characters go
        self.assertEqual(kept.screen, FACTS)
        self.assertEqual(kept.facts(), [
            "Watching: the island's past, at 2026-10-26 07:33:20 UTC", "Island: day 3, 14:30", "Island stream: live",
            "Camera: following Godling", "Window: 1600x900 at 2x", "Browser: Chrome 142 on Windows"])

    def test_only_the_facts_the_screen_sends_are_kept(self):
        odd = {"view": "<b>live</b>", "moment": 12, "day": True, "hour": 25, "camera": "free", "stream": "hacked",
               "size": "big", "pixels": 99, "touch": "yes", "browser": "<script>",
               "system": "Linux", "cookie": "secret", "email": "me@example.org"}
        self.send(kind="idea", screen=odd)
        self.assertEqual(Feedback.objects.get().screen, {"camera": "free", "system": "Linux"})
        self.send(kind="question", screen="not facts")
        self.assertEqual(Feedback.objects.filter(kind="question").get().screen, {})
        self.assertEqual(Feedback.objects.filter(kind="question").get().facts(), [])

    def test_signed_out_viewers_are_asked_to_sign_in(self):
        answer = self.send(Client())
        self.assertEqual(answer.status_code, 401)
        self.assertEqual(answer.json(), {"ok": False, "signIn": True, "text": "Sign in to send the makers a message."})
        self.assertFalse(Feedback.objects.exists())

    def test_the_page_must_send_its_csrf_token(self):
        guarded = Client(enforce_csrf_checks=True)
        guarded.force_login(self.viewer)
        self.assertEqual(self.send(guarded).status_code, 403)

    def test_a_kind_and_a_few_words_up_to_the_limit(self):
        for body, words in [({"kind": "rant"}, "Say what it is: a bug, a question or an idea."),
                            ({"text": " ok "}, "Write a few words first."),
                            ({"text": "x" * 2001}, "Messages are 2,000 characters at most.")]:
            answer = self.send(**body)
            self.assertEqual((answer.status_code, answer.json()["text"]), (400, words))
        self.assertEqual(self.send(text="x" * 2000).status_code, 200)
        self.assertEqual(self.client.get("/api/feedback").status_code, 405)

    def test_a_few_an_hour(self):
        Rules.objects.filter(pk=Rules.get().pk).update(feedback_per_hour=2)
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.send().status_code, 200)
        refused = self.send()
        self.assertEqual(refused.status_code, 429)
        self.assertIn("That is 2 messages this hour. The next can go in 60:00.", refused.json()["text"])
        self.assertEqual(refused.json()["wait"], 3600)
        Feedback.objects.update(created=Feedback.objects.first().created - timedelta(minutes=59))
        self.assertEqual(self.send().json()["wait"], 60)
        Feedback.objects.update(created=Feedback.objects.first().created - timedelta(minutes=2))
        self.assertEqual(self.send().status_code, 200)
        other = User.objects.create_user(username="mara", email="mara@example.org", password="x-test-pass-0002")
        self.client.force_login(other)
        self.assertEqual(self.send().status_code, 200)  # each viewer has their own hour

    def test_staff_get_an_email_when_the_rules_name_an_inbox(self):
        self.send()
        self.assertEqual(mail.outbox, [])  # no inbox named: the admin's list is enough
        Rules.objects.filter(pk=Rules.get().pk).update(feedback_email="makers@example.org")
        self.send(kind="idea", text="A coconut power, please.", screen=FACTS)
        (sent,) = mail.outbox
        idea = Feedback.objects.get(kind="idea")
        self.assertEqual((sent.to, sent.subject), (["makers@example.org"], "[Godling beta] Idea from tomv"))
        self.assertIn("Idea from tomv <tomv@example.org>", sent.body)
        self.assertIn("A coconut power, please.", sent.body)
        self.assertIn("  Camera: following Godling\n", sent.body)
        self.assertIn(f"http://testserver/admin/feedback/feedback/{idea.pk}/change/", sent.body)

    def test_a_failed_email_never_fails_the_send(self):
        Rules.objects.filter(pk=Rules.get().pk).update(feedback_email="makers@example.org")
        with mock.patch("apps.feedback.tasks.send_mail", side_effect=OSError("the mail server is away")), \
                self.assertLogs("godling.feedback", "ERROR"):
            answer = self.send()
        self.assertTrue(answer.json()["ok"])
        self.assertTrue(Feedback.objects.exists())

    def test_kept_when_its_account_goes(self):
        self.send()
        self.viewer.delete()
        kept = Feedback.objects.get()
        self.assertIsNone(kept.author)
        self.assertIn("from a deleted account", str(kept))


class FeedbackAdminTests(TestCase):
    def setUp(self):
        staff = two_factor(User.objects.create_superuser(username="keeper", email="keeper@example.org",
                                                         password="an-island-test-pass-4127"))
        self.client.force_login(staff)
        code_entered(self.client)
        viewer = User.objects.create_user(username="tomv", email="tomv@example.org", password="x-test-pass-0001")
        self.bug = Feedback.objects.create(author=viewer, kind="bug", text="Long " * 30, screen=FACTS)
        self.idea = Feedback.objects.create(kind="idea", text="Rain power")

    def test_staff_read_and_mark_them(self):
        page = self.client.get("/admin/feedback/feedback/")
        self.assertContains(page, "Long Long")
        self.assertContains(page, "…")
        self.assertContains(page, "the past")
        page = self.client.get(f"/admin/feedback/feedback/{self.bug.pk}/change/")
        self.assertContains(page, 'href="mailto:tomv@example.org"')
        self.assertContains(page, "Camera: following Godling<br>Window: 1600x900 at 2x")
        self.assertContains(self.client.get(f"/admin/feedback/feedback/{self.idea.pk}/change/"), "Not attached")
        self.assertEqual(self.client.get("/admin/feedback/feedback/add/").status_code, 403)
        page = self.client.post("/admin/feedback/feedback/", {"action": "done", "_selected_action": [self.bug.pk]},
                                follow=True)
        self.assertContains(page, "1 message(s) marked done.")
        self.client.post("/admin/feedback/feedback/", {"action": "looking", "_selected_action": [self.idea.pk]})
        self.assertEqual(sorted(Feedback.objects.values_list("status", flat=True)), ["done", "looking"])

    def test_the_site_rules_hold_the_pace_and_the_inbox(self):
        page = self.client.get(f"/admin/rules/rules/{Rules.get().pk}/change/")
        self.assertContains(page, "feedback_per_hour")
        self.assertContains(page, "feedback_email")
