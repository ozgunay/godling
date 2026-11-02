"""Buying credits with Stripe Checkout (the user's choice of provider).

Stripe's hosted checkout takes the payment; its webhook (or, if that is late, the return page asking Stripe) marks the
payment paid, and services.credit_payment credits the pack once. Without Stripe keys, in development only, a test
checkout stands in so the whole flow can be tried locally; it is never there in production.
"""
import logging
import uuid

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.credits import services
from apps.credits.models import CreditPack, Entry, Payment, Purse, StripeEvent

log = logging.getLogger("godling.credits")
CHECKOUT_PAID = ("checkout.session.completed", "checkout.session.async_payment_succeeded")
CHECKOUT_UNPAID = ("checkout.session.expired", "checkout.session.async_payment_failed")
# A charge's refunds changed: the charge itself, or one of its refunds (a refund made, failed or cancelled).
REFUND_EVENTS = ("charge.refunded", "charge.refund.updated", "refund.created", "refund.updated", "refund.failed")


def money(cents):
    symbol = {"eur": "€", "usd": "$", "gbp": "£"}.get(settings.GODLING_CURRENCY, "")
    return f"{symbol}{cents / 100:.2f}" if symbol else f"{cents / 100:.2f} {settings.GODLING_CURRENCY.upper()}"


def checkout_mode():
    if settings.GODLING_STRIPE_SECRET_KEY:
        return "stripe"
    return "test" if settings.DEBUG else ""


def live_key():
    """Whether the Stripe key is a live one (sk_live_…, or a restricted rk_live_…)."""
    return settings.GODLING_STRIPE_SECRET_KEY.startswith(("sk_live_", "rk_live_"))


@login_required
def credits_page(request):
    packs = [{"pack": p, "price": money(p.price_cents)} for p in CreditPack.objects.filter(active=True)]
    purse = Purse.objects.filter(user=request.user).first()
    return render(request, "credits/credits.html", {
        "balance": purse.balance if purse else 0, "owed": purse.owed if purse else 0, "packs": packs,
        "mode": checkout_mode(), "entries": Entry.objects.filter(user=request.user)[:12]})


@login_required
@require_POST
def buy(request, key):
    """The payment is made first and Stripe's session second, carrying the payment's id in its metadata: a paid
    checkout then always has its payment, even if the server stopped between the two (credit_payment finds it)."""
    pack = get_object_or_404(CreditPack, key=key, active=True)
    mode = checkout_mode()
    if mode not in ("stripe", "test"):
        messages.error(request, "Buying credits is not set up yet.")
        return redirect("credits")
    common = {"user": request.user, "pack": pack.key, "credits": pack.credits, "amount_cents": pack.price_cents,
              "currency": settings.GODLING_CURRENCY}
    if mode == "test":
        payment = Payment.objects.create(session=f"test_{uuid.uuid4().hex}", **common)
        return redirect("credits_test_checkout", session=payment.session)
    payment = Payment.objects.create(session=f"{Payment.PENDING}{uuid.uuid4().hex}", **common)
    ours = {"payment": str(payment.pk), "user": str(request.user.pk), "pack": pack.key, "credits": str(pack.credits)}
    done = request.build_absolute_uri(reverse("credits_done")) + "?session_id={CHECKOUT_SESSION_ID}"
    try:
        session = stripe.checkout.Session.create(
            api_key=settings.GODLING_STRIPE_SECRET_KEY, idempotency_key=f"godling-payment-{payment.pk}",
            mode="payment",
            line_items=[{"quantity": 1, "price_data": {
                "currency": settings.GODLING_CURRENCY, "unit_amount": pack.price_cents,
                "product_data": {"name": f"{pack.credits} credits for Godling ({pack.name})"}}}],
            success_url=done, cancel_url=request.build_absolute_uri(reverse("credits")),
            client_reference_id=str(payment.pk), customer_email=request.user.email, metadata=ours,
            payment_intent_data={"metadata": ours})  # so the charge in Stripe's dashboard says whose it is
    except stripe.StripeError as err:
        # Kept, closed: had Stripe made the session after all, its webhook still finds this payment by its id.
        Payment.objects.filter(pk=payment.pk).update(status=Payment.EXPIRED)
        log.warning("Checkout for payment %s not opened: %s", payment.pk, err)
        messages.error(request, "Stripe did not answer; nothing was charged. Please try again in a moment.")
        return redirect("credits")
    Payment.objects.filter(pk=payment.pk).update(session=session.id)
    return redirect(session.url, permanent=False)


