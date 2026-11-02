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


# Stripe's dispute states (docs.stripe.com/api/disputes/object). Open ones, and a lost one, hold back the pack's
# credits; a won dispute, or an inquiry closed without a chargeback, gives them back. The last three are final.
DISPUTE_OPEN = {"warning_needs_response", "warning_under_review", "needs_response", "under_review"}
DISPUTE_FINAL = {"won", "lost", "warning_closed"}


def due_credits(payment):
    """What the pack should give the viewer now, from Stripe's facts kept on the payment: nothing until it is paid
    or while a dispute holds it (or after one is lost), else its credits less the refunded share, rounded up."""
    if payment.paid_at is None or payment.dispute_status in DISPUTE_OPEN | {"lost"}:
        return 0
    refunded = min(payment.amount_refunded, payment.amount_cents)
    share = -(-payment.credits * refunded // payment.amount_cents) if payment.amount_cents else 0
    return max(0, payment.credits - share)


def reconcile(payment, why):
    """Bring the viewer's purse in line with what the pack should give now: only the difference moves. Repeated,
    late or reordered events therefore change nothing they should not. Call it inside the payment's row lock."""
    due = due_credits(payment)
    move = due - payment.granted
    if move > 0:
        kind = Entry.PURCHASE if why == "paid" else Entry.REFUND
        change(payment.user, move, kind, f"{payment.pack}: {why} ({payment.session[:60]})")
    elif move < 0:
        take_back(payment.user, -move, f"{payment.pack}: {why} ({payment.session[:60]})")
    payment.granted = due
    if payment.paid_at is not None:
        payment.status = (Payment.DISPUTED if payment.dispute_status in DISPUTE_OPEN | {"lost"}
                          else Payment.REFUNDED if due == 0 else Payment.PAID)
    payment.save(update_fields=["granted", "status", "amount_refunded", "dispute_id", "dispute_status",
                                "payment_intent", "paid_at"])
    return move


def _locked(payment):
    return Payment.objects.select_for_update().get(pk=payment.pk)


@transaction.atomic
def credit_payment(session, payment_intent=""):
    """Stripe (or the return page) says the checkout is paid: the pack's credits go to the viewer, less anything a
    refund or dispute Stripe told of first. Once, however often it is reported. True if credits moved now."""
    payment = Payment.objects.select_for_update().filter(session=session).first()
    if payment is None:
        return False
    payment.payment_intent = payment.payment_intent or payment_intent
    if payment.paid_at is None:
        payment.paid_at = timezone.now()
    return reconcile(payment, "paid") > 0


@transaction.atomic
def refunded(payment, amount_refunded):
    """Stripe refunded `amount_refunded` cents of the payment so far (its running total, which only grows). Kept even
    before the checkout is reported paid, so credits granted later already leave the refunded share out."""
    payment = _locked(payment)
    payment.amount_refunded = max(payment.amount_refunded, int(amount_refunded or 0))
    return reconcile(payment, "refunded")


@transaction.atomic
def dispute_changed(payment, dispute_id, status):
    """A dispute on the payment moved to `status`. A final state stays final: a repeated or late "created" event
    never reopens a dispute that was won or lost."""
    payment = _locked(payment)
    status = str(status or "")
    if payment.dispute_status in DISPUTE_FINAL and payment.dispute_id == dispute_id and status not in DISPUTE_FINAL:
        return 0
    payment.dispute_id, payment.dispute_status = dispute_id or payment.dispute_id, status
    return reconcile(payment, f"dispute {status.replace('_', ' ')}")
