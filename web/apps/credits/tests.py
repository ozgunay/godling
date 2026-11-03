"""Credits: welcome credits once, buying packs through Stripe (mocked) or the development checkout, credited once, and
Stripe's refunds and disputes taken back exactly, whatever order and however often Stripe tells of them; and live keys
waiting for an outside security review."""
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest import mock

import stripe
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from apps.credits import services
from apps.credits.models import CreditPack, Entry, Payment, StripeEvent, Welcome
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

    def test_a_deleted_account_does_not_free_its_inbox_for_another_gift(self):
        first = User.objects.create_user(username="sam", email="sam@gmail.com", password=PASSWORD)
        services.welcome(first)
        first.delete()
        self.assertTrue(Welcome.objects.filter(email_key="sam@gmail.com").exists())
        again = User.objects.create_user(username="sam3", email="sam@gmail.com", password=PASSWORD)
        self.assertFalse(services.welcome(again))
        self.assertEqual(services.balance_of(again), 0)


class LedgerTests(TestCase):
    def test_every_change_is_an_entry_and_the_balance_never_goes_below_zero(self):
        user = make_user()
        services.change(user, 10, Entry.GRANT, "test")
        services.spend(user, 4, "Stone")
        with self.assertRaises(services.NotEnough):
            services.spend(user, 40, "Lightning")
        self.assertEqual(services.balance_of(user), 6)
        self.assertEqual([e.balance_after for e in Entry.objects.filter(user=user)], [6, 10])

    def test_a_pack_costs_at_least_what_stripe_can_charge_and_gives_credits(self):
        for credits, cents in ((0, 500), (100, 0), (100, 49)):
            with self.assertRaises(ValidationError):
                CreditPack(key="x", name="x", credits=credits, price_cents=cents).full_clean()
        CreditPack(key="ok", name="ok", credits=1, price_cents=50).full_clean()


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
    """Stripe stands in here as it behaves: it keeps the charge and the dispute as they are now (what retrieve gives),
    and an event carries a copy of one, which may be older."""

    events = 0

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.charge_now = {"object": "charge", "id": "ch_1", "payment_intent": "pi_1", "amount": 500,
                           "amount_refunded": 0}
        self.disputes = {}
        for target, now in (("stripe.Charge.retrieve", lambda charge_id, **kw: dict(self.charge_now)),
                            ("stripe.Dispute.retrieve", lambda dispute_id, **kw: dict(self.disputes[dispute_id]))):
            patcher = mock.patch(target, side_effect=now)
            patcher.start()
            self.addCleanup(patcher.stop)

    def buy(self, session_id="cs_test_1"):
        made = SimpleNamespace(id=session_id, url=f"https://checkout.stripe.com/c/{session_id}")
        with mock.patch("stripe.checkout.Session.create", return_value=made) as create:
            response = self.client.post(reverse("credits_buy", args=["handful"]))
        return response, create

    def webhook(self, event):
        with mock.patch("stripe.Webhook.construct_event", return_value=event):
            return self.client.post(reverse("credits_stripe_webhook"), b"{}", content_type="application/json",
                                    HTTP_STRIPE_SIGNATURE="t=1,v1=x")

    def event(self, kind, thing, event_id=None, livemode=False):
        """A Stripe event as the webhook receives it, each with its own id unless one is given (a redelivery)."""
        StripeTests.events += 1
        return self.webhook({"id": event_id or f"evt_{StripeTests.events}", "type": kind, "livemode": livemode,
                             "data": {"object": thing}})

    def session(self, **fields):
        payment = Payment.objects.order_by("-pk").first()
        return {"object": "checkout.session", "id": "cs_test_1", "payment_status": "paid", "payment_intent": "pi_1",
                "amount_total": 500, "currency": "eur",
                "metadata": {"payment": str(payment.pk), "user": str(payment.user_id)}, **fields}

    def completed(self, event_id=None, **fields):
        return self.event("checkout.session.completed", self.session(**fields), event_id)

    def paid(self):
        self.buy()
        self.completed()
        return Payment.objects.get()

    def refund_to(self, cents, kind="charge.refunded", event_id=None):
        """Stripe's charge now shows `cents` refunded; the event says so (a charge, or one of its refunds)."""
        self.charge_now["amount_refunded"] = cents
        thing = (dict(self.charge_now) if kind == "charge.refunded" else
                 {"object": "refund", "id": "re_1", "charge": "ch_1", "payment_intent": "pi_1"})
        return self.event(kind, thing, event_id)

    def dispute(self, status, kind="charge.dispute.updated", event_id=None, dispute_id="dp_1", amount=500, old=False):
        """A dispute event. With `old`, the event carries an older copy: Stripe's dispute stays as it is now."""
        thing = {"object": "dispute", "id": dispute_id, "payment_intent": "pi_1", "status": status, "amount": amount}
        if not old:
            self.disputes[dispute_id] = dict(thing)
        return self.event(kind, thing, event_id)

    def purse(self):
        purse = self.user.purse
        purse.refresh_from_db()
        return purse.balance, purse.owed

    def stripe_finds_the_session(self):
        """Stripe's session list for the payment intent: how a payment whose intent is not kept yet is found."""
        return mock.patch("stripe.checkout.Session.list",
                          return_value=SimpleNamespace(data=[SimpleNamespace(id="cs_test_1")]))

    # -- buying -------------------------------------------------------------------------------------------------

    def test_buying_opens_stripe_checkout_for_the_pack(self):
        response, create = self.buy()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://checkout.stripe.com/c/cs_test_1")
        payment = Payment.objects.get()
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["line_items"][0]["price_data"]["unit_amount"], 500)
        self.assertEqual(kwargs["metadata"], {"payment": str(payment.pk), "user": str(self.user.pk), "pack": "handful",
                                              "credits": "100"})
        self.assertEqual(kwargs["payment_intent_data"]["metadata"]["payment"], str(payment.pk))
        self.assertEqual(kwargs["idempotency_key"], f"godling-payment-{payment.pk}")
        self.assertEqual((payment.session, payment.status), ("cs_test_1", Payment.OPEN))

    def test_stripe_not_answering_charges_nothing_and_shows_why(self):
        with mock.patch("stripe.checkout.Session.create", side_effect=stripe.APIConnectionError("no route")):
            response = self.client.post(reverse("credits_buy", args=["handful"]), follow=True)
        self.assertContains(response, "nothing was charged")
        self.assertEqual(Payment.objects.get().status, Payment.EXPIRED)

    def test_a_paid_checkout_whose_session_was_never_saved_is_found_by_its_payment(self):
        """The server stopped between Stripe making the session and saving its id: the payment is still found."""
        self.buy()
        payment = Payment.objects.get()
        Payment.objects.filter(pk=payment.pk).update(session=f"{Payment.PENDING}lost")
        self.completed()
        payment.refresh_from_db()
        self.assertEqual((payment.session, payment.status, services.balance_of(self.user)),
                         ("cs_test_1", Payment.PAID, 100))

    def test_the_metadata_must_name_the_payments_own_viewer(self):
        self.buy()
        payment = Payment.objects.get()
        Payment.objects.filter(pk=payment.pk).update(session=f"{Payment.PENDING}lost")
        self.completed(metadata={"payment": str(payment.pk), "user": "999"})
        self.assertEqual(services.balance_of(self.user), 0)
        self.assertIn("matched no payment", StripeEvent.objects.get().note)

    def test_a_paid_checkout_matching_nothing_is_noted_for_staff(self):
        self.buy()
        self.event("checkout.session.completed", {**self.session(id="cs_someone_else"), "metadata": {}})
        self.assertIn("matched no payment", StripeEvent.objects.get().note)

    # -- crediting --------------------------------------------------------------------------------------------------

    def test_the_webhook_credits_a_paid_checkout_once(self):
        self.buy()
        event = {"type": "checkout.session.completed", "livemode": False, "data": {"object": self.session()}}
        self.assertEqual(self.webhook(event).status_code, 200)
        self.assertEqual(self.webhook(event).status_code, 200)  # Stripe retries: still credited once
        self.assertEqual(self.webhook({**event, "id": "evt_other"}).status_code, 200)  # even as another event
        self.assertEqual(services.balance_of(self.user), 100)
        self.assertEqual(Payment.objects.get().amount_paid, 500)

    def test_a_charge_for_less_than_the_pack_is_held_until_staff_release_it(self):
        self.buy()
        self.completed(amount_total=1)
        payment = Payment.objects.get()
        self.assertEqual((payment.status, services.balance_of(self.user)), (Payment.HELD, 0))
        self.assertIn("held", StripeEvent.objects.get().note)
        self.completed(amount_total=1)  # reported again: still held
        self.assertEqual(services.balance_of(self.user), 0)
        services.release_review(payment, "keeper")
        payment.refresh_from_db()
        self.assertEqual((payment.status, services.balance_of(self.user)), (Payment.PAID, 100))
        self.completed(amount_total=1)  # and a released payment stays released
        self.assertEqual(Payment.objects.get().status, Payment.PAID)

    def test_a_charge_in_another_currency_is_held(self):
        self.buy()
        self.completed(currency="usd")
        self.assertEqual((Payment.objects.get().status, services.balance_of(self.user)), (Payment.HELD, 0))

    def test_an_unpaid_or_expired_checkout_credits_nothing(self):
        self.buy()
        self.completed(payment_status="unpaid")
        self.event("checkout.session.expired", self.session(payment_status="unpaid"))
        self.assertEqual(services.balance_of(self.user), 0)
        self.assertEqual(Payment.objects.get().status, Payment.EXPIRED)

    def test_a_forged_webhook_is_refused(self):
        response = self.client.post(reverse("credits_stripe_webhook"), b"{}", content_type="application/json",
                                    HTTP_STRIPE_SIGNATURE="t=1,v1=forged")
        self.assertEqual(response.status_code, 400)

    def test_an_event_from_test_mode_does_nothing_with_live_keys(self):
        self.buy()
        with self.settings(GODLING_STRIPE_SECRET_KEY="sk_live_x"):
            self.assertContains(self.event("checkout.session.completed", self.session(), livemode=False),
                                "other mode")
        self.assertEqual(services.balance_of(self.user), 0)

    def test_the_return_page_asks_stripe_when_the_webhook_is_late(self):
        self.buy()
        found = SimpleNamespace(payment_status="paid", payment_intent="pi_1", amount_total=500, currency="eur")
        with mock.patch("stripe.checkout.Session.retrieve", return_value=found):
            page = self.client.get(reverse("credits_done") + "?session_id=cs_test_1")
        self.assertContains(page, "100 credits are in your purse")
        self.assertEqual(services.balance_of(self.user), 100)

    def test_the_return_page_holds_a_short_charge_too(self):
        self.buy()
        found = SimpleNamespace(payment_status="paid", payment_intent="pi_1", amount_total=100, currency="eur")
        with mock.patch("stripe.checkout.Session.retrieve", return_value=found):
            page = self.client.get(reverse("credits_done") + "?session_id=cs_test_1")
        self.assertContains(page, "We are checking this payment")
        self.assertEqual(services.balance_of(self.user), 0)

    # -- refunds ----------------------------------------------------------------------------------------------------

    def test_a_refund_takes_its_share_of_the_credits_back(self):
        payment = self.paid()
        self.assertEqual(payment.payment_intent, "pi_1")
        self.refund_to(100)  # a fifth of the €5.00
        self.assertEqual(services.balance_of(self.user), 80)
        self.refund_to(100)  # Stripe retries: taken once
        self.assertEqual(services.balance_of(self.user), 80)
        self.refund_to(500)  # the rest, later
        self.assertEqual(services.balance_of(self.user), 0)
        self.assertEqual(Payment.objects.get().status, Payment.REFUNDED)
        self.assertEqual(Entry.objects.filter(user=self.user, kind=Entry.CLAWBACK).count(), 2)

    def test_a_refund_that_fails_gives_its_credits_back(self):
        self.paid()
        self.refund_to(500, kind="refund.created")
        self.assertEqual(services.balance_of(self.user), 0)
        self.refund_to(0, kind="refund.failed")  # the bank sent it back: Stripe's charge shows nothing refunded
        self.assertEqual(services.balance_of(self.user), 100)
        self.assertEqual(Payment.objects.get().status, Payment.PAID)

    def test_an_older_refund_event_cannot_undo_a_newer_one(self):
        self.paid()
        self.refund_to(500)
        old = {**self.charge_now, "amount_refunded": 100}  # a copy from before the second refund, arriving late
        self.event("charge.refunded", old)
        self.assertEqual(services.balance_of(self.user), 0)  # Stripe's charge as it is now still says 500

    def test_spent_credits_are_owed_and_paid_from_what_comes_next(self):
        self.paid()
        services.spend(self.user, 70, "Meteor")
        self.refund_to(500)
        self.assertEqual(self.purse(), (0, 70))
        with self.assertRaises(services.NotEnough):
            services.spend(self.user, 4, "Stone")
        services.change(self.user, 100, Entry.GRANT, "a later pack")
        self.assertEqual(self.purse(), (30, 0))

    def test_a_refund_that_arrives_before_the_checkout_is_kept(self):
        """A full refund first, the checkout's own event after, and no spendable credits."""
        self.buy()
        with self.stripe_finds_the_session():
            self.assertEqual(self.refund_to(500).status_code, 200)
        self.assertEqual(services.balance_of(self.user), 0)
        self.completed()
        payment = Payment.objects.get()
        self.assertEqual((services.balance_of(self.user), payment.status, payment.granted), (0, Payment.REFUNDED, 0))

    def test_a_partly_refunded_checkout_reported_late_grants_the_rest(self):
        self.buy()
        with self.stripe_finds_the_session():
            self.refund_to(250)
        self.completed()
        self.assertEqual(services.balance_of(self.user), 50)

    def test_the_refunded_share_is_of_what_stripe_charged(self):
        """With tax on top (€6.00 charged for the €5.00 pack), refunding €3.00 is half the pack, not 60%."""
        self.buy()
        self.charge_now["amount"] = 600
        self.completed(amount_total=600)
        self.refund_to(300)
        self.assertEqual(services.balance_of(self.user), 50)

    def test_an_event_delivered_twice_is_applied_once(self):
        self.paid()
        services.spend(self.user, 30, "Meteor")
        self.refund_to(100, event_id="evt_refund")
        self.refund_to(100, event_id="evt_refund")
        self.assertEqual(services.balance_of(self.user), 50)
        self.assertEqual(Entry.objects.filter(user=self.user, kind=Entry.CLAWBACK).count(), 1)

    def test_stripe_out_of_reach_asks_for_the_event_again(self):
        """Stripe cannot be asked: the webhook says 503 so Stripe sends the event again, and applies nothing."""
        self.paid()
        with mock.patch("stripe.Charge.retrieve", side_effect=stripe.APIConnectionError("no route")):
            self.assertEqual(self.refund_to(500, event_id="evt_retry").status_code, 503)
        self.assertEqual(services.balance_of(self.user), 100)
        self.assertFalse(StripeEvent.objects.filter(event_id="evt_retry").exists())
        self.assertEqual(self.refund_to(500, event_id="evt_retry").status_code, 200)
        self.assertEqual(services.balance_of(self.user), 0)

    def test_a_payment_whose_intent_was_not_kept_is_found_through_stripe(self):
        self.buy()
        services.credit_payment("cs_test_1")  # as the return page did before payment intents were kept
        with self.stripe_finds_the_session() as lookup:
            self.refund_to(500)
        self.assertEqual(lookup.call_args.kwargs["payment_intent"], "pi_1")
        self.assertEqual(services.balance_of(self.user), 0)
        self.assertEqual(Payment.objects.get().payment_intent, "pi_1")

    def test_a_lookup_that_fails_asks_for_the_event_again(self):
        self.buy()
        services.credit_payment("cs_test_1")  # its intent not kept: the refund needs Stripe to find it
        with mock.patch("stripe.checkout.Session.list", side_effect=stripe.APIConnectionError("no route")):
            self.assertEqual(self.refund_to(500).status_code, 503)
        self.assertEqual(services.balance_of(self.user), 100)

    def test_an_event_about_someone_elses_payment_is_acknowledged(self):
        with mock.patch("stripe.checkout.Session.list", return_value=SimpleNamespace(data=[])):
            self.assertEqual(self.refund_to(500).status_code, 200)

    # -- disputes ---------------------------------------------------------------------------------------------------

    def test_a_dispute_holds_the_credits_until_the_bank_decides(self):
        self.paid()
        self.dispute("needs_response", kind="charge.dispute.created")
        self.assertEqual(services.balance_of(self.user), 0)
        self.assertEqual(Payment.objects.get().status, Payment.DISPUTED)
        self.dispute("won", kind="charge.dispute.closed")
        self.assertEqual(services.balance_of(self.user), 100)
        self.assertEqual(Payment.objects.get().status, Payment.PAID)
        self.dispute("needs_response", kind="charge.dispute.created", dispute_id="dp_2")  # another dispute, later
        self.dispute("lost", kind="charge.dispute.closed", dispute_id="dp_2")
        self.assertEqual(services.balance_of(self.user), 0)

    def test_a_repeated_or_late_dispute_event_never_reopens_a_decided_dispute(self):
        """Stripe may send an event again, or out of order (100 → 0 → 100 → 0 before)."""
        self.paid()
        self.dispute("needs_response", kind="charge.dispute.created", event_id="evt_dp_created")
        self.dispute("won", kind="charge.dispute.closed")
        self.dispute("needs_response", kind="charge.dispute.created", event_id="evt_dp_created", old=True)
        self.dispute("under_review", kind="charge.dispute.updated", old=True)  # an older copy, arriving late
        self.assertEqual(services.balance_of(self.user), 100)
        self.assertEqual(Payment.objects.get().status, Payment.PAID)

    def test_a_close_that_arrives_before_its_dispute_holds(self):
        self.paid()
        self.dispute("won", kind="charge.dispute.closed")
        self.dispute("needs_response", kind="charge.dispute.created", old=True)
        self.assertEqual(services.balance_of(self.user), 100)

    def test_a_lost_dispute_over_part_of_the_payment_takes_that_part(self):
        self.paid()
        self.dispute("needs_response", kind="charge.dispute.created", amount=200)
        self.assertEqual(services.balance_of(self.user), 0)  # held whole while the bank decides
        self.dispute("lost", kind="charge.dispute.closed", amount=200)
        self.assertEqual(services.balance_of(self.user), 60)  # €2.00 of €5.00 went back: 40 credits

    def test_a_lost_dispute_of_unknown_amount_takes_the_whole_pack(self):
        self.paid()
        self.dispute("lost", kind="charge.dispute.closed", amount=0)
        self.assertEqual(services.balance_of(self.user), 0)

    def test_a_refund_during_a_dispute_is_not_given_back_when_the_dispute_is_won(self):
        self.paid()
        self.dispute("needs_response", kind="charge.dispute.created")
        self.refund_to(100)  # a fifth refunded meanwhile
        self.dispute("won", kind="charge.dispute.closed")
        self.assertEqual(services.balance_of(self.user), 80)

    # -- failures ---------------------------------------------------------------------------------------------------

    def test_a_failure_while_applying_is_not_taken_for_a_repeat(self):
        """Only the event's own record counts as 'seen': another failure is a 500, and Stripe sends it again."""
        self.paid()
        strict = Client(raise_request_exception=False)
        with mock.patch("stripe.Webhook.construct_event",
                        return_value={"id": "evt_boom", "type": "charge.refunded", "livemode": False,
                                      "data": {"object": dict(self.charge_now, amount_refunded=500)}}), \
                mock.patch("apps.credits.services.refunded", side_effect=IntegrityError("something else")):
            response = strict.post(reverse("credits_stripe_webhook"), b"{}", content_type="application/json",
                                   HTTP_STRIPE_SIGNATURE="t=1,v1=x")
        self.assertEqual(response.status_code, 500)
        self.assertFalse(StripeEvent.objects.filter(event_id="evt_boom").exists())
        self.assertEqual(services.balance_of(self.user), 100)

    def test_packs_come_from_the_admin(self):
        CreditPack.objects.filter(key="handful").update(active=False)
        page = self.client.get(reverse("credits"))
        self.assertNotContains(page, "A handful")
        self.assertContains(page, "A chest")

    def test_the_purse_page_says_what_is_owed(self):
        self.paid()
        services.spend(self.user, 70, "Meteor")
        self.refund_to(500)
        self.assertContains(self.client.get(reverse("credits")), "You owe 70 credits")