@login_required
def test_checkout(request, session):
    """Development only: a stand-in for Stripe's checkout page. No money moves."""
    if checkout_mode() != "test":
        raise Http404
    payment = get_object_or_404(Payment, session=session, user=request.user)
    if request.method == "POST":
        services.credit_payment(payment.session)
        return redirect(f"{reverse('credits_done')}?session_id={payment.session}")
    return render(request, "credits/test_checkout.html", {"payment": payment, "price": money(payment.amount_cents)})


@login_required
def done(request):
    """Back from the checkout. If Stripe's webhook has not credited the pack yet, ask Stripe once."""
    session = request.GET.get("session_id", "")
    payment = Payment.objects.filter(session=session, user=request.user).first()
    if payment and payment.paid_at is None and checkout_mode() == "stripe":
        try:
            found = stripe.checkout.Session.retrieve(session, api_key=settings.GODLING_STRIPE_SECRET_KEY)
            if found.payment_status == "paid":
                services.credit_payment(session, getattr(found, "payment_intent", None) or "",
                                        getattr(found, "amount_total", None), getattr(found, "currency", "") or "")
        except stripe.StripeError:
            pass  # the webhook will still come
        payment.refresh_from_db()
    purse = Purse.objects.filter(user=request.user).first()
    return render(request, "credits/done.html", {"payment": payment, "balance": purse.balance if purse else 0,
                                                 "owed": purse.owed if purse else 0})


class AskAgain(Exception):
    """Stripe could not be asked just now: the webhook answers 503, and Stripe delivers the event again later."""


def payment_for(payment_intent):
    """The pack bought with this Stripe PaymentIntent, or None if it is not one of ours. A payment whose intent is not
    kept yet (a refund that arrives before the checkout's own event, or an older payment) is found through Stripe:
    the checkout session that made it. Raises AskAgain when Stripe cannot be reached."""
    if not payment_intent:
        return None
    payment = Payment.objects.filter(payment_intent=payment_intent).first()
    if payment is None and settings.GODLING_STRIPE_SECRET_KEY:
        try:
            sessions = stripe.checkout.Session.list(payment_intent=payment_intent, limit=1,
                                                    api_key=settings.GODLING_STRIPE_SECRET_KEY)
        except stripe.StripeError as err:
            raise AskAgain(str(err)) from err
        for found in sessions.data:
            payment = Payment.objects.filter(session=found.id).first()
            if payment:  # kept only where none is yet: a payment's own intent is never overwritten
                Payment.objects.filter(pk=payment.pk, payment_intent="").update(payment_intent=payment_intent)
    return payment


