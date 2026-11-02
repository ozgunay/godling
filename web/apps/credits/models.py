"""Credits (ADR-013): what powers cost, the packs viewers buy, each viewer's purse, and the ledger behind it.

Prices and packs are rows, so the admin changes them without a deployment. A purse's balance changes only through
apps.credits.services, which writes a ledger entry for every change; entries are never edited.
"""
from django.conf import settings
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
    credits = models.PositiveIntegerField()
    price_cents = models.PositiveIntegerField(help_text="In the smallest unit of the currency (cents).")
    active = models.BooleanField(default=True)
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort", "price_cents"]

    def __str__(self):
        return f"{self.name}: {self.credits} cr for {self.price_cents / 100:.2f}"


class Purse(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purse")
    balance = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user}: {self.balance} cr"


class Entry(models.Model):
    """One change to a purse: bought, given, spent on a power, or given back when the world refused the power."""

    PURCHASE, WELCOME, POWER, REFUND, GRANT, ADJUST = "purchase", "welcome", "power", "refund", "grant", "adjust"
    KINDS = [(PURCHASE, "Bought"), (WELCOME, "Welcome credits"), (POWER, "Spent on a power"),
             (REFUND, "Given back"), (GRANT, "Granted by staff"), (ADJUST, "Changed by staff")]

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


class PowerCall(models.Model):
    """Every power a viewer called through the site: what, where, what it cost, and what the world said."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="power_calls")
    power = models.CharField(max_length=30)
    price = models.PositiveIntegerField(help_text="Credits taken (0 in test mode).")
    at_x = models.FloatField(null=True, blank=True)
    at_z = models.FloatField(null=True, blank=True)
    ok = models.BooleanField(help_text="The world did it.")
    refunded = models.BooleanField(default=False)
    answer = models.CharField(max_length=200, blank=True, help_text="What the world said.")
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.user} {self.power} ({'done' if self.ok else 'refused'})"


class Payment(models.Model):
    """A credit pack bought through Stripe Checkout; credited once, when Stripe says it is paid."""

    OPEN, PAID, EXPIRED = "open", "paid", "expired"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    pack = models.CharField(max_length=40)
    credits = models.PositiveIntegerField()
    amount_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)
    session = models.CharField(max_length=255, unique=True, help_text="Stripe Checkout Session id (test_… for the "
                                                                       "development checkout).")
    status = models.CharField(max_length=8, default=OPEN, choices=[(OPEN, "Open"), (PAID, "Paid"),
                                                                   (EXPIRED, "Expired")])
    created = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.user}: {self.credits} cr, {self.status}"
