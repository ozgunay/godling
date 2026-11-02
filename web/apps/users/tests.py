"""Signing up as a viewer: the allauth flow as AgentOp has it, with Godling's username rules."""
import re

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.users.models import User

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

    def test_the_sign_in_page_wears_the_island(self):
        response = self.client.get(reverse("account_login"))
        self.assertContains(response, "Back to the island")
        self.assertContains(response, "Tiny5")
