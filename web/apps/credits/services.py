"""Every change to a purse goes through here: one locked row per purse, one ledger entry per change.

Locks are always taken in one order, a payment's row before its viewer's purse, so two changes never wait on each
other in a circle."""
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.credits.models import Entry, Payment, Power, Purse, Welcome

log = logging.getLogger("godling.credits")


class NotEnough(Exception):
    def __init__(self, balance, price):
        super().__init__(f"{price} credits needed, {balance} held")
        self.balance, self.price = balance, price


def balance_of(user):
    purse = Purse.objects.filter(user=user).first()
    return purse.balance if purse else 0


def prices():
    """Each enabled power's price, by its world name."""
    return {p.key: p.price for p in Power.objects.filter(enabled=True)}


def powers():
    """Each enabled power as the screen shows it (the admin edits all of it), by its world name."""
    return {p.key: {"label": p.label, "price": p.price, "kind": p.kind, "harms": p.harms, "does": p.description,
                    "rule": p.rule, "did": p.did, "after": p.after} for p in Power.objects.filter(enabled=True)}


def _purse(user):
    Purse.objects.get_or_create(user=user)
    return Purse.objects.select_for_update().get(user=user)


@transaction.atomic
def change(user, amount, kind, ref=""):
    """Add `amount` (negative to take); the balance after. Raises NotEnough rather than go below zero.

    Credits coming in first pay what the purse owes from a refunded or disputed payment (take_back)."""
    purse = _purse(user)
    if purse.balance + amount < 0:
        raise NotEnough(purse.balance, -amount)
    purse.balance += amount
    purse.save(update_fields=["balance"])
    Entry.objects.create(user=user, amount=amount, kind=kind, ref=ref[:120], balance_after=purse.balance)
    if amount > 0 and purse.owed:
        paid = min(purse.owed, purse.balance)
        purse.balance -= paid
        purse.owed -= paid
        purse.save(update_fields=["balance", "owed"])
        Entry.objects.create(user=user, amount=-paid, kind=Entry.CLAWBACK, ref="owed from a refunded or disputed payment",
                             balance_after=purse.balance)
    return purse.balance


@transaction.atomic
def take_back(user, amount, ref):
    """Take back `amount` credits a payment brought (refunded or disputed). What the purse no longer holds is owed,
    and paid from what comes in next. Returns (taken now, owed)."""
    purse = _purse(user)
    taken = min(purse.balance, amount)
    purse.balance -= taken
    purse.owed += amount - taken
    purse.save(update_fields=["balance", "owed"])
    if taken:
        Entry.objects.create(user=user, amount=-taken, kind=Entry.CLAWBACK, ref=ref[:120], balance_after=purse.balance)
    return taken, amount - taken


def spend(user, price, ref):
    return change(user, -price, Entry.POWER, ref)


def refund(user, price, ref):
    return change(user, price, Entry.REFUND, ref)


def welcome(user):
    """The new account's free credits (the user's choice: 20 on confirming the email), once per inbox: an account
    made from the same inbox as one already welcomed (me+2@, m.e@gmail.com) gets none (Welcome, ADR-014)."""
    from apps.rules.models import Rules
    from apps.users.validators import canonical_email

    amount = Rules.get().welcome_credits
    if amount <= 0 or Entry.objects.filter(user=user, kind=Entry.WELCOME).exists():
        return False
    try:
        with transaction.atomic():
            Welcome.objects.create(email_key=user.email_key or canonical_email(user.email), user=user)
            change(user, amount, Entry.WELCOME, "email confirmed")
    except IntegrityError:  # this inbox was welcomed already, or confirmed twice at once
        return False
    return True


# Stripe's dispute states (docs.stripe.com/api/disputes/object). Open ones, and a lost one, hold back the pack's
# credits; a won dispute, or an inquiry closed without a chargeback, gives them back. The last three are final.
DISPUTE_OPEN = {"warning_needs_response", "warning_under_review", "needs_response", "under_review"}
DISPUTE_FINAL = {"won", "lost", "warning_closed"}


