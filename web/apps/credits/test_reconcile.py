"""reconcile_stripe: after the database is restored from a backup (ADR-018), what Stripe did since the snapshot comes
back in: a pack paid for whose payment the restore lost, a refund, a dispute decided. Stripe is mocked as it lists
them; running it again changes nothing."""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.credits import services
from apps.credits.models import Payment
from apps.credits.tests import make_user


class Listing:
    def __init__(self, items):
        self.items = items

    def auto_paging_iter(self):
        return iter(self.items)


@override_settings(GODLING_STRIPE_SECRET_KEY="sk_test_x")
class ReconcileTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.sessions, self.refunds, self.disputes = [], [], []
        self.charge = {"id": "ch_1", "payment_intent": "pi_1", "amount": 500, "amount_refunded": 0}
        for target, answer in (("stripe.checkout.Session.list", lambda **kw: Listing(self.sessions)),
                               ("stripe.Refund.list", lambda **kw: Listing(self.refunds)),
                               ("stripe.Dispute.list", lambda **kw: Listing(self.disputes)),
                               ("stripe.Charge.retrieve", lambda charge_id, **kw: dict(self.charge))):
            patcher = mock.patch(target, side_effect=answer)
            patcher.start()
            self.addCleanup(patcher.stop)

    def reconcile(self):
        out = StringIO()
        call_command("reconcile_stripe", "--since", "2026-11-03T14:00:00Z", stdout=out)
        return out.getvalue()

    def paid_checkout(self):
        """Paid at 14:40, after the 14:00 snapshot: the restored database has no payment for it."""
        self.sessions.append({"id": "cs_lost", "payment_status": "paid", "status": "complete", "payment_intent": "pi_1",
                              "amount_total": 500, "currency": "eur",
                              "metadata": {"payment": "41", "user": str(self.user.pk), "pack": "handful",
                                           "credits": "100"}})

    def test_a_pack_paid_after_the_snapshot_is_found_again_and_credited_once(self):
        self.paid_checkout()
        self.assertIn("1 lost payment(s) found again, 1 credited", self.reconcile())
        payment = Payment.objects.get(session="cs_lost")
        self.assertEqual((payment.user, payment.pack, payment.credits, payment.status), (self.user, "handful", 100,
                                                                                         Payment.PAID))
        self.assertEqual(services.balance_of(self.user), 100)
        self.assertIn("0 lost payment(s) found again, 0 credited", self.reconcile())  # again: nothing moves
        self.assertEqual(services.balance_of(self.user), 100)

    def test_a_refund_after_the_snapshot_takes_its_share_back(self):
        self.paid_checkout()
        self.reconcile()
        self.charge["amount_refunded"] = 250
        self.refunds.append({"id": "re_1", "charge": "ch_1", "payment_intent": "pi_1"})
        self.assertIn("1 refund(s)", self.reconcile())
        self.assertEqual(services.balance_of(self.user), 50)

    def test_other_checkouts_and_unknown_viewers_are_left(self):
        self.sessions.append({"id": "cs_other", "payment_status": "paid", "metadata": {}})  # not one of ours
        self.sessions.append({"id": "cs_gone", "payment_status": "paid", "amount_total": 500,
                              "metadata": {"payment": "7", "user": "999", "credits": "100"}})
        err = StringIO()
        call_command("reconcile_stripe", "--since", "2026-11-03T14:00:00", stdout=StringIO(), stderr=err)
        self.assertFalse(Payment.objects.exists())
        self.assertIn("its viewer '999' is not here", err.getvalue())

    @override_settings(GODLING_STRIPE_SECRET_KEY="")
    def test_without_a_stripe_key_it_says_so(self):
        with self.assertRaisesMessage(CommandError, "GODLING_STRIPE_SECRET_KEY is not set"):
            self.reconcile()
