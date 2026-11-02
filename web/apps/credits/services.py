"""Every change to a purse goes through here: one locked row per purse, one ledger entry per change."""
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.credits.models import Entry, Payment, Power, Purse


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


@transaction.atomic
def change(user, amount, kind, ref=""):
    """Add `amount` (negative to take); the balance after. Raises NotEnough rather than go below zero."""
    Purse.objects.get_or_create(user=user)
    purse = Purse.objects.select_for_update().get(user=user)
    if purse.balance + amount < 0:
        raise NotEnough(purse.balance, -amount)
    purse.balance += amount
    purse.save(update_fields=["balance"])
    Entry.objects.create(user=user, amount=amount, kind=kind, ref=ref[:120], balance_after=purse.balance)
    return purse.balance


def spend(user, price, ref):
    return change(user, -price, Entry.POWER, ref)


def refund(user, price, ref):
    return change(user, price, Entry.REFUND, ref)


def welcome(user):
    """The new account's free credits, once (the user's choice: 20 on confirming the email)."""
    from apps.rules.models import Rules

    amount = Rules.get().welcome_credits
    if amount <= 0 or Entry.objects.filter(user=user, kind=Entry.WELCOME).exists():
        return False
    try:
        change(user, amount, Entry.WELCOME, "email confirmed")
    except IntegrityError:  # confirmed twice at once: the constraint keeps it to one
        return False
    return True


@transaction.atomic
def credit_payment(session):
    """Mark a payment paid and credit its pack, once however often Stripe (or the return page) reports it."""
    payment = Payment.objects.select_for_update().filter(session=session).first()
    if payment is None or payment.status == Payment.PAID:
        return False
    payment.status, payment.paid_at = Payment.PAID, timezone.now()
    payment.save(update_fields=["status", "paid_at"])
    change(payment.user, payment.credits, Entry.PURCHASE, f"{payment.pack} ({session[:60]})")
    return True