WEBHOOK_SECRET = "whsec_test_signed"


@override_settings(GODLING_STRIPE_SECRET_KEY="", GODLING_STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET)
class SignedWebhookTests(TestCase):
    """Real signed bodies through stripe-python's own construct_event, nothing mocked: the shapes the views read are
    the shapes the installed library hands them (the other tests mock it with plain dicts)."""

    def post(self, event, signed_at=None):
        body = json.dumps(event)
        at = int(signed_at or time.time())
        signature = hmac.new(WEBHOOK_SECRET.encode(), f"{at}.{body}".encode(), hashlib.sha256).hexdigest()
        return self.client.post(reverse("credits_stripe_webhook"), body, content_type="application/json",
                                HTTP_STRIPE_SIGNATURE=f"t={at},v1={signature}")

    def test_a_signed_checkout_event_credits_the_pack(self):
        user = make_user()
        payment = Payment.objects.create(user=user, pack="handful", credits=100, amount_cents=500, currency="eur",
                                         session="cs_signed_1")
        event = {"id": "evt_signed_1", "object": "event", "type": "checkout.session.completed", "livemode": False,
                 "data": {"object": {"id": "cs_signed_1", "object": "checkout.session", "payment_status": "paid",
                                     "payment_intent": "pi_signed", "amount_total": 500, "currency": "eur",
                                     "metadata": {"payment": str(payment.pk), "user": str(user.pk)}}}}
        self.assertEqual(self.post(event).status_code, 200)
        self.assertEqual(services.balance_of(user), 100)
        self.assertEqual(self.post(event).content, b"seen")
        self.assertEqual(services.balance_of(user), 100)

    def test_a_signed_refund_event_takes_back_its_share(self):
        user = make_user()
        Payment.objects.create(user=user, pack="handful", credits=100, amount_cents=500, currency="eur",
                               session="cs_signed_2", payment_intent="pi_signed_2")
        services.credit_payment("cs_signed_2", "pi_signed_2", 500, "eur")
        event = {"id": "evt_signed_2", "object": "event", "type": "charge.refunded", "livemode": False,
                 "data": {"object": {"id": "ch_signed", "object": "charge", "payment_intent": "pi_signed_2",
                                     "amount": 500, "amount_refunded": 250}}}
        self.assertEqual(self.post(event).status_code, 200)
        self.assertEqual(services.balance_of(user), 50)

    def test_an_old_signature_is_refused(self):
        """A captured event replayed after Stripe's five-minute tolerance."""
        event = {"id": "evt_old", "object": "event", "type": "checkout.session.completed", "livemode": False,
                 "data": {"object": {"id": "cs_x", "object": "checkout.session"}}}
        self.assertEqual(self.post(event, signed_at=time.time() - 600).status_code, 400)


