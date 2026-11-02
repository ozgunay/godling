"""Buying credits with Stripe Checkout (the user's choice of provider).

Stripe's hosted checkout takes the payment; its webhook (or, if that is late, the return page asking Stripe) marks the
payment paid, and services.credit_payment credits the pack once. Without Stripe keys, in development only, a test
checkout stands in so the whole flow can be tried locally; it is never there in production.
"""
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
from apps.credits.models import CreditPack, Entry, Payment, StripeEvent


def money(cents):
    symbol = {"eur": "€", "usd": "$", "gbp": "£"}.get(settings.GODLING_CURRENCY, "")
    return f"{symbol}{cents / 100:.2f}" if symbol else f"{cents / 100:.2f} {settings.GODLING_CURRENCY.upper()}"


def checkout_mode():
    if settings.GODLING_STRIPE_SECRET_KEY:
        return "stripe"
    return "test" if settings.DEBUG else ""


@login_required
def credits_page(request):
    packs = [{"pack": p, "price": money(p.price_cents)} for p in CreditPack.objects.filter(active=True)]
    return render(request, "credits/credits.html", {
        "balance": services.balance_of(request.user), "packs": packs, "mode": checkout_mode(),
        "entries": Entry.objects.filter(user=request.user)[:12]})


@login_required
@require_POST
def buy(request, key):
    pack = get_object_or_404(CreditPack, key=key, active=True)
    mode = checkout_mode()
    common = {"user": request.user, "pack": pack.key, "credits": pack.credits, "amount_cents": pack.price_cents,
              "currency": settings.GODLING_CURRENCY}
    if mode == "stripe":
        done = request.build_absolute_uri(reverse("credits_done")) + "?session_id={CHECKOUT_SESSION_ID}"
        session = stripe.checkout.Session.create(
            api_key=settings.GODLING_STRIPE_SECRET_KEY, mode="payment",
            line_items=[{"quantity": 1, "price_data": {
                "currency": settings.GODLING_CURRENCY, "unit_amount": pack.price_cents,
                "product_data": {"name": f"{pack.credits} credits for Godling ({pack.name})"}}}],
            success_url=done, cancel_url=request.build_absolute_uri(reverse("credits")),
            client_reference_id=str(request.user.pk), customer_email=request.user.email,
            metadata={"user": str(request.user.pk), "pack": pack.key, "credits": str(pack.credits)})
        Payment.objects.create(session=session.id, **common)
        return redirect(session.url, permanent=False)
    if mode == "test":
        payment = Payment.objects.create(session=f"test_{uuid.uuid4().hex}", **common)
        return redirect("credits_test_checkout", session=payment.session)
    messages.error(request, "Buying credits is not set up yet.")
    return redirect("credits")


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
                services.credit_payment(session, getattr(found, "payment_intent", None) or "")
        except stripe.StripeError:
            pass  # the webhook will still come
        payment.refresh_from_db()
    return render(request, "credits/done.html", {"payment": payment, "balance": services.balance_of(request.user)})


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
            if payment:
                Payment.objects.filter(pk=payment.pk).update(payment_intent=payment_intent)
    return payment


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Stripe tells the site a checkout finished, or that a payment was refunded or disputed. Signed with
    GODLING_STRIPE_WEBHOOK_SECRET; anything else is refused.

    Each event is applied once (StripeEvent), in one transaction with its record, so an event that fails is not marked
    seen and Stripe's retry applies it. What an event says is kept on the payment, and services.reconcile moves only
    the difference it makes, so events may come in any order (docs.stripe.com/webhooks#event-ordering). A refund takes
    back its share of the pack's credits; a dispute holds back all of them until the bank decides, and a won dispute
    gives them back. Credits already spent are owed, and paid from what comes in next (services.take_back)."""
    if not settings.GODLING_STRIPE_WEBHOOK_SECRET:
        return HttpResponseBadRequest("not set up")
    try:
        event = stripe.Webhook.construct_event(request.body, request.headers.get("Stripe-Signature", ""),
                                               settings.GODLING_STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponseBadRequest("bad signature")
    event_id, kind, thing = event.get("id") or "", event["type"], event["data"]["object"]
    if event_id and StripeEvent.objects.filter(event_id=event_id).exists():
        return HttpResponse("seen")
    payment = None
    if kind == "charge.refunded" or kind.startswith("charge.dispute."):
        try:
            payment = payment_for(thing.get("payment_intent"))
        except AskAgain:
            return HttpResponse("Stripe could not be reached; send it again", status=503)
        if payment is None:
            return HttpResponse("not ours")
    try:
        with transaction.atomic():
            if event_id:
                StripeEvent.objects.create(event_id=event_id, kind=kind[:80])
            apply_event(kind, thing, payment)
    except IntegrityError:  # the same event, delivered twice at once: the other delivery applied it
        return HttpResponse("seen")
    return HttpResponse("ok")


def apply_event(kind, thing, payment):
    if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if thing.get("payment_status") == "paid":
            services.credit_payment(thing["id"], thing.get("payment_intent") or "")
    elif kind in ("checkout.session.expired", "checkout.session.async_payment_failed"):
        Payment.objects.filter(session=thing["id"], status=Payment.OPEN, paid_at__isnull=True).update(
            status=Payment.EXPIRED)
    elif kind == "charge.refunded":  # a charge: its running refunded total
        services.refunded(payment, int(thing.get("amount_refunded") or 0))
    elif kind.startswith("charge.dispute."):  # created, updated, closed, funds_withdrawn…: the dispute as it is now
        services.dispute_changed(payment, thing.get("id") or "", thing.get("status"))
