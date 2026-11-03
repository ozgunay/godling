"""Prices and packs are edited right in their lists; purses, the ledger, payments and Stripe's events are records,
read-only here. A staff grant goes through the user admin's actions (apps.users.admin), so it lands in the ledger like
any change; a held payment is let stand through its own action."""
from django.contrib import admin

from apps.credits import services
from apps.credits.models import CreditPack, Entry, Payment, Power, PowerCall, Purse, StripeEvent


@admin.register(Power)
class PowerAdmin(admin.ModelAdmin):
    """Prices in their list; each power's words on its page. The key must match the world's name for the power."""
    list_display = ["label", "key", "price", "kind", "harms", "enabled", "sort"]
    list_editable = ["price", "enabled", "sort"]
    list_display_links = ["label"]
    search_fields = ["label", "key"]
    fieldsets = [
        (None, {"fields": ["key", "label", "price", "enabled", "sort"]}),
        ("What the screen says", {"fields": ["kind", "harms", "description", "rule", "did", "after"]}),
    ]


@admin.register(CreditPack)
class CreditPackAdmin(admin.ModelAdmin):
    list_display = ["name", "key", "credits", "price_cents", "per_credit", "active", "sort"]
    list_editable = ["credits", "price_cents", "active", "sort"]
    list_display_links = ["name"]

    @admin.display(description="Per credit (cents)")
    def per_credit(self, obj):
        return f"{obj.price_cents / obj.credits:.2f}" if obj.credits else "-"


class ReadOnly(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Purse)
class PurseAdmin(ReadOnly):
    list_display = ["user", "balance", "owed"]
    search_fields = ["user__username", "user__email"]
    ordering = ["-balance"]


@admin.register(Entry)
class EntryAdmin(ReadOnly):
    list_display = ["created", "user", "kind", "amount", "balance_after", "ref"]
    list_filter = ["kind", "created"]
    search_fields = ["user__username", "ref"]
    date_hierarchy = "created"


@admin.register(PowerCall)
class PowerCallAdmin(ReadOnly):
    list_display = ["created", "user", "power", "price", "status", "ok", "refunded", "aimed", "answer"]
    list_filter = ["status", "power", "ok", "refunded", "created"]
    search_fields = ["user__username", "user__email", "answer"]
    date_hierarchy = "created"

    @admin.display(description="Aimed at")
    def aimed(self, obj):
        return f"({obj.at_x:.0f}, {obj.at_z:.0f})" if obj.at_x is not None else "the sky chose"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Records, never edited by hand: what Stripe said is kept as it said it, and credits move only through
    services. The one thing staff do here is let a held payment stand (Stripe charged less than the pack, or in
    another currency), after looking at it in Stripe's dashboard; otherwise they refund it there."""
    list_display = ["created", "user", "pack", "credits", "amount", "charged", "granted", "status", "refunded",
                    "dispute_status", "review", "paid_at", "session"]
    list_filter = ["status", "pack", "dispute_status", "created"]
    search_fields = ["user__username", "user__email", "session", "payment_intent", "dispute_id"]
    date_hierarchy = "created"
    actions = ["release"]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Price")
    def amount(self, obj):
        return f"{obj.amount_cents / 100:.2f} {obj.currency.upper()}"

    @admin.display(description="Charged")
    def charged(self, obj):
        return "-" if obj.amount_paid is None else f"{obj.amount_paid / 100:.2f}"

    @admin.display(description="Refunded")
    def refunded(self, obj):
        return f"{obj.amount_refunded / 100:.2f}" if obj.amount_refunded else "-"

    @admin.action(permissions=["change"], description="Let held payments stand: credit their packs")
    def release(self, request, queryset):
        held = list(queryset.filter(status=Payment.HELD))
        for payment in held:
            services.release_review(payment, request.user.username)
        self.message_user(request, f"{len(held)} held payment(s) released.")


@admin.register(StripeEvent)
class StripeEventAdmin(ReadOnly):
    """Every Stripe event applied, once each; a note marks one staff should look at."""
    list_display = ["received", "kind", "event_id", "note"]
    list_filter = ["kind", "received"]
    search_fields = ["event_id", "note"]
    date_hierarchy = "received"