def due_credits(payment):
    """What the pack should give the viewer now, from Stripe's facts kept on the payment.

    Nothing until it is paid, while it is held for review, or while a dispute is open. Otherwise its credits less the
    share of the money that went back, rounded up: what was refunded, and what a lost dispute took. The share is of
    what Stripe charged, which is also what its refunds are counted in."""
    if payment.paid_at is None or payment.review or payment.dispute_status in DISPUTE_OPEN:
        return 0
    charged = payment.amount_paid or payment.amount_cents
    lost = (payment.dispute_amount or charged) if payment.dispute_status == "lost" else 0  # amount unknown: all of it
    back = payment.amount_refunded + lost
    share = -(-payment.credits * min(back, charged) // charged) if charged else payment.credits
    return max(0, payment.credits - share)


def reconcile(payment, why, kind=Entry.REFUND):
    """Bring the viewer's purse in line with what the pack should give now: only the difference moves. Repeated,
    late or reordered events therefore change nothing they should not. Call it inside the payment's row lock.
    `kind` names credits that come in (bought, or given back after a failed refund or a won dispute)."""
    due = due_credits(payment)
    move = due - payment.granted
    if move > 0:
        change(payment.user, move, kind, f"{payment.pack}: {why} ({payment.session[:60]})")
    elif move < 0:
        take_back(payment.user, -move, f"{payment.pack}: {why} ({payment.session[:60]})")
    payment.granted = due
    if payment.paid_at is not None:
        payment.status = (Payment.HELD if payment.review
                          else Payment.DISPUTED if payment.dispute_status in DISPUTE_OPEN | {"lost"}
                          else Payment.REFUNDED if due == 0 else Payment.PAID)
    payment.save(update_fields=["granted", "status", "amount_paid", "amount_refunded", "dispute_id",
                                "dispute_status", "dispute_amount", "review", "payment_intent", "paid_at", "session"])
    return move


def _locked(payment):
    return Payment.objects.select_for_update().get(pk=payment.pk)


def _for_session(session, payment_ref="", user_ref=""):
    """The locked payment of a checkout session: by its id, or by the payment id the session carries in its metadata
    (views.buy), for a session whose id was never saved. The metadata's user must be the payment's."""
    payment = Payment.objects.select_for_update().filter(session=session).first()
    if payment is None and str(payment_ref or "").isdigit():
        payment = Payment.objects.select_for_update().filter(pk=int(payment_ref),
                                                             session__startswith=Payment.PENDING).first()
        if payment is not None and user_ref and str(payment.user_id) != str(user_ref):
            payment = None
        if payment is not None:
            payment.session = session
    return payment


@transaction.atomic
def credit_payment(session, payment_intent="", amount_total=None, currency="", payment_ref="", user_ref=""):
    """Stripe (or the return page) says the checkout is paid: the pack's credits go to the viewer, less anything a
    refund or dispute Stripe told of first. Once, however often it is reported.

    What Stripe charged (`amount_total`, `currency`) is checked against the pack: less, or another currency, and the
    payment is held for staff (release_review) instead of crediting. Returns True if credits moved now; False also
    when no payment matches, which is logged: someone paid and got nothing yet."""
    payment = _for_session(session, payment_ref, user_ref)
    if payment is None:
        log.error("Paid checkout %s matches no payment (metadata payment %r, user %r)", session, payment_ref, user_ref)
        return False
    payment.payment_intent = payment.payment_intent or payment_intent
    if payment.paid_at is None:  # the first report of it paid: checked once, so a release by staff stays released
        payment.paid_at = timezone.now()
        if amount_total is not None:
            payment.amount_paid = int(amount_total)
            wrong_currency = bool(currency) and str(currency).lower() != payment.currency.lower()
            if payment.amount_paid < payment.amount_cents or wrong_currency:
                payment.review = (f"Stripe charged {payment.amount_paid} {currency or payment.currency}; the pack "
                                  f"costs {payment.amount_cents} {payment.currency}")
                log.error("Payment %s held: %s", payment.pk, payment.review)
    return reconcile(payment, "paid", Entry.PURCHASE) > 0


@transaction.atomic
def checkout_expired(session, payment_ref="", user_ref=""):
    """The checkout ended unpaid (expired, or a delayed payment failed): the payment closes, crediting nothing."""
    payment = _for_session(session, payment_ref, user_ref)
    if payment is None or payment.paid_at is not None:
        return False
    payment.status = Payment.EXPIRED
    payment.save(update_fields=["status", "session"])
    return True


@transaction.atomic
def refunded(payment, amount_refunded, charged=None, latest=True):
    """Stripe has refunded `amount_refunded` cents of the payment, as its charge says now. From the charge as it is
    now (`latest`, fetched from Stripe), the total is taken as it is: a refund that failed lowers it, and its credits
    come back. From an event's own copy, which may be older, the total only grows. Kept even before the checkout is
    reported paid, so credits granted later already leave the refunded share out."""
    payment = _locked(payment)
    total = int(amount_refunded or 0)
    payment.amount_refunded = total if latest else max(payment.amount_refunded, total)
    if charged and payment.amount_paid is None:
        payment.amount_paid = int(charged)
    return reconcile(payment, "refund")


@transaction.atomic
def dispute_changed(payment, dispute_id, status, amount=0):
    """A dispute on the payment, as it is now: `status` (Stripe's word) and the `amount` in cents it is about. A
    final state stays final: a repeated or late "created" event never reopens a dispute that was won or lost."""
    payment = _locked(payment)
    status = str(status or "")
    if payment.dispute_status in DISPUTE_FINAL and payment.dispute_id == dispute_id and status not in DISPUTE_FINAL:
        return 0
    payment.dispute_id, payment.dispute_status = dispute_id or payment.dispute_id, status
    payment.dispute_amount = int(amount or 0) or payment.dispute_amount
    return reconcile(payment, f"dispute {status.replace('_', ' ')}")


@transaction.atomic
def release_review(payment, by):
    """Staff looked at a held payment and let it stand: the pack's credits go to the viewer."""
    payment = _locked(payment)
    if not payment.review:
        return 0
    log.warning("Payment %s released by %s (was: %s)", payment.pk, by, payment.review)
    payment.review = ""
    return reconcile(payment, f"released by {by}", Entry.PURCHASE)
