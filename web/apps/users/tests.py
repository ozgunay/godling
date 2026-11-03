"""Signing up as a viewer: the allauth flow as AgentOp has it, with Godling's username rules."""
import re

from allauth.core.internal.httpkit import get_client_ip
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.users import validators
from apps.users.models import DisposableDomain, User

PASSWORD = "an-island-test-pass-4127"


def signup(client, username="mara_k", email="mara@example.org"):
    return client.post(reverse("account_signup"), {"username": username, "email": email, "password1": PASSWORD,
                                                   "password2": PASSWORD})


class SignupTests(TestCase):
    def setUp(self):
        cache.clear()  # allauth's 3-minute cooldown between confirmation emails lives in the cache

    def test_signup_needs_the_email_confirmed_before_signing_in(self):
        response = signup(self.client)
        self.assertRedirects(response, reverse("account_email_verification_sent"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Confirm your email", mail.outbox[0].subject)
        # Not signed in yet, and signing in is refused until the email is confirmed.
        self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.post(reverse("account_login"), {"login": "mara@example.org", "password": PASSWORD})
        self.assertNotIn("_auth_user_id", self.client.session)
        link = re.search(r"https?://\S+/accounts/confirm-email/\S+/", mail.outbox[-1].body).group(0)
        self.client.post(link)
        response = self.client.post(reverse("account_login"), {"login": "mara@example.org", "password": PASSWORD})
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), User.objects.get(username="mara_k").pk)

    def test_reserved_long_and_offensive_usernames_are_refused(self):
        for name in ("Godling", "sky", "admin", "a" * 19, "xXfuckXx"):
            signup(self.client, username=name, email=f"{len(name)}{name[:3]}@example.org")
            self.assertFalse(User.objects.filter(username=name).exists(), name)
        signup(self.client, username="grapefan", email="grape@example.org")
        self.assertTrue(User.objects.filter(username="grapefan").exists())

    def test_disposable_email_is_refused(self):
        response = signup(self.client, email="someone@mailinator.com")
        self.assertFalse(User.objects.exists())
        self.assertContains(response, "permanent email address")

    def test_a_domain_added_by_hand_keeps_the_bundled_list(self):
        bundled = next(d for d in validators._load_bundled_domains() if d not in validators.FALLBACK_DISPOSABLE_DOMAINS)
        DisposableDomain.objects.create(domain="throwaway-by-hand.example")
        cache.clear()
        domains = validators.get_disposable_domains()
        self.assertIn("throwaway-by-hand.example", domains)
        self.assertIn(bundled, domains)  # a fresh deployment's first row no longer replaces the ~74k bundled domains
        self.assertGreater(len(domains), 50000)
        DisposableDomain.objects.create(domain=bundled, is_active=False)  # a moderator unblocks a bundled domain
        cache.clear()
        self.assertNotIn(bundled, validators.get_disposable_domains())

    @override_settings(ALLAUTH_TRUSTED_PROXY_COUNT=1)
    def test_rate_limits_see_each_viewer_behind_caddy(self):
        caddy = {"REMOTE_ADDR": "172.18.0.5"}
        one = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="203.0.113.7", **caddy)
        two = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="198.51.100.20", **caddy)
        self.assertEqual((get_client_ip(one), get_client_ip(two)), ("203.0.113.7", "198.51.100.20"))

    def test_one_key_per_inbox(self):
        same = ("mara@example.org", "Mara+island@Example.org", "mara+x+y@example.org")
        self.assertEqual({validators.canonical_email(e) for e in same}, {"mara@example.org"})
        gmail = ("j.o.e@gmail.com", "joe+1@googlemail.com", "JOE@gmail.com")
        self.assertEqual({validators.canonical_email(e) for e in gmail}, {"joe@gmail.com"})
        self.assertNotEqual(validators.canonical_email("j.o.e@example.org"), validators.canonical_email("joe@example.org"))
        user = User.objects.create_user(username="joe", email="J.oe+tv@gmail.com", password=PASSWORD)
        self.assertEqual(user.email_key, "joe@gmail.com")
        user.email = "joe2@example.org"
        user.save(update_fields=["email"])
        user.refresh_from_db()
        self.assertEqual(user.email_key, "joe2@example.org")

    def test_the_sign_in_page_wears_the_island(self):
        response = self.client.get(reverse("account_login"))
        self.assertContains(response, "Back to the island")
        self.assertContains(response, "Tiny5")
