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

    def test_one_welcome_per_inbox(self):
        """me+2@ is me@'s inbox: a second account from it may watch and buy, but gets no second gift."""
        first = User.objects.create_user(username="sam", email="sam@gmail.com", password=PASSWORD)
        again = User.objects.create_user(username="sam2", email="S.am+island@googlemail.com", password=PASSWORD)
        other = User.objects.create_user(username="ana", email="ana@gmail.com", password=PASSWORD)
        self.assertEqual(again.email_key, "sam@gmail.com")
        self.assertTrue(services.welcome(first))
        self.assertFalse(services.welcome(again))
        self.assertTrue(services.welcome(other))
        self.assertEqual([services.balance_of(u) for u in (first, again, other)], [20, 0, 20])


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
        self.assertEqual(self.webhook({**event, "id": "evt_other"}).status_code, 200)  # even as another event
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

    events = 0

    def event(self, kind, thing, event_id=None):
        """A Stripe event as the webhook receives it, each with its own id unless one is given (a redelivery)."""
        StripeTests.events += 1
        return self.webhook({"id": event_id or f"evt_{StripeTests.events}", "type": kind, "data": {"object": thing}})

    def completed(self, event_id=None):
        return self.event("checkout.session.completed",
                          {"id": "cs_test_1", "payment_status": "paid", "payment_intent": "pi_1"}, event_id)

    def paid(self):
        self.buy()
        self.completed()
        return Payment.objects.get()

    def charge(self, kind, event_id=None, **fields):
        thing = {"payment_intent": "pi_1", **({"id": "dp_1"} if kind.startswith("charge.dispute.") else {}), **fields}
        return self.event(kind, thing, event_id)

    def test_a_refund_takes_its_share_of_the_credits_back(self):
        payment = self.paid()
        self.assertEqual(payment.payment_intent, "pi_1")
        self.charge("charge.refunded", amount=500, amount_refunded=100)  # a fifth of the €5.00
        self.assertEqual(services.balance_of(self.user), 80)
        self.charge("charge.refunded", amount=500, amount_refunded=100)  # Stripe retries: taken once
        self.assertEqual(services.balance_of(self.user), 80)
        self.charge("charge.refunded", amount=500, amount_refunded=500)  # the rest, later
        self.assertEqual(services.balance_of(self.user), 0)
        self.assertEqual(Payment.objects.get().status, Payment.REFUNDED)
        self.assertEqual(Entry.objects.filter(user=self.user, kind=Entry.CLAWBACK).count(), 2)

    def test_spent_credits_are_owed_and_paid_from_what_comes_next(self):
        self.paid()
        services.spend(self.user, 70, "Meteor")
        self.charge("charge.refunded", amount=500, amount_refunded=500)
        purse = self.user.purse
        purse.refresh_from_db()
        self.assertEqual((purse.balance, purse.owed), (0, 70))
        with self.assertRaises(services.NotEnough):
            services.spend(self.user, 4, "Stone")
        services.change(self.user, 100, Entry.GRANT, "a later pack")
        purse.refresh_from_db()
        self.assertEqual((purse.balance, purse.owed), (30, 0))

    def test_a_dispute_holds_the_credits_until_the_bank_decides(self):
        self.paid()
        self.charge("charge.dispute.created", status="needs_response")
        self.assertEqual(services.balance_of(self.user), 0)
        self.assertEqual(Payment.objects.get().status, Payment.DISPUTED)
        self.charge("charge.dispute.closed", status="won")
        self.assertEqual(services.balance_of(self.user), 100)
        self.assertEqual(Payment.objects.get().status, Payment.PAID)
        self.charge("charge.dispute.created", status="needs_response", id="dp_2")  # another dispute, later
        self.charge("charge.dispute.closed", status="lost", id="dp_2")
        self.assertEqual(services.balance_of(self.user), 0)

    def test_a_repeated_or_late_dispute_event_never_reopens_a_decided_dispute(self):
        """Stripe may send an event again, or out of order (the reviewer's 100 → 0 → 100 → 0)."""
        self.paid()
        self.charge("charge.dispute.created", event_id="evt_dp_created", status="needs_response")
        self.charge("charge.dispute.closed", status="won")
        self.charge("charge.dispute.created", event_id="evt_dp_created", status="needs_response")  # redelivered
        self.charge("charge.dispute.updated", status="under_review")  # a late update about the same dispute
        self.assertEqual(services.balance_of(self.user), 100)
        self.assertEqual(Payment.objects.get().status, Payment.PAID)

    def test_a_close_that_arrives_before_its_dispute_holds(self):
        self.paid()
        self.charge("charge.dispute.closed", status="won")
        self.charge("charge.dispute.created", status="needs_response")
        self.assertEqual(services.balance_of(self.user), 100)

    def test_a_refund_that_arrives_before_the_checkout_is_kept(self):
        """The reviewer's case: a full refund first, the checkout's own event after, and no spendable credits."""
        self.buy()
        listed = SimpleNamespace(data=[SimpleNamespace(id="cs_test_1")])
        with mock.patch("stripe.checkout.Session.list", return_value=listed):
            self.assertEqual(self.charge("charge.refunded", amount=500, amount_refunded=500).status_code, 200)
        self.assertEqual(services.balance_of(self.user), 0)
        self.completed()
        payment = Payment.objects.get()
        self.assertEqual((services.balance_of(self.user), payment.status, payment.granted), (0, Payment.REFUNDED, 0))

    def test_a_partly_refunded_checkout_reported_late_grants_the_rest(self):
        self.buy()
        listed = SimpleNamespace(data=[SimpleNamespace(id="cs_test_1")])
        with mock.patch("stripe.checkout.Session.list", return_value=listed):
            self.charge("charge.refunded", amount=500, amount_refunded=250)
        self.completed()
        self.assertEqual(services.balance_of(self.user), 50)

    def test_an_event_delivered_twice_is_applied_once(self):
        self.paid()
        services.spend(self.user, 30, "Meteor")
        self.charge("charge.refunded", event_id="evt_refund", amount=500, amount_refunded=100)
        self.charge("charge.refunded", event_id="evt_refund", amount=500, amount_refunded=100)
        self.assertEqual(services.balance_of(self.user), 50)
        self.assertEqual(Entry.objects.filter(user=self.user, kind=Entry.CLAWBACK).count(), 1)

    def test_stripe_out_of_reach_asks_for_the_event_again(self):
        """The reviewer's case: the lookup fails; the webhook says 503 so Stripe sends it again, and applies nothing."""
        self.buy()
        services.credit_payment("cs_test_1")  # its intent not kept yet: the refund needs Stripe to find it
        with mock.patch("stripe.checkout.Session.list", side_effect=stripe.APIConnectionError("no route")):
            answer = self.charge("charge.refunded", event_id="evt_retry", amount=500, amount_refunded=500)
        self.assertEqual(answer.status_code, 503)
        self.assertEqual(services.balance_of(self.user), 100)
        listed = SimpleNamespace(data=[SimpleNamespace(id="cs_test_1")])
        with mock.patch("stripe.checkout.Session.list", return_value=listed):
            self.assertEqual(self.charge("charge.refunded", event_id="evt_retry", amount=500,
                                         amount_refunded=500).status_code, 200)
        self.assertEqual(services.balance_of(self.user), 0)

    def test_an_event_about_someone_elses_payment_is_acknowledged(self):
        with mock.patch("stripe.checkout.Session.list", return_value=SimpleNamespace(data=[])):
            self.assertEqual(self.charge("charge.refunded", amount=500, amount_refunded=500).status_code, 200)

    def test_a_refund_during_a_dispute_is_not_given_back_when_the_dispute_is_won(self):
        self.paid()
        self.charge("charge.dispute.created", status="needs_response")
        self.charge("charge.refunded", amount=500, amount_refunded=100)  # a fifth refunded meanwhile
        self.charge("charge.dispute.closed", status="won")
        self.assertEqual(services.balance_of(self.user), 80)

    def test_a_payment_credited_before_its_intent_was_kept_is_found_through_stripe(self):
        self.buy()
        services.credit_payment("cs_test_1")  # as the return page did before payment intents were kept
        listed = SimpleNamespace(data=[SimpleNamespace(id="cs_test_1")])
        with mock.patch("stripe.checkout.Session.list", return_value=listed) as lookup:
            self.charge("charge.refunded", amount=500, amount_refunded=500)
        self.assertEqual(lookup.call_args.kwargs["payment_intent"], "pi_1")
        self.assertEqual(services.balance_of(self.user), 0)
        self.assertEqual(Payment.objects.get().payment_intent, "pi_1")

    def test_packs_come_from_the_admin(self):
        CreditPack.objects.filter(key="handful").update(active=False)
        page = self.client.get(reverse("credits"))
        self.assertNotContains(page, "A handful")
        self.assertContains(page, "A chest")


class StripeErrorTests(TestCase):
    def test_stripe_errors_are_importable_where_the_views_expect_them(self):
        self.assertTrue(issubclass(stripe.SignatureVerificationError, Exception))
        self.assertTrue(issubclass(stripe.StripeError, Exception))
