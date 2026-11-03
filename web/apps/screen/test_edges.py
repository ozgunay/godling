"""The site's rarer paths since ADR-014: the shared news while another request fetches it, a settled power settled
again, held payments in the admin, Stripe telling one event twice at once, and the records' words."""
import time
from unittest import mock

import stripe
from django.core.cache import cache
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.credits import services as credits
from apps.credits import views as credit_views
from apps.credits.models import Payment, PowerCall, StripeEvent, Welcome
from apps.notes.tests import code_entered, two_factor
from apps.screen import island, tasks
from apps.users.models import User
from apps.users.validators import canonical_email


def make_user(name="tomv", **fields):
    return User.objects.create_user(username=name, email=f"{name}@example.org", password="an-island-test-pass-4127",
                                    **fields)


class SharedNewsTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_while_another_request_fetches_the_last_copy_is_shown(self):
        cache.set(island.STATUS_KEY, {"at": time.time() - 5, "status": {"world": True, "old": 1}})
        cache.add(island.STATUS_LOCK, 1)  # another request is fetching
        build = mock.Mock()
        self.assertEqual(island.shared(build), {"world": True, "old": 1})
        build.assert_not_called()

    def test_a_cold_start_that_never_gets_its_copy_shows_no_island(self):
        cache.add(island.STATUS_LOCK, 1)
        with mock.patch.object(island, "COLD_WAIT", 0.2):
            self.assertEqual(island.shared(mock.Mock()), {"world": False})

    def test_a_count_that_expired_between_two_calls_starts_again(self):
        fake = mock.Mock()
        fake.incr.side_effect = ValueError("gone")
        with mock.patch.object(island, "cache", fake):
            self.assertEqual(island._count("watch:1:count"), 1)
        fake.set.assert_called_once_with("watch:1:count", 1, island.WINDOW * 3)


class PowerEdgeTests(TestCase):
    def test_a_call_settled_meanwhile_is_left_as_it_is(self):
        call = PowerCall.objects.create(user=make_user(), power="Stone", price=4, ok=True, status=PowerCall.DONE)
        settled = tasks.settle(call.pk, {"ok": False}, PowerCall.QUEUED, PowerCall.EXPIRED)
        self.assertEqual((settled.status, settled.ok, settled.refunded), (PowerCall.DONE, True, False))

    def test_signed_out_viewers_cannot_ask_after_a_power(self):
        call = PowerCall.objects.create(user=make_user(), power="Stone", price=4, status=PowerCall.QUEUED)
        self.assertEqual(self.client.get(f"/api/power/{call.pk}").status_code, 401)


class PaymentAdminTests(TestCase):
    def setUp(self):
        staff = two_factor(make_user("keeper", is_staff=True, is_superuser=True))
        self.client.force_login(staff)
        code_entered(self.client)
        self.viewer = make_user()
        self.held = Payment.objects.create(user=self.viewer, pack="handful", credits=100, amount_cents=500,
                                           currency="eur", session="cs_held", amount_paid=400, amount_refunded=100,
                                           paid_at=timezone.now(), status=Payment.HELD, review="charged 4.00 of 5.00")
        self.open = Payment.objects.create(user=self.viewer, pack="handful", credits=100, amount_cents=500,
                                           currency="eur", session="cs_open")

    def test_the_list_shows_what_stripe_charged_and_refunded(self):
        page = self.client.get("/admin/credits/payment/")
        self.assertContains(page, "4.00")  # charged
        self.assertContains(page, "1.00")  # refunded
        page = self.client.get(f"/admin/credits/payment/{self.open.pk}/change/")
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'name="credits"')  # every field is Stripe's fact: nothing to type over

    def test_held_payments_are_released_and_open_ones_left_alone(self):
        page = self.client.post("/admin/credits/payment/", {"action": "release",
                                                             "_selected_action": [self.held.pk, self.open.pk]},
                                follow=True)
        self.assertContains(page, "1 held payment(s) released.")
        self.held.refresh_from_db()
        self.assertEqual((self.held.status, self.held.review), (Payment.PAID, ""))
        self.assertEqual(credits.balance_of(self.viewer), 75)  # its credits, less the refunded quarter
        self.assertEqual(credits.release_review(self.held, "keeper"), 0)  # released already: nothing more


class StripeEdgeTests(TestCase):
    def setUp(self):
        self.payment = Payment.objects.create(user=make_user(), pack="handful", credits=100, amount_cents=500,
                                              currency="eur", session="cs_1", payment_intent="pi_1",
                                              amount_paid=500, paid_at=timezone.now(), status=Payment.PAID,
                                              dispute_id="dp_1", dispute_status="won")

    def test_a_decided_dispute_stays_decided(self):
        self.assertEqual(credits.dispute_changed(self.payment, "dp_1", "needs_response"), 0)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.dispute_status, "won")

    def test_an_unpaid_close_of_a_paid_checkout_changes_nothing(self):
        self.assertFalse(credits.checkout_expired("cs_1"))
        self.assertFalse(credits.checkout_expired("cs_nobody"))

    @override_settings(GODLING_STRIPE_SECRET_KEY="")
    def test_without_a_key_events_are_taken_as_they_come(self):
        dispute = {"object": "dispute", "id": "dp_2", "payment_intent": "pi_1", "status": "needs_response"}
        self.assertIs(credit_views.as_it_is_now("charge.dispute.created", dispute), dispute)
        self.assertIsNone(credit_views.payment_for(""))

    @override_settings(GODLING_STRIPE_SECRET_KEY="", GODLING_STRIPE_WEBHOOK_SECRET="whsec_x")
    def test_one_event_delivered_twice_at_once_is_applied_once(self):
        """Both deliveries pass the first look; the second finds the first's record when it tries to keep its own."""
        event = {"id": "evt_twice", "type": "checkout.session.expired", "data": {"object": {"id": "cs_1"}}}
        with mock.patch("stripe.Webhook.construct_event", return_value=stripe.Event.construct_from(event, "k")), \
                mock.patch.object(StripeEvent.objects, "filter") as kept, \
                mock.patch.object(StripeEvent.objects, "create", side_effect=IntegrityError("unique")):
            kept.return_value.exists.side_effect = [False, True]
            response = self.client.post(reverse("credits_stripe_webhook"), b"{}", content_type="application/json",
                                        HTTP_STRIPE_SIGNATURE="t=1,v1=x")
        self.assertEqual(response.content, b"seen")


class RecordTests(TestCase):
    def test_how_records_read(self):
        user = make_user()
        self.assertEqual(str(Welcome.objects.create(email_key="tomv@example.org", user=user)),
                         "tomv@example.org (first: tomv)")
        call = PowerCall.objects.create(user=user, power="Stone", price=4, status=PowerCall.QUEUED)
        self.assertEqual(str(call), "tomv Stone (on its way)")
        self.assertEqual(str(StripeEvent.objects.create(event_id="evt_1", kind="charge.refunded")),
                         "charge.refunded evt_1")

    def test_an_address_without_an_at_is_its_own_key(self):
        self.assertEqual(canonical_email(" Not-An-Address "), "not-an-address")