def as_it_is_now(kind, thing):
    """The charge or dispute an event is about, as Stripe has it now (docs.stripe.com/webhooks#event-ordering: fetch
    the object rather than trust an event's copy, which may be older than one already applied). Without a secret key
    (development), the event's own copy. Raises AskAgain when Stripe cannot be reached."""
    key = settings.GODLING_STRIPE_SECRET_KEY
    try:
        if kind in REFUND_EVENTS:
            charge_id = thing.get("id") if thing.get("object") == "charge" else thing.get("charge")
            if key and charge_id:
                return stripe.Charge.retrieve(str(charge_id), api_key=key)
            return thing if thing.get("object") == "charge" else None
        if key and thing.get("id"):
            return stripe.Dispute.retrieve(str(thing["id"]), api_key=key)
        return thing
    except stripe.StripeError as err:
        raise AskAgain(str(err)) from err


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Stripe tells the site a checkout finished, or that a payment was refunded or disputed. Signed with
    GODLING_STRIPE_WEBHOOK_SECRET; anything else is refused, and so is a signature over five minutes old.

    Each event is applied once (StripeEvent), in one transaction with its record, so an event that fails is not marked
    seen and Stripe's retry applies it. Refunds and disputes are read from Stripe as they are now, and what they say
    is kept on the payment; services.reconcile moves only the difference it makes, so events may come in any order. A
    refund takes back its share of the pack's credits, and a failed one gives it back; a dispute holds back all of
    them until the bank decides, and a won dispute gives them back. Credits already spent are owed, and paid from
    what comes in next (services.take_back). Events from the other mode (test events with live keys) are ignored."""
    if not settings.GODLING_STRIPE_WEBHOOK_SECRET:
        return HttpResponseBadRequest("not set up")
    try:
        event = stripe.Webhook.construct_event(request.body, request.headers.get("Stripe-Signature", ""),
                                               settings.GODLING_STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponseBadRequest("bad signature")
    event_id, kind, thing = event.get("id") or "", event["type"], event["data"]["object"]
    if settings.GODLING_STRIPE_SECRET_KEY and bool(event.get("livemode")) != live_key():
        log.warning("Stripe event %s (%s) is from the other mode than the key: ignored", event_id, kind)
        return HttpResponse("other mode")
    if event_id and StripeEvent.objects.filter(event_id=event_id).exists():
        return HttpResponse("seen")
    payment = now = None
    if kind in REFUND_EVENTS or kind.startswith("charge.dispute."):
        try:
            now = as_it_is_now(kind, thing)
            payment = payment_for(now.get("payment_intent")) if now is not None else None
        except AskAgain:
            return HttpResponse("Stripe could not be reached; send it again", status=503)
        if payment is None:
            return HttpResponse("not ours")
    try:
        with transaction.atomic():
            record = StripeEvent.objects.create(event_id=event_id, kind=kind[:80]) if event_id else None
            note = apply_event(kind, thing, payment, now)
            if record is not None and note:
                StripeEvent.objects.filter(pk=record.pk).update(note=note[:200])
    except IntegrityError:
        if event_id and StripeEvent.objects.filter(event_id=event_id).exists():
            return HttpResponse("seen")  # the same event, delivered twice at once: the other delivery applied it
        raise  # anything else is a real failure: 500, nothing kept, and Stripe sends the event again
    return HttpResponse("ok")


def apply_event(kind, thing, payment, now):
    """Apply one event; returns a note for staff when something is wrong (StripeEvent.note), else ''."""
    if kind in CHECKOUT_PAID or kind in CHECKOUT_UNPAID:
        # Only the metadata's payment id finds a payment besides the session id (views.buy): sessions made before
        # it carried the user's id as client_reference_id, which is not a payment's.
        meta = thing.get("metadata") or {}
        ref, user = meta.get("payment") or "", meta.get("user") or ""
        if kind in CHECKOUT_UNPAID:
            services.checkout_expired(thing["id"], ref, user)
        elif thing.get("payment_status") == "paid":
            services.credit_payment(thing["id"], thing.get("payment_intent") or "", thing.get("amount_total"),
                                    thing.get("currency") or "", ref, user)
            payment = Payment.objects.filter(session=thing["id"]).first()
            if payment is None:
                return f"paid checkout {thing['id']} matched no payment (payment {ref!r}, user {user!r})"
            if payment.status == Payment.HELD:
                return f"payment {payment.pk} held: {payment.review}"
    elif kind in REFUND_EVENTS:
        services.refunded(payment, now.get("amount_refunded"), now.get("amount"),
                          latest=bool(settings.GODLING_STRIPE_SECRET_KEY))
    elif kind.startswith("charge.dispute."):  # created, updated, closed, funds_withdrawn…: the dispute as it is now
        services.dispute_changed(payment, now.get("id") or "", now.get("status"), now.get("amount"))
    return ""