class MigrationTests(TransactionTestCase):
    """A site with payments from before ADR-014 migrates without crediting anything twice."""

    def test_paid_packs_from_before_count_as_granted(self):
        before = [("credits", "0005_alter_entry_kind"), ("users", "0003_viewer_pace")]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        user = old.get_model("users", "User").objects.create(username="old", email="Old.Timer+tv@gmail.com",
                                                              password="x")
        old.get_model("credits", "Payment").objects.create(user=user, pack="handful", credits=100, amount_cents=500,
                                                           currency="eur", session="cs_old", status="paid")
        old.get_model("credits", "Entry").objects.create(user=user, amount=20, kind="welcome", ref="email confirmed",
                                                         balance_after=20)
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        payment = Payment.objects.get(session="cs_old")
        self.assertEqual(payment.granted, 100)
        self.assertEqual(User.objects.get(pk=user.pk).email_key, "oldtimer@gmail.com")
        self.assertTrue(Welcome.objects.filter(email_key="oldtimer@gmail.com", user_id=user.pk).exists())
        self.assertFalse(services.credit_payment("cs_old", "pi_old", 500, "eur"))  # reported again: nothing moves
        self.assertFalse(Entry.objects.filter(user_id=user.pk, kind=Entry.PURCHASE).exists())


