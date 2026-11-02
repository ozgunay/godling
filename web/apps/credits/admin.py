"""Prices and packs are edited right in their lists; purses, the ledger and payments are records, read-only here.
A staff grant goes through the user admin's actions (apps.users.admin), so it lands in the ledger like any change."""
from django.contrib import admin

from apps.credits.models import CreditPack, Entry, Payment, Power, PowerCall, Purse


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
    list_display = ["user", "balance"]
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
    list_display = ["created", "user", "power", "price", "ok", "refunded", "aimed", "answer"]
    list_filter = ["power", "ok", "refunded", "created"]
    search_fields = ["user__username", "user__email", "answer"]
    date_hierarchy = "created"

    @admin.display(description="Aimed at")
    def aimed(self, obj):
        return f"({obj.at_x:.0f}, {obj.at_z:.0f})" if obj.at_x is not None else "the sky chose"


@admin.register(Payment)
class PaymentAdmin(ReadOnly):
    list_display = ["created", "user", "pack", "credits", "amount", "status", "paid_at", "session"]
    list_filter = ["status", "pack", "created"]
    search_fields = ["user__username", "user__email", "session"]
    date_hierarchy = "created"

    @admin.display(description="Amount")
    def amount(self, obj):
        return f"{obj.amount_cents / 100:.2f} {obj.currency.upper()}"
