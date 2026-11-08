"""The admin, as staff use it: every page opens; prices are edited in their list; grants, mutes and bans work; the
island's logs show; staff need two-factor sign-in."""
import tempfile
from pathlib import Path

from allauth.account.internal.flows.login import AUTHENTICATION_METHODS_SESSION_KEY, record_authentication
from allauth.mfa.models import Authenticator
from django.contrib.auth import SESSION_KEY
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.credits import services
from apps.credits.models import Power
from apps.notes.models import Note
from apps.users.models import User


def two_factor(user):
    """As if the user had set up an authenticator app (allauth.mfa): what the admin asks of staff."""
    Authenticator.objects.create(user=user, type=Authenticator.Type.TOTP, data={"secret": "not-used-in-tests"})
    return user


def code_entered(client, ago=0):
    """As if this client's session had given its authenticator's code `ago` seconds ago, recorded by allauth itself
    (since 65.21 the records are tied to the signed-in user)."""
    session = client.session
    request = RequestFactory().get("/")
    request.session = session
    user = User.objects.get(pk=session[SESSION_KEY])
    record_authentication(request, user, "password")
    record_authentication(request, user, "mfa", type="totp")
    for record in session[AUTHENTICATION_METHODS_SESSION_KEY][-2:]:
        record["at"] -= ago
    session.save()


class AdminTests(TestCase):
    def setUp(self):
        self.staff = two_factor(User.objects.create_superuser(username="keeper", email="keeper@example.org",
                                                              password="an-island-test-pass-4127"))
        self.client.force_login(self.staff)
        code_entered(self.client)
        self.viewer = User.objects.create_user(username="tomv", email="tomv@example.org",
                                               password="an-island-test-pass-4127")

    def test_every_list_opens(self):
        for model in ("users/user", "users/disposabledomain", "credits/power", "credits/creditpack", "credits/purse",
                      "credits/entry", "credits/powercall", "credits/payment", "credits/stripeevent", "notes/note",
                      "notes/report",
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
        reports = {"reports_to_hide": "4", "report_min_age_hours": "48", "reports_per_hour": "5",
                   "feedback_per_hour": "3", "feedback_email": "makers@example.org"}
        self.client.post("/admin/rules/rules/1/change/", {"welcome_credits": "30", "power_every": "5",
                                                          "note_every": "120", "note_limit": "100", **reports})
        rules = Rules.get()
        self.assertEqual((rules.welcome_credits, rules.free_powers, rules.note_limit), (30, False, 100))
        self.assertEqual((rules.report_min_age_hours, rules.reports_per_hour), (48, 5))
        self.assertEqual((rules.feedback_per_hour, rules.feedback_email), (3, "makers@example.org"))
        self.assertEqual(self.client.post("/admin/rules/rules/1/change/", {
            "welcome_credits": "30", "power_every": "5", "note_every": "120", "note_limit": "200",
            **reports}).status_code, 200)  # over 140: the form refuses it
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

    def test_staff_without_two_factor_set_it_up_first(self):
        newcomer = User.objects.create_user(username="newkeeper", email="newkeeper@example.org",
                                            password="an-island-test-pass-4127", is_staff=True, is_superuser=True)
        self.client.force_login(newcomer)
        for page in ("/admin/", "/admin/credits/power/", reverse("admin_logs")):
            self.assertRedirects(self.client.get(page), reverse("mfa_activate_totp"), fetch_redirect_response=False)
        self.assertEqual(self.client.get("/watch").status_code, 200)  # the screen itself asks nothing of them
        two_factor(newcomer)
        code_entered(self.client)
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_a_password_only_session_is_asked_for_a_code(self):
        """The reviewer's case: signed in with a password on one device, an authenticator set up on another. This
        session never gave a code, so the admin asks it for one; a code given 13 hours ago no longer counts."""
        self.client.logout()
        self.client.force_login(self.staff)  # a fresh session: a password, no code
        ask = f"{reverse('mfa_reauthenticate')}?next=%2Fadmin%2Fcredits%2Fpower%2F"
        self.assertRedirects(self.client.get("/admin/credits/power/"), ask, fetch_redirect_response=False)
        code_entered(self.client, ago=13 * 3600)
        self.assertRedirects(self.client.get("/admin/credits/power/"), ask, fetch_redirect_response=False)
        code_entered(self.client)
        self.assertEqual(self.client.get("/admin/credits/power/").status_code, 200)

    def test_a_real_code_on_allauths_screen_opens_the_admin(self):
        """End to end, with a real authenticator: the code typed on allauth's screen is what the admin then sees."""
        from allauth.mfa.totp.internal.auth import (TOTP, format_hotp_value, generate_totp_secret, hotp_value,
                                                     yield_hotp_counters_from_time)

        keeper = User.objects.create_user(username="keeper2", email="keeper2@example.org",
                                          password="an-island-test-pass-4127", is_staff=True, is_superuser=True)
        secret = generate_totp_secret()
        TOTP.activate(keeper, secret)
        self.client.logout()
        self.client.force_login(keeper)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        code = format_hotp_value(hotp_value(secret, next(yield_hotp_counters_from_time())))
        self.client.post(reverse("mfa_reauthenticate"), {"code": code})
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_the_admin_signs_in_through_the_site(self):
        """Django's own admin form would skip the site's rate limits and the two-factor code."""
        self.client.logout()
        response = self.client.get("/admin/login/?next=/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("account_login")))
        self.assertEqual(self.client.post("/admin/login/", {"username": "keeper@example.org",
                                                            "password": "an-island-test-pass-4127"}).status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_staff_need_the_permission_for_imports_and_actions(self):
        """A staff account allowed only to look (view permissions) imports no domains and runs no actions."""
        from django.contrib.auth.models import Permission

        from apps.users.models import DisposableDomain
        looker = two_factor(User.objects.create_user(username="looker", email="looker@example.org",
                                                     password="an-island-test-pass-4127", is_staff=True))
        looker.user_permissions.add(*Permission.objects.filter(codename__in=(
            "view_disposabledomain", "view_user", "view_note")))
        self.client.force_login(looker)
        code_entered(self.client)
        page = self.client.get("/admin/users/disposabledomain/")
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Add Domains")  # no import forms for someone who may not add
        self.assertEqual(self.client.post(reverse("admin:users_disposabledomain_import_manual"),
                                          {"domains_text": "sneaky.example"}).status_code, 403)
        self.assertFalse(DisposableDomain.objects.filter(domain="sneaky.example").exists())
        note = Note.objects.create(author=self.viewer, text="hello")
        self.client.post("/admin/users/user/", {"action": "grant_100", "_selected_action": [self.viewer.pk]})
        self.client.post("/admin/notes/note/", {"action": "hide", "_selected_action": [note.pk]})
        note.refresh_from_db()
        self.assertEqual((services.balance_of(self.viewer), note.status), (0, Note.SENT))
        # With the add permission, the import works.
        looker.user_permissions.add(Permission.objects.get(codename="add_disposabledomain"))
        self.client.post(reverse("admin:users_disposabledomain_import_manual"), {"domains_text": "sneaky.example"})
        self.assertTrue(DisposableDomain.objects.filter(domain="sneaky.example").exists())
