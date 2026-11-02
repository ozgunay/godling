"""Every change to a purse goes through here: one locked row per purse, one ledger entry per change."""
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.credits.models import Entry, Payment, Power, Purse, Welcome


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


@transaction.atomic
def credit_payment(session, payment_intent=""):
    """Mark a payment paid and credit its pack, once however often Stripe (or the return page) reports it."""
    payment = Payment.objects.select_for_update().filter(session=session).first()
    if payment is None:
        return False
    if payment_intent and not payment.payment_intent:
        payment.payment_intent = payment_intent
        payment.save(update_fields=["payment_intent"])
    if payment.status != Payment.OPEN:
        return False
    payment.status, payment.paid_at = Payment.PAID, timezone.now()
    payment.save(update_fields=["status", "paid_at"])
    change(payment.user, payment.credits, Entry.PURCHASE, f"{payment.pack} ({session[:60]})")
    return True


def _held(payment):
    """Credits of this payment still in the viewer's hands: neither refunded nor held for a dispute."""
    return payment.credits - payment.refund_taken - payment.dispute_taken


@transaction.atomic
def refunded(payment, amount_refunded):
    """Stripe refunded `amount_refunded` cents of the payment so far (its running total): take back that share of
    the pack's credits, rounded up, less what earlier refunds took. Returns the credits taken back now."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status in (Payment.OPEN, Payment.EXPIRED) or not payment.amount_cents:
        return 0
    share = -(-payment.credits * min(amount_refunded, payment.amount_cents) // payment.amount_cents)
    due = min(max(0, share - payment.refund_taken), _held(payment))
    if due:
        take_back(payment.user, due, f"refund of {payment.pack} ({payment.session[:60]})")
        payment.refund_taken += due
    if payment.refund_taken >= payment.credits or amount_refunded >= payment.amount_cents:
        payment.status = Payment.REFUNDED
    payment.save(update_fields=["refund_taken", "status"])
    return due


@transaction.atomic
def disputed(payment):
    """The buyer disputed the payment with their bank: hold back every credit of it until the dispute ends."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status in (Payment.OPEN, Payment.EXPIRED):
        return 0
    due = _held(payment)
    if due:
        take_back(payment.user, due, f"dispute on {payment.pack} ({payment.session[:60]})")
        payment.dispute_taken += due
    payment.status = Payment.DISPUTED
    payment.save(update_fields=["dispute_taken", "status"])
    return due


@transaction.atomic
def dispute_closed(payment, won):
    """The dispute ended. Won (the payment stands): the held credits come back. Lost: they stay taken."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status != Payment.DISPUTED or not won:
        return 0
    back = payment.dispute_taken
    if back:
        change(payment.user, back, Entry.REFUND, f"dispute won on {payment.pack} ({payment.session[:60]})")
    payment.dispute_taken = 0
    payment.status = Payment.REFUNDED if payment.refund_taken >= payment.credits else Payment.PAID
    payment.save(update_fields=["dispute_taken", "status"])
    return back