class StripeErrorTests(TestCase):
    def test_stripe_errors_are_importable_where_the_views_expect_them(self):
        self.assertTrue(issubclass(stripe.SignatureVerificationError, Exception))
        self.assertTrue(issubclass(stripe.StripeError, Exception))
        self.assertTrue(issubclass(stripe.APIConnectionError, stripe.StripeError))


class LivePaymentsWaitForAReviewTests(SimpleTestCase):
    """The money gate (godling_web/settings.py, ADR-017): live Stripe keys stop the site from starting until an outside
    security review is named. Run as the site starts: `manage.py check` in a fresh process."""

    def check(self, **env):
        clean = {k: v for k, v in os.environ.items() if not k.startswith(("GODLING_STRIPE", "GODLING_SECURITY"))}
        return subprocess.run([sys.executable, "manage.py", "check"], cwd=settings.BASE_DIR, capture_output=True,
                              text=True, timeout=120, env={**clean, "GODLING_SECRET_KEY": "check", "GODLING_DEBUG": "0", **env})

    def test_live_keys_wait_for_a_review(self):
        refused = self.check(GODLING_STRIPE_SECRET_KEY="sk_live_51abc")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("outside security review", refused.stderr)
        reviewed = self.check(GODLING_STRIPE_SECRET_KEY="sk_live_51abc",
                              GODLING_SECURITY_REVIEW="Example Security, 2026-12-01, report in the shared drive")
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)

    def test_test_keys_and_none_need_no_review(self):
        self.assertEqual(self.check(GODLING_STRIPE_SECRET_KEY="sk_test_51abc").returncode, 0)
        self.assertEqual(self.check().returncode, 0)
