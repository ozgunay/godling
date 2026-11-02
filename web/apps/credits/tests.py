"""Credits: welcome credits once, buying packs through Stripe (mocked) or the development checkout, credited once."""
import re
from types import SimpleNamespace
from unittest import mock

import stripe
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.credits import services
from apps.credits.models import CreditPack, Entry, Payment
from apps.users.models import User

PASSWORD = "an-island-test-pass-4127"


def make_user(name="tomv"):
    return User.objects.create_user(username=name, email=f"{name}@example.org", password=PASSWORD)


class WelcomeTests(TestCase):
    def setUp(self):
        cache.clear()  # allauth's 3-minute cooldown between confirmation emails lives in the cache

    def test_twenty_credits_on_confirming_the_email_once(self):
        self.client.post(reverse("account_signup"), {"username": "mara_k", "email": "mara@example.org",
                                                     "password1": PASSWORD, "password2": PASSWORD})
        link = re.search(r"https?://\S+/accounts/confirm-email/\S+/", mail.outbox[-1].body).group(0)
        self.client.post(link)
        user = User.objects.get(username="mara_k")
        self.assertEqual(services.balance_of(user), 20)
        self.assertFalse(services.welcome(user))
        self.assertEqual(services.balance_of(user), 20)


class LedgerTests(TestCase):
    def test_every_change_is_an_entry_and_the_balance_never_goes_below_zero(self):
        user = make_user()
        services.change(user, 10, Entry.GRANT, "test")
        services.spend(user, 4, "Stone")
        with self.assertRaises(services.NotEnough):
            services.spend(user, 40, "Lightning")
        self.assertEqual(services.balance_of(user), 6)
        self.assertEqual([e.balance_after for e in Entry.objects.filter(user=user)], [6, 10])


@override_settings(DEBUG=True, GODLING_STRIPE_SECRET_KEY="")
class TestCheckoutTests(TestCase):
    def test_the_development_checkout_credits_a_pack_once(self):
        user = make_user()
        self.client.force_login(user)
        page = self.client.get(reverse("credits"))
        self.assertContains(page, "test checkout")
        self.assertContains(page, "€5.00")
        response = self.client.post(reverse("credits_buy", args=["bag"]))
        payment = Payment.objects.get()
        self.assertRedirects(response, reverse("credits_test_checkout", args=[payment.session]))
        url = reverse("credits_test_checkout", args=[payment.session])
        self.client.post(url)
        self.client.post(url)  # twice: credited once
        self.assertEqual(services.balance_of(user), 320)
        self.assertEqual(Payment.objects.get().status, Payment.PAID)


@override_settings(DEBUG=False, GODLING_STRIPE_SECRET_KEY="")
class NoPaymentsTests(TestCase):
    def test_without_stripe_in_production_nothing_is_sold(self):
        self.client.force_login(make_user())
        self.assertContains(self.client.get(reverse("credits")), "not set up yet")
        self.client.post(reverse("credits_buy", args=["bag"]))
        self.assertFalse(Payment.objects.exists())


@override_settings(GODLING_STRIPE_SECRET_KEY="sk_test_x", GODLING_STRIPE_WEBHOOK_SECRET="whsec_x")
class StripeTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def buy(self):
        with mock.patch("stripe.checkout.Session.create",
                        return_value=SimpleNamespace(id="cs_test_1", url="https://checkout.stripe.com/c/cs_test_1")) as create:
            response = self.client.post(reverse("credits_buy", args=["handful"]))
        return response, create

    def test_buying_opens_stripe_checkout_for_the_pack(self):
        response, create = self.buy()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://checkout.stripe.com/c/cs_test_1")
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["line_items"][0]["price_data"]["unit_amount"], 500)
        self.assertEqual(kwargs["metadata"]["credits"], "100")
        self.assertEqual(Payment.objects.get().status, Payment.OPEN)

    def webhook(self, event):
        with mock.patch("stripe.Webhook.construct_event", return_value=event):
            return self.client.post(reverse("credits_stripe_webhook"), b"{}", content_type="application/json",
                                    HTTP_STRIPE_SIGNATURE="t=1,v1=x")

    def test_the_webhook_credits_a_paid_checkout_once(self):
        self.buy()
        event = {"type": "checkout.session.completed", "data": {"object": {"id": "cs_test_1", "payment_status": "paid"}}}
        self.assertEqual(self.webhook(event).status_code, 200)
        self.assertEqual(self.webhook(event).status_code, 200)  # Stripe retries: still credited once
        self.assertEqual(services.balance_of(self.user), 100)

    def test_an_unpaid_or_expired_checkout_credits_nothing(self):
        self.buy()
        self.webhook({"type": "checkout.session.completed",
                      "data": {"object": {"id": "cs_test_1", "payment_status": "unpaid"}}})
        self.webhook({"type": "checkout.session.expired", "data": {"object": {"id": "cs_test_1"}}})
        self.assertEqual(services.balance_of(self.user), 0)
        self.assertEqual(Payment.objects.get().status, Payment.EXPIRED)

    def test_a_forged_webhook_is_refused(self):
        response = self.client.post(reverse("credits_stripe_webhook"), b"{}", content_type="application/json",
                                    HTTP_STRIPE_SIGNATURE="t=1,v1=forged")
        self.assertEqual(response.status_code, 400)

    def test_the_return_page_asks_stripe_when_the_webhook_is_late(self):
        self.buy()
        with mock.patch("stripe.checkout.Session.retrieve", return_value=SimpleNamespace(payment_status="paid")):
            page = self.client.get(reverse("credits_done") + "?session_id=cs_test_1")
        self.assertContains(page, "100 credits are in your purse")
        self.assertEqual(services.balance_of(self.user), 100)

    def test_packs_come_from_the_admin(self):
        CreditPack.objects.filter(key="handful").update(active=False)
        page = self.client.get(reverse("credits"))
        self.assertNotContains(page, "A handful")
        self.assertContains(page, "A chest")


class StripeErrorTests(TestCase):
    def test_stripe_errors_are_importable_where_the_views_expect_them(self):
        self.assertTrue(issubclass(stripe.SignatureVerificationError, Exception))
        self.assertTrue(issubclass(stripe.StripeError, Exception))
