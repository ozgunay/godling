"""Credits at their edges: the records' words in the admin, Stripe answering badly, the development checkout outside
development, and two confirmations of one email at once."""
from types import SimpleNamespace
from unittest import mock

import stripe
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.credits import services
from apps.credits.admin import CreditPackAdmin, PaymentAdmin, PowerCallAdmin
from apps.credits.models import CreditPack, Entry, Payment, Power, PowerCall, Purse
from apps.credits.views import money
from apps.users.models import User


def make_user(name="tomv"):
    return User.objects.create_user(username=name, email=f"{name}@example.org", password="an-island-test-pass-4127")


class RecordTests(TestCase):
    def test_how_records_read(self):
        user = make_user()
        services.change(user, 7, Entry.GRANT, "x")
        self.assertEqual(str(Purse.objects.get(user=user)), "tomv: 7 cr")
        self.assertEqual(str(Entry.objects.get(user=user)), "tomv +7 (grant)")
        call = PowerCall.objects.create(user=user, power="Stone", price=4, ok=False)
        self.assertEqual(str(call), "tomv Stone (refused)")
        payment = Payment.objects.create(user=user, pack="bag", credits=50, amount_cents=500, currency="eur",
                                         session="s1")
        self.assertEqual(str(payment), "tomv: 50 cr, open")
        self.assertEqual(str(Power.objects.get(key="Meteor")), "Meteor (300 cr)")
        self.assertTrue(str(CreditPack.objects.first()).endswith(")") or ":" in str(CreditPack.objects.first()))

    def test_admin_columns(self):
        user = make_user()
        self.assertEqual(PowerCallAdmin.aimed(None, SimpleNamespace(at_x=3.4, at_z=-1.6)), "(3, -2)")
        self.assertEqual(PowerCallAdmin.aimed(None, SimpleNamespace(at_x=None, at_z=None)), "the sky chose")
        self.assertEqual(PaymentAdmin.amount(None, SimpleNamespace(amount_cents=1250, currency="eur")), "12.50 EUR")
        self.assertEqual(CreditPackAdmin.per_credit(None, SimpleNamespace(price_cents=500, credits=100)), "5.00")
        self.assertEqual(CreditPackAdmin.per_credit(None, SimpleNamespace(price_cents=500, credits=0)), "-")
        self.assertTrue(user.pk)

    def test_prices_follow_the_enabled_powers(self):
        Power.objects.filter(key="Earthquake").update(enabled=False)
        prices = services.prices()
        self.assertEqual(prices["Meteor"], 300)
        self.assertNotIn("Earthquake", prices)

    def test_two_confirmations_at_once_give_the_welcome_once(self):
        user = make_user()
        with mock.patch("apps.credits.services.change", side_effect=IntegrityError("one_welcome_per_user")):
            self.assertFalse(services.welcome(user))

    def test_nothing_to_credit(self):
        self.assertFalse(services.credit_payment("no-such-session"))

    @override_settings(GODLING_CURRENCY="chf")
    def test_money_without_a_symbol(self):
        self.assertEqual(money(1999), "19.99 CHF")


@override_settings(DEBUG=False, GODLING_STRIPE_SECRET_KEY="sk_test_x", GODLING_STRIPE_WEBHOOK_SECRET="")
class StripeEdgeTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.payment = Payment.objects.create(user=self.user, pack="handful", credits=100, amount_cents=500,
                                              currency="eur", session="cs_test_9")

    def test_the_development_checkout_is_not_there(self):
        self.assertEqual(self.client.get(reverse("credits_test_checkout", args=["cs_test_9"])).status_code, 404)

    def test_stripe_failing_on_the_return_page_leaves_it_to_the_webhook(self):
        with mock.patch("stripe.checkout.Session.retrieve", side_effect=stripe.APIConnectionError("down")):
            page = self.client.get(reverse("credits_done") + "?session_id=cs_test_9")
        self.assertEqual(page.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.OPEN)

    def test_a_webhook_without_its_secret_is_refused(self):
        response = self.client.post(reverse("credits_stripe_webhook"), b"{}", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b"not set up")
