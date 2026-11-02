"""The admin, as staff use it: every page opens; prices are edited in their list; grants, mutes and bans work; the
island's logs show."""
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.credits import services
from apps.credits.models import Power
from apps.notes.models import Note
from apps.users.models import User


class AdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(username="keeper", email="keeper@example.org",
                                                   password="an-island-test-pass-4127")
        self.client.force_login(self.staff)
        self.viewer = User.objects.create_user(username="tomv", email="tomv@example.org",
                                               password="an-island-test-pass-4127")

    def test_every_list_opens(self):
        for model in ("users/user", "users/disposabledomain", "credits/power", "credits/creditpack", "credits/purse",
                      "credits/entry", "credits/powercall", "credits/payment", "notes/note", "notes/report",
                      "rules/blockedword"):
            self.assertEqual(self.client.get(f"/admin/{model}/").status_code, 200, model)
        page = self.client.get(f"/admin/users/user/{self.viewer.pk}/change/")
        self.assertContains(page, "Adjust credits")
        self.assertContains(page, "Powers called")
        self.assertRedirects(self.client.get("/admin/rules/rules/"), "/admin/rules/rules/1/change/")
        self.assertContains(self.client.get("/admin/credits/power/5/change/"), "What the screen says")

    def test_prices_are_edited_in_the_list(self):
        powers = list(Power.objects.order_by("sort", "key"))
        form = {"form-TOTAL_FORMS": str(len(powers)), "form-INITIAL_FORMS": str(len(powers)), "_save": "Save"}
        for i, p in enumerate(powers):
            form.update({f"form-{i}-id": str(p.pk), f"form-{i}-price": str(250 if p.key == "Meteor" else p.price),
                         f"form-{i}-enabled": "on", f"form-{i}-sort": str(p.sort)})
        self.client.post("/admin/credits/power/", form)
        self.assertEqual(Power.objects.get(key="Meteor").price, 250)

    def test_grant_mute_and_ban_actions(self):
        url = "/admin/users/user/"
        for action in ("grant_100", "mute_notes", "ban"):
            self.client.post(url, {"action": action, "_selected_action": [self.viewer.pk]})
        self.viewer.refresh_from_db()
        self.assertEqual(services.balance_of(self.viewer), 100)
        self.assertTrue(self.viewer.notes_muted)
        self.assertFalse(self.viewer.is_active)
        self.client.post(url, {"action": "ban", "_selected_action": [self.staff.pk]})
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)  # staff are never banned from here

    def test_credits_are_adjusted_on_the_viewers_page(self):
        url = reverse("admin:users_user_adjust_credits", args=[self.viewer.pk])
        self.assertContains(self.client.get(url), "holds <strong>0</strong>")
        self.client.post(url, {"amount": "50", "reason": "a lost meteor"})
        self.client.post(url, {"amount": "-20", "reason": "a mistaken grant"})
        self.assertEqual(services.balance_of(self.viewer), 30)
        self.assertContains(self.client.post(url, {"amount": "-31", "reason": "too much"}), "never goes below zero")
        self.assertContains(self.client.post(url, {"amount": "0", "reason": "nothing"}), "Zero changes nothing")
        self.assertEqual(services.balance_of(self.viewer), 30)
        from apps.credits.models import Entry
        self.assertEqual(Entry.objects.filter(user=self.viewer).first().ref, "a mistaken grant (keeper)")

    def test_the_rules_are_edited_on_one_page(self):
        from apps.rules.models import Rules
        self.client.post("/admin/rules/rules/1/change/", {"welcome_credits": "30", "power_every": "5",
                                                          "note_every": "120", "note_limit": "100",
                                                          "reports_to_hide": "4"})
        rules = Rules.get()
        self.assertEqual((rules.welcome_credits, rules.free_powers, rules.note_limit), (30, False, 100))
        self.assertEqual(self.client.post("/admin/rules/rules/1/change/", {
            "welcome_credits": "30", "power_every": "5", "note_every": "120", "note_limit": "200",
            "reports_to_hide": "4"}).status_code, 200)  # over 140: the form refuses it
        self.assertEqual(Rules.get().note_limit, 100)

    def test_notes_are_hidden_and_restored(self):
        note = Note.objects.create(author=self.viewer, text="hello")
        self.client.post("/admin/notes/note/", {"action": "hide", "_selected_action": [note.pk]})
        note.refresh_from_db()
        self.assertEqual(note.status, Note.HIDDEN)
        self.client.post("/admin/notes/note/", {"action": "restore", "_selected_action": [note.pk]})
        note.refresh_from_db()
        self.assertEqual(note.status, Note.SENT)

    def test_the_islands_logs(self):
        with tempfile.TemporaryDirectory() as run:
            (Path(run) / "world.log").write_text("first\n[Lua] SKY Stone #1 dropped\n")
            with override_settings(GODLING_RUN_DIR=run):
                self.assertContains(self.client.get(reverse("admin_logs")), "The island's logs")
                tail = self.client.get(reverse("admin_logs") + "?log=world", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
                self.assertIn("SKY Stone #1", tail.json()["content"])

    def test_the_admin_is_for_staff(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get("/admin/credits/power/").status_code, 302)
        self.assertEqual(self.client.get(reverse("admin_logs")).status_code, 302)
