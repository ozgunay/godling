"""Reading viewers' feedback: new first, filtered by kind and status, with the screen's facts when the viewer attached
them and a link to write back."""
from urllib.parse import quote

from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from apps.feedback.models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ["created", "kind", "status", "author", "short_text", "watching"]
    list_editable = ["status"]
    list_filter = ["status", "kind", "created"]
    search_fields = ["text", "staff_note", "author__username", "author__email"]
    readonly_fields = ["author", "write_back", "kind", "created", "text", "screen_shown"]
    fields = ["author", "write_back", "kind", "created", "text", "screen_shown", "status", "staff_note"]
    list_select_related = ["author"]
    date_hierarchy = "created"
    actions = ["looking", "done"]

    @admin.display(description="Message")
    def short_text(self, obj):
        return obj.text if len(obj.text) <= 80 else obj.text[:80] + "…"

    @admin.display(description="Watching")
    def watching(self, obj):
        return {"live": "live", "replay": "the past"}.get((obj.screen or {}).get("view"), "–")

    @admin.display(description="Write back")
    def write_back(self, obj):
        if not obj.author or not obj.author.email:
            return "–"
        # Percent-encoded: a valid address may hold ? # or %, which a mailto URL would read as headers or a fragment.
        return format_html('<a href="mailto:{}">{}</a>', quote(obj.author.email, safe="@"), obj.author.email)

    @admin.display(description="Their screen")
    def screen_shown(self, obj):
        lines = obj.facts()
        return format_html_join(mark_safe("<br>"), "{}", ((line,) for line in lines)) if lines else "Not attached"

    def has_add_permission(self, request):
        return False

    @admin.action(permissions=["change"], description="Mark as being looked at")
    def looking(self, request, queryset):
        self.message_user(request, f"{queryset.update(status=Feedback.LOOKING)} message(s) marked.")

    @admin.action(permissions=["change"], description="Mark as done")
    def done(self, request, queryset):
        self.message_user(request, f"{queryset.update(status=Feedback.DONE)} message(s) marked done.")
