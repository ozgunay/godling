"""Moderating notes (the user's choice: report after delivery). Reported notes first; hide or restore them, and mute,
unmute or ban their authors."""
from django.contrib import admin, messages
from django.db.models import Count

from apps.notes.models import Note, Report


class ReportInline(admin.TabularInline):
    model = Report
    extra = 0
    fields = ["created", "reporter", "reason", "reviewed"]
    readonly_fields = ["created", "reporter", "reason"]


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ["created", "author", "text", "status", "report_count", "author_muted"]
    list_filter = ["status", "created", "author__notes_muted"]
    search_fields = ["text", "author__username", "author__email"]
    readonly_fields = ["author", "text", "created"]
    fields = ["author", "text", "created", "status"]
    inlines = [ReportInline]
    date_hierarchy = "created"
    actions = ["hide", "restore", "mute_authors", "unmute_authors", "ban_authors"]

    ordering = ["-created"]  # sort by the Reports column to see the most reported first

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("author").annotate(n_reports=Count("reports"))

    @admin.display(description="Reports", ordering="n_reports")
    def report_count(self, obj):
        return obj.n_reports

    @admin.display(description="Author muted", boolean=True)
    def author_muted(self, obj):
        return obj.author.notes_muted

    def has_add_permission(self, request):
        return False

    @admin.action(description="Hide from every screen")
    def hide(self, request, queryset):
        n = queryset.update(status=Note.HIDDEN)
        Report.objects.filter(note__in=queryset).update(reviewed=True)
        self.message_user(request, f"{n} note(s) hidden.")

    @admin.action(description="Restore (shown again)")
    def restore(self, request, queryset):
        n = queryset.update(status=Note.SENT)
        Report.objects.filter(note__in=queryset).update(reviewed=True)
        self.message_user(request, f"{n} note(s) restored.")

    def _authors(self, queryset):
        from apps.users.models import User

        return User.objects.filter(pk__in=queryset.values("author"))

    @admin.action(description="Mute the authors' notes")
    def mute_authors(self, request, queryset):
        n = self._authors(queryset).update(notes_muted=True, notes_muted_reason="muted by a moderator")
        self.message_user(request, f"{n} account(s) muted.")

    @admin.action(description="Unmute the authors' notes")
    def unmute_authors(self, request, queryset):
        n = self._authors(queryset).update(notes_muted=False, notes_muted_reason="")
        Report.objects.filter(note__in=queryset).update(reviewed=True)
        self.message_user(request, f"{n} account(s) unmuted.")

    @admin.action(description="Ban the authors (no signing in)")
    def ban_authors(self, request, queryset):
        n = self._authors(queryset).filter(is_staff=False).update(is_active=False)
        self.message_user(request, f"{n} account(s) banned; staff accounts are never banned here.", messages.WARNING)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["created", "reporter", "reason", "note_text", "note_author", "reviewed"]
    list_filter = ["reviewed", "reason", "created"]
    list_editable = ["reviewed"]
    search_fields = ["note__text", "reporter__username", "note__author__username"]
    readonly_fields = ["note", "reporter", "reason", "created"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("note", "note__author", "reporter")

    @admin.display(description="Note")
    def note_text(self, obj):
        return obj.note.text[:80]

    @admin.display(description="Author")
    def note_author(self, obj):
        return obj.note.author

    def has_add_permission(self, request):
        return False
