from django.contrib import admin
from django.shortcuts import redirect

from apps.rules.models import BlockedWord, Rules


@admin.register(Rules)
class RulesAdmin(admin.ModelAdmin):
    """One row: the list goes straight to it."""

    fieldsets = [
        ("Credits", {"fields": ["welcome_credits", "free_powers"]}),
        ("Pace", {"fields": ["power_every", "note_every"]}),
        ("Notes", {"fields": ["note_limit", "reports_to_hide", "report_min_age_hours", "reports_per_hour"]}),
        ("Feedback", {"fields": ["feedback_per_hour", "feedback_email"]}),
    ]

    def changelist_view(self, request, extra_context=None):
        return redirect("admin:rules_rules_change", Rules.get().pk)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BlockedWord)
class BlockedWordAdmin(admin.ModelAdmin):
    list_display = ["word", "applies_to", "active", "added"]
    list_editable = ["applies_to", "active"]
    list_filter = ["applies_to", "active"]
    search_fields = ["word"]
