"""The viewers' admin at its edges (grants, unmute, unban, credits refused, permissions) and the disposable-domain
tools (syncing the online lists, importing the bundled file, pasting a list); the log viewer; the validators' fallbacks."""
import io
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from apps.credits import services
from apps.notes.tests import code_entered, two_factor
from apps.users import admin as users_admin
from apps.users import validators
from apps.users.models import DisposableDomain, User


class ViewerAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(username="keeper", email="keeper@example.org",
                                                   password="an-island-test-pass-4127")
        self.client.force_login(two_factor(self.staff))
        code_entered(self.client)
        self.viewer = User.objects.create_user(username="tomv", email="tomv@example.org", password="x-test-pass-0001")

    def act(self, action):
        return self.client.post("/admin/users/user/", {"action": action, "_selected_action": [self.viewer.pk]},
                                follow=True)

    def test_grant_unmute_and_unban(self):
        self.assertContains(self.act("grant_20"), "Granted 20 credits to 1 viewer(s).")
        self.assertEqual(services.balance_of(self.viewer), 20)
        User.objects.filter(pk=self.viewer.pk).update(notes_muted=True, is_active=False)
        self.assertContains(self.act("unmute_notes"), "1 viewer(s) unmuted.")
        self.assertContains(self.act("unban"), "1 viewer(s) unbanned.")
        self.viewer.refresh_from_db()
        self.assertFalse(self.viewer.notes_muted)
        self.assertTrue(self.viewer.is_active)

    def test_a_purse_never_goes_below_zero(self):
        page = self.client.post(f"/admin/users/user/{self.viewer.pk}/credits/", {"amount": "-5", "reason": "oops"})
        self.assertContains(page, "tomv holds 0: a purse never goes below zero.")

    def test_staff_without_the_change_permission_cannot_adjust_credits(self):
        clerk = User.objects.create_user(username="clerk", email="clerk@example.org", password="x-test-pass-0003",
                                         is_staff=True)
        clerk.user_permissions.add(Permission.objects.get(codename="view_user"))
        self.client.force_login(two_factor(clerk))
        code_entered(self.client)
        response = self.client.get(f"/admin/users/user/{self.viewer.pk}/credits/")
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)


class DomainToolsTests(TestCase):
    def setUp(self):
        cache.clear()
        staff = User.objects.create_superuser(username="keeper", email="keeper@example.org",
                                              password="an-island-test-pass-4127")
        self.client.force_login(two_factor(staff))
        code_entered(self.client)

    def test_parsing_a_list(self):
        found = users_admin._parse_domain_text("# a comment\n\n.Spam.Example\nnot a domain\nok.io\nx.c\n")
        self.assertEqual(found, {"spam.example", "ok.io"})

    def test_the_tools_only_act_on_post(self):
        for tool in ("sync-online", "import-bundled", "import-manual"):
            response = self.client.get(f"/admin/users/disposabledomain/{tool}/")
            self.assertRedirects(response, "/admin/users/disposabledomain/", fetch_redirect_response=False)

    def test_syncing_the_online_lists_survives_one_source_down(self):
        def urlopen(url, timeout=None):
            if "fakefilter" in url:
                raise OSError("unreachable")
            return io.BytesIO(b"burner.example\n# note\nthrowaway.test\n")
        with mock.patch("apps.users.admin.urllib.request.urlopen", side_effect=urlopen):
            page = self.client.post("/admin/users/disposabledomain/sync-online/", follow=True)
        self.assertContains(page, "could not fetch data.txt")
        self.assertContains(page, "Online sync complete.")
        self.assertTrue(DisposableDomain.objects.filter(domain="burner.example", source="online").exists())

    def test_importing_the_bundled_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundled = Path(tmp) / "domains.txt"
            bundled.write_text("bundled-one.example\n")
            with mock.patch("apps.users.admin.DISPOSABLE_DOMAINS_FILE", bundled):
                page = self.client.post("/admin/users/disposabledomain/import-bundled/", follow=True)
            self.assertContains(page, "Bundled file import complete.")
            with mock.patch("apps.users.admin.DISPOSABLE_DOMAINS_FILE", Path(tmp) / "missing.txt"):
                page = self.client.post("/admin/users/disposabledomain/import-bundled/", follow=True)
            self.assertContains(page, "Bundled file not found.")
        self.assertTrue(DisposableDomain.objects.filter(domain="bundled-one.example").exists())

    def test_pasting_a_list(self):
        page = self.client.post("/admin/users/disposabledomain/import-manual/", {"domains_text": "nothing here"},
                                follow=True)
        self.assertContains(page, "No valid domains found in the pasted text.")
        page = self.client.post("/admin/users/disposabledomain/import-manual/", {"domains_text": "pasted.example"},
                                follow=True)
        self.assertContains(page, "Manual import complete. 1 new domain(s) added")
        page = self.client.post("/admin/users/disposabledomain/import-manual/", {"domains_text": "pasted.example"},
                                follow=True)
        self.assertContains(page, "0 new domain(s) added, 1 already existed")

    def test_switching_domains_and_their_words(self):
        domain = DisposableDomain.objects.create(domain="  Mixed.Example ")
        self.assertEqual(str(domain), "mixed.example")
        for action, word in (("deactivate_domains", "deactivated"), ("activate_domains", "activated")):
            page = self.client.post("/admin/users/disposabledomain/", {"action": action,
                                                                       "_selected_action": [domain.pk]}, follow=True)
            self.assertContains(page, f"1 domain(s) {word}.")


