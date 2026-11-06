"""Credits (ADR-013): what powers cost, the packs viewers buy, each viewer's purse, and the ledger behind it.

Prices and packs are rows, so the admin changes them without a deployment. A purse's balance changes only through
apps.credits.services, which writes a ledger entry for every change; entries are never edited.
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Power(models.Model):
    """A sky power: its price and what the screen says about it. `key` is the world's name for it (world/main.lua
    SKY_POWERS); the screen draws its icon by that key. A power switched off is gone from the hotbar."""

    GIFT, WONDER, DISASTER = "Gift", "Wonder", "Disaster"

    key = models.CharField(max_length=30, unique=True)
    label = models.CharField(max_length=40)
    price = models.PositiveIntegerField(help_text="Credits per call.")
    enabled = models.BooleanField(default=True, help_text="Off: viewers cannot call it, and the hotbar leaves it out.")
    sort = models.PositiveSmallIntegerField(default=0)
    kind = models.CharField(max_length=10, default=GIFT, choices=[(GIFT, GIFT), (WONDER, WONDER), (DISASTER, DISASTER)])
    harms = models.BooleanField(default=False, help_text="Can hurt Godling: the slot carries a red corner.")
    description = models.TextField(max_length=300, blank=True, help_text="The tooltip: what it does.")
    rule = models.CharField(max_length=160, blank=True, help_text="The tooltip's rule line, e.g. how often.")
    did = models.CharField(max_length=60, blank=True, help_text='The pop-up: "<name> dropped a stone".')
    after = models.CharField(max_length=60, blank=True, help_text="The pop-up's second line.")

    class Meta:
        ordering = ["sort", "key"]

    def __str__(self):
        return f"{self.label} ({self.price} cr)"


class CreditPack(models.Model):
    """What a viewer can buy: so many credits for so much money."""

    key = models.SlugField(max_length=30, unique=True)
    name = models.CharField(max_length=40)
    credits = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    # Stripe charges no less than 50 cents in most currencies (docs.stripe.com/currencies#minimum-and-maximum-charge).
    price_cents = models.PositiveIntegerField(validators=[MinValueValidator(50)],
                                              help_text="In the smallest unit of the currency (cents), 50 at least.")
    active = models.BooleanField(default=True)
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort", "price_cents"]

    def __str__(self):
        return f"{self.name}: {self.credits} cr for {self.price_cents / 100:.2f}"


class Purse(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purse")
    balance = models.PositiveIntegerField(default=0)
    # Credits a refunded or disputed payment took back that the purse no longer held (spent already). Whatever comes
    # in next pays this first (services.change), so refunded credits cannot be spent twice.
    owed = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user}: {self.balance} cr" + (f", {self.owed} owed" if self.owed else "")


class Entry(models.Model):
    """One change to a purse: bought, given, spent on a power, given back when the world refused the power, or taken
    back when Stripe refunded the payment or the buyer disputed it."""

    PURCHASE, WELCOME, POWER, REFUND, GRANT, ADJUST = "purchase", "welcome", "power", "refund", "grant", "adjust"
    CLAWBACK = "clawback"
    KINDS = [(PURCHASE, "Bought"), (WELCOME, "Welcome credits"), (POWER, "Spent on a power"),
             (REFUND, "Given back"), (GRANT, "Granted by staff"), (ADJUST, "Changed by staff"),
             (CLAWBACK, "Taken back (payment refunded or disputed)")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="credit_entries")
    amount = models.IntegerField()
    kind = models.CharField(max_length=10, choices=KINDS)
    ref = models.CharField(max_length=120, blank=True)
    balance_after = models.PositiveIntegerField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created", "-id"]
        verbose_name_plural = "entries"
        constraints = [models.UniqueConstraint(fields=["user"], condition=models.Q(kind="welcome"),
                                               name="one_welcome_per_user")]

    def __str__(self):
        return f"{self.user} {self.amount:+d} ({self.kind})"


class Welcome(models.Model):
    """The welcome gift, once per inbox (users.User.email_key): me+1@ and me+2@ are one viewer's two accounts."""

    email_key = models.CharField(max_length=254, unique=True)
    # Kept when the account is deleted: the inbox has had its gift, and a new account from it gets none.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email_key} (first: {self.user})"


