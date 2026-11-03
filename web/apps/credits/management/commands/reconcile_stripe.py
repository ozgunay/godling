"""After the database is restored from a backup (ADR-018): what Stripe did since the snapshot, brought back in.

The webhook's events from after the snapshot were answered at the time, so Stripe will not send them again, and the
restored database has none of what they did: packs paid for, refunds, disputes. This reads them from Stripe and applies
them as the webhook would (apps.credits.services: each once, and only the difference it makes, so running it again
changes nothing). A checkout whose payment was lost with the restore gets its payment back from the session's
metadata, which views.buy fills with the payment, the viewer, the pack and its credits.

    python manage.py reconcile_stripe --since 2026-11-03T14:00:00Z

`--since` is the snapshot's time, as `backup restore db` says it. Stripe is asked from an hour before it, for a
checkout opened before the snapshot and paid after it.
"""
import datetime as dt

import stripe
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from apps.credits import services
from apps.credits.models import Payment
from apps.credits.views import AskAgain, payment_for
from apps.users.models import User


def _all(listing):
    """Every item of a Stripe list, page after page."""
    return listing.auto_paging_iter() if hasattr(listing, "auto_paging_iter") else listing.data


class Command(BaseCommand):
    help = "Applies what Stripe did since a time (a restored backup's): payments, refunds and disputes."

    def add_arguments(self, parser):
        parser.add_argument("--since", required=True, help="the snapshot's time, in UTC (2026-11-03T14:00:00Z)")

    def handle(self, *args, since, **options):
        key = settings.GODLING_STRIPE_SECRET_KEY
        if not key:
            raise CommandError("GODLING_STRIPE_SECRET_KEY is not set: there is no Stripe to ask")
        start = parse_datetime(since.replace("Z", "+00:00"))
        if start is None:
            raise CommandError(f"--since {since!r} is not a time (2026-11-03T14:00:00Z)")
        if start.tzinfo is None:
            start = start.replace(tzinfo=dt.timezone.utc)
        after = {"gte": int(start.timestamp()) - 3600}
        try:
            found, credited = self.checkouts(key, after)
            refunds, disputes = self.refunds_and_disputes(key, after)
        except (stripe.StripeError, AskAgain) as err:
            raise CommandError(f"Stripe could not be asked ({err}); run it again: it changes nothing twice") from err
        self.stdout.write(f"Since {start:%Y-%m-%d %H:%M} UTC: {found} lost payment(s) found again, {credited} credited, "
                          f"{refunds} refund(s) and {disputes} dispute(s) applied.")

    def checkouts(self, key, after):
        found = credited = 0
        for session in _all(stripe.checkout.Session.list(created=after, limit=100, api_key=key)):
            meta = session.get("metadata") or {}
            if not meta.get("payment"):
                continue  # not one of ours (views.buy marks each)
            if not Payment.objects.filter(session=session["id"]).exists():
                user = User.objects.filter(pk=meta.get("user")).first()
                if user is None:
                    self.stderr.write(f"Checkout {session['id']}: its viewer {meta.get('user')!r} is not here")
                    continue
                amount = session.get("amount_total") or 0
                Payment.objects.create(user=user, pack=str(meta.get("pack") or "")[:40],
                                       credits=int(meta.get("credits") or 0), amount_cents=amount,
                                       currency=session.get("currency") or settings.GODLING_CURRENCY,
                                       session=session["id"])
                found += 1
            if session.get("payment_status") == "paid":
                if services.credit_payment(session["id"], session.get("payment_intent") or "",
                                           session.get("amount_total"), session.get("currency") or ""):
                    credited += 1
            elif session.get("status") == "expired":
                services.checkout_expired(session["id"])
        return found, credited

    def refunds_and_disputes(self, key, after):
        refunds = disputes = 0
        for refund in _all(stripe.Refund.list(created=after, limit=100, api_key=key)):
            payment = payment_for(refund.get("payment_intent"))
            if payment is not None and refund.get("charge"):
                charge = stripe.Charge.retrieve(str(refund["charge"]), api_key=key)  # the charge as it is now
                services.refunded(payment, charge.get("amount_refunded"), charge.get("amount"))
                refunds += 1
        seen = set()
        for dispute in _all(stripe.Dispute.list(created=after, limit=100, api_key=key)):
            payment = payment_for(dispute.get("payment_intent"))
            if payment is not None:
                services.dispute_changed(payment, dispute["id"], dispute.get("status"), dispute.get("amount"))
                seen.add(dispute["id"])
                disputes += 1
        # Disputes opened before the snapshot may have been decided since.
        for payment in Payment.objects.filter(dispute_status__in=services.DISPUTE_OPEN).exclude(dispute_id__in=seen):
            if payment.dispute_id:
                dispute = stripe.Dispute.retrieve(payment.dispute_id, api_key=key)
                services.dispute_changed(payment, dispute["id"], dispute.get("status"), dispute.get("amount"))
                disputes += 1
        return refunds, disputes