class LogViewerTests(TestCase):
    def setUp(self):
        staff = User.objects.create_superuser(username="keeper", email="keeper@example.org",
                                              password="an-island-test-pass-4127")
        self.client.force_login(two_factor(staff))
        code_entered(self.client)

    def logs(self, which):
        return self.client.get(f"/admin/logs/?log={which}", HTTP_X_REQUESTED_WITH="XMLHttpRequest").json()["content"]

    @override_settings(GODLING_RUN_DIR="")
    def test_without_a_run(self):
        self.assertIn("GODLING_RUN_DIR is not set", self.logs("mind"))

    def test_a_log_that_is_not_there_yet(self):
        with tempfile.TemporaryDirectory() as run, override_settings(GODLING_RUN_DIR=run):
            self.assertEqual(self.logs("panel"), "panel.log is not there (yet).")


class ValidatorFallbackTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_a_missing_bundled_file_leaves_the_fallback(self):
        with mock.patch.object(validators, "DISPOSABLE_DOMAINS_FILE", Path("/nowhere/domains.txt")):
            self.assertEqual(validators._load_bundled_domains(), set())

    def test_the_table_unreadable_leaves_nothing_from_it(self):
        with mock.patch("apps.users.models.DisposableDomain.objects") as objects:
            objects.values_list.side_effect = RuntimeError("no table yet")
            self.assertEqual(validators._load_db_domains(), (set(), set()))

    def test_usernames_and_emails(self):
        with self.assertRaises(ValidationError) as raised:
            validators.validate_username("x" * 30)
        self.assertEqual(raised.exception.code, "username_too_long")
        self.assertEqual(validators.normalize_email("no-at-sign"), "no-at-sign")
        self.assertEqual(validators.normalize_email(" Mara@Example.ORG "), "Mara@example.org")

    def test_a_username_too_short(self):
        with self.assertRaises(ValidationError) as raised:
            validators.validate_username(" ab ")
        self.assertEqual(raised.exception.code, "username_too_short")

    def test_an_offensive_username(self):
        with self.assertRaises(ValidationError) as raised:
            validators.validate_username("nazi_fan")
        self.assertEqual(raised.exception.code, "username_offensive")


class BlockedWordsFallbackTests(TestCase):
    def test_the_seed_holds_when_the_table_cannot_be_read(self):
        from apps.rules import words
        words.forget()
        with mock.patch("apps.rules.models.BlockedWord.objects") as objects:
            objects.filter.side_effect = RuntimeError("database away")
            self.assertIn("hitler", words.words("usernames"))
        words.forget()