class PowerCall(models.Model):
    """Every power a viewer called through the site: what, where, what it cost, and what the world said.

    Queued when called, with its price already taken; the worker takes it to the island (apps.screen.tasks) and
    settles it: done with the world's answer, or expired when the island never answered (its credits come back)."""

    QUEUED, SENDING, DONE, EXPIRED = "queued", "sending", "done", "expired"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="power_calls")
    power = models.CharField(max_length=30)
    price = models.PositiveIntegerField(help_text="Credits taken (0 in test mode).")
    at_x = models.FloatField(null=True, blank=True)
    at_z = models.FloatField(null=True, blank=True)
    spots = models.JSONField(default=list, blank=True, help_text="A storm's strikes: up to three [x, z] (ADR-023).")
    ok = models.BooleanField(default=False, help_text="The world did it.")
    refunded = models.BooleanField(default=False)
    answer = models.CharField(max_length=200, blank=True, help_text="What the world said.")
    status = models.CharField(max_length=8, default=DONE, choices=[(QUEUED, "Queued"), (SENDING, "With the island"),
                                                                    (DONE, "Done"), (EXPIRED, "No answer")])
    reply = models.JSONField(default=dict, blank=True, help_text="The answer as the viewer's screen shows it.")
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        if self.status in (self.QUEUED, self.SENDING):
            return f"{self.user} {self.power} (on its way)"
        return f"{self.user} {self.power} ({'done' if self.ok else 'refused'})"


class Payment(models.Model):
    """A credit pack bought through Stripe Checkout.

    Made before Stripe's checkout session (views.buy), so a paid checkout always has its payment: the session carries
    this payment's id in its metadata, and a webhook finds it by that even if the session id was never saved.

    The payment keeps Stripe's facts as they arrive, in whatever order Stripe sends them: paid (paid_at) and for how
    much (amount_paid), refunded so far (amount_refunded), and the dispute's state. services.reconcile works out from
    them what the pack should give the viewer now and moves only the difference, recorded in `granted`, so a late,
    repeated or reordered event changes nothing it should not (ADR-014). A checkout Stripe charged less for, or in
    another currency, is held (`review`) until staff look at it."""

    OPEN, PAID, EXPIRED, REFUNDED, DISPUTED, HELD = "open", "paid", "expired", "refunded", "disputed", "held"
    PENDING = "pending_"  # the session id until Stripe has made the session

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    pack = models.CharField(max_length=40)
    credits = models.PositiveIntegerField()
    amount_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)
    session = models.CharField(max_length=255, unique=True, help_text="Stripe Checkout Session id (test_… for the "
                                                                       "development checkout).")
    payment_intent = models.CharField(max_length=255, blank=True, db_index=True,
                                      help_text="Stripe's PaymentIntent: how its refunds and disputes find this.")
    status = models.CharField(max_length=8, default=OPEN, choices=[(OPEN, "Open"), (PAID, "Paid"), (EXPIRED, "Expired"),
                                                                   (REFUNDED, "Refunded"), (DISPUTED, "Disputed"),
                                                                   (HELD, "Held for review")])
    amount_paid = models.PositiveIntegerField(null=True, blank=True, help_text="Cents Stripe charged for it.")
    amount_refunded = models.PositiveIntegerField(default=0, help_text="Cents Stripe has refunded so far.")
    dispute_id = models.CharField(max_length=255, blank=True)
    dispute_status = models.CharField(max_length=32, blank=True, help_text="Stripe's word for the dispute, if any.")
    dispute_amount = models.PositiveIntegerField(default=0, help_text="Cents the dispute is about.")
    review = models.CharField(max_length=200, blank=True, help_text="Why it is held for staff, if it is.")
    granted = models.PositiveIntegerField(default=0, help_text="Credits the pack gives the viewer now.")
    created = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.user}: {self.credits} cr, {self.status}"


class StripeEvent(models.Model):
    """A Stripe event already applied: Stripe may deliver one more than once, and it is applied once."""

    event_id = models.CharField(max_length=255, unique=True)
    kind = models.CharField(max_length=80)
    received = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=200, blank=True, help_text="Anything staff should see, e.g. a paid checkout "
                                                                  "that matched no payment.")

    def __str__(self):
        return f"{self.kind} {self.event_id}"
