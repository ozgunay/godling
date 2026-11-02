"""The viewers, and the disposable-domain blocklist. Borrowed from AgentOp's admin (C:/Work/agentop, apps/users/admin.py):
the user admin's shape, and the blocklist's actions and import views (sync the online lists, import the bundled file,
paste a list). Godling adds what running the island needs: each viewer's credits and notes, and actions to grant
credits, mute or unmute notes, and ban or unban.
"""
import re
import urllib.request

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.html import format_html

from apps.credits import services as credits
from apps.credits.models import Entry, PowerCall
from apps.users.models import DisposableDomain, User
from apps.users.validators import (DISPOSABLE_DOMAINS_FILE, FALLBACK_DISPOSABLE_DOMAINS,
                                   invalidate_disposable_domains_cache)

_DOMAIN_RE = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$")

ONLINE_SOURCES = [
    "https://raw.githubusercontent.com/disposable-email-domains/disposable-email-domains/main/disposable_email_blocklist.conf",
    "https://raw.githubusercontent.com/disposable/disposable-email-domains/master/domains.txt",
    "https://raw.githubusercontent.com/7c/fakefilter/main/txt/data.txt",
    "https://raw.githubusercontent.com/FGRibreau/mailchecker/master/list.txt",
]


def _parse_domain_text(text):
    """Extract valid lowercase domains from a newline-separated text block."""
    found = set()
    for raw in text.splitlines():
        line = raw.strip().lower().lstrip(".")
        if not line or line.startswith("#"):
            continue
        if _DOMAIN_RE.match(line):
            found.add(line)
    return found


def _bulk_insert(domains, source):
    """Insert *domains* not already in the table.  Returns (added, skipped)."""
    existing = set(DisposableDomain.objects.filter(domain__in=domains).values_list("domain", flat=True))
    new_domains = domains - existing
    if new_domains:
        DisposableDomain.objects.bulk_create(
            [DisposableDomain(domain=d, source=source) for d in sorted(new_domains)], batch_size=1000)
    invalidate_disposable_domains_cache()
    return len(new_domains), len(existing)


# ─── Viewers ──────────────────────────────────────────────────────────────────


class EntryInline(admin.TabularInline):
    """The viewer's credit ledger, latest first (read-only: credits change only through services or the actions)."""
    model = Entry
    fields = ["created", "kind", "amount", "balance_after", "ref"]
    readonly_fields = fields
    extra = 0
    max_num = 0
    can_delete = False
    ordering = ["-created"]
    verbose_name_plural = "Credits ledger"


class PowerCallInline(admin.TabularInline):
    """The powers the viewer called, latest first (read-only)."""
    model = PowerCall
    fields = ["created", "power", "price", "ok", "refunded", "answer"]
    readonly_fields = fields
    extra = 0
    max_num = 0
    can_delete = False
    ordering = ["-created"]
    verbose_name_plural = "Powers called"


class AdjustCreditsForm(forms.Form):
    amount = forms.IntegerField(min_value=-1_000_000, max_value=1_000_000,
                                help_text="Credits to add; a minus sign takes them away.")
    reason = forms.CharField(max_length=80, help_text="Kept in the viewer's ledger, e.g. 'refund for a lost meteor'.")

    def clean_amount(self):
        if self.cleaned_data["amount"] == 0:
            raise forms.ValidationError("Zero changes nothing.")
        return self.cleaned_data["amount"]


@admin.register(User)
class ViewerAdmin(UserAdmin):
    list_display = ["username", "email", "verified", "credits", "notes_sent", "notes_muted", "is_active", "date_joined",
                    "last_login"]
    change_form_template = "admin/users/user/change_form.html"
    list_filter = ["is_active", "notes_muted", "is_staff", "date_joined"]
    search_fields = ["username", "email"]
    ordering = ["-date_joined"]
    inlines = [EntryInline, PowerCallInline]
    fieldsets = UserAdmin.fieldsets + (
        ("Notes", {"fields": ("notes_muted", "notes_muted_at", "notes_muted_reason")}),
    )
    actions = ["grant_20", "grant_100", "mute_notes", "unmute_notes", "ban", "unban"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("purse").annotate(n_notes=Count("notes", distinct=True))

    @admin.display(description="Credits", ordering="purse__balance")
    def credits(self, obj):
        purse = getattr(obj, "purse", None)
        return purse.balance if purse else 0

    @admin.display(description="Notes", ordering="n_notes")
    def notes_sent(self, obj):
        return obj.n_notes

    @admin.display(description="Email confirmed", boolean=True)
    def verified(self, obj):
        return obj.emailaddress_set.filter(verified=True).exists()

    def get_urls(self):
        return [path("<int:user_id>/credits/", self.admin_site.admin_view(self.adjust_credits),
                     name="users_user_adjust_credits")] + super().get_urls()

    def adjust_credits(self, request, user_id):
        """Any amount in or out of one viewer's purse, with a reason, as a ledger entry (never below zero)."""
        viewer = get_object_or_404(User, pk=user_id)
        if not self.has_change_permission(request, viewer):
            return HttpResponseRedirect(reverse("admin:index"))
        form = AdjustCreditsForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            amount = form.cleaned_data["amount"]
            try:
                balance = credits.change(viewer, amount, Entry.ADJUST,
                                         f"{form.cleaned_data['reason']} ({request.user.username})")
            except credits.NotEnough as short:
                form.add_error("amount", f"{viewer} holds {short.balance}: a purse never goes below zero.")
            else:
                self.message_user(request, f"{viewer}: {amount:+d} credits, {balance} now.", messages.SUCCESS)
                return HttpResponseRedirect(reverse("admin:users_user_change", args=[viewer.pk]))
        return render(request, "admin/users/user/adjust_credits.html", {
            **self.admin_site.each_context(request), "title": f"Credits of {viewer}", "viewer": viewer, "form": form,
            "balance": credits.balance_of(viewer), "opts": self.model._meta,
            "entries": Entry.objects.filter(user=viewer)[:10]})

    def _grant(self, request, queryset, amount):
        for user in queryset:
            credits.change(user, amount, Entry.GRANT, f"granted by {request.user.username}")
        self.message_user(request, f"Granted {amount} credits to {queryset.count()} viewer(s).")

    @admin.action(description="Grant 20 credits")
    def grant_20(self, request, queryset):
        self._grant(request, queryset, 20)

    @admin.action(description="Grant 100 credits")
    def grant_100(self, request, queryset):
        self._grant(request, queryset, 100)

    @admin.action(description="Mute their notes")
    def mute_notes(self, request, queryset):
        n = queryset.update(notes_muted=True, notes_muted_reason="muted by a moderator")
        self.message_user(request, f"{n} viewer(s) muted.")

    @admin.action(description="Unmute their notes")
    def unmute_notes(self, request, queryset):
        n = queryset.update(notes_muted=False, notes_muted_reason="")
        self.message_user(request, f"{n} viewer(s) unmuted.")

    @admin.action(description="Ban (no signing in)")
    def ban(self, request, queryset):
        n = queryset.filter(is_staff=False).update(is_active=False)
        self.message_user(request, f"{n} viewer(s) banned; staff accounts are never banned here.", messages.WARNING)

    @admin.action(description="Unban")
    def unban(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f"{n} viewer(s) unbanned.")


# ─── DisposableDomain admin (AgentOp's) ───────────────────────────────────────


@admin.register(DisposableDomain)
class DisposableDomainAdmin(admin.ModelAdmin):
    list_display = ["domain", "source_badge", "is_active", "added_at"]
    list_filter = ["source", "is_active"]
    search_fields = ["domain"]
    list_per_page = 100
    ordering = ["domain"]
    date_hierarchy = "added_at"
    fields = ["domain", "source", "is_active"]
    actions = ["activate_domains", "deactivate_domains"]
    change_list_template = "admin/users/disposabledomain/change_list.html"

    @admin.action(description="Activate selected domains")
    def activate_domains(self, request, queryset):
        updated = queryset.update(is_active=True)
        invalidate_disposable_domains_cache()
        self.message_user(request, f"{updated} domain(s) activated.")

    @admin.action(description="Deactivate selected domains")
    def deactivate_domains(self, request, queryset):
        updated = queryset.update(is_active=False)
        invalidate_disposable_domains_cache()
        self.message_user(request, f"{updated} domain(s) deactivated.")

    @admin.display(description="Source", ordering="source")
    def source_badge(self, obj):
        colours = {DisposableDomain.SOURCE_MANUAL: "#8e44ad", DisposableDomain.SOURCE_BUNDLED: "#2980b9",
                   DisposableDomain.SOURCE_ONLINE: "#27ae60"}
        return format_html('<span style="background:{};color:#fff;padding:2px 8px;border-radius:3px;font-size:11px">'
                           "{}</span>", colours.get(obj.source, "#7f8c8d"), obj.get_source_display())

    def get_urls(self):
        custom = [
            path("sync-online/", self.admin_site.admin_view(self._view_sync_online),
                 name="users_disposabledomain_sync_online"),
            path("import-bundled/", self.admin_site.admin_view(self._view_import_bundled),
                 name="users_disposabledomain_import_bundled"),
            path("import-manual/", self.admin_site.admin_view(self._view_import_manual),
                 name="users_disposabledomain_import_manual"),
        ]
        return custom + super().get_urls()

    def _back(self):
        return HttpResponseRedirect(reverse("admin:users_disposabledomain_changelist"))

    def _view_sync_online(self, request):
        if request.method != "POST":
            return self._back()
        all_domains = set(FALLBACK_DISPOSABLE_DOMAINS)
        source_results = []
        for url in ONLINE_SOURCES:
            try:
                with urllib.request.urlopen(url, timeout=30) as resp:  # nosec B310: fixed https sources
                    fetched = _parse_domain_text(resp.read().decode("utf-8", "replace"))
                all_domains |= fetched
                source_results.append(f"{len(fetched):,} from {url.split('/')[-1]}")
            except Exception as exc:  # noqa: BLE001 (one source down should not stop the others)
                self.message_user(request, f"Warning: could not fetch {url.split('/')[-1]}: {exc}", messages.WARNING)
        added, skipped = _bulk_insert(all_domains, DisposableDomain.SOURCE_ONLINE)
        self.message_user(request, format_html("<strong>Online sync complete.</strong> {} new domain(s) added, {} "
                                               "already existed. Sources: {}", f"{added:,}", f"{skipped:,}",
                                               " | ".join(source_results)), messages.SUCCESS)
        return self._back()

    def _view_import_bundled(self, request):
        if request.method != "POST":
            return self._back()
        try:
            text = DISPOSABLE_DOMAINS_FILE.read_text(encoding="utf-8")
        except FileNotFoundError:
            self.message_user(request, "Bundled file not found.", messages.ERROR)
            return self._back()
        added, skipped = _bulk_insert(_parse_domain_text(text) | set(FALLBACK_DISPOSABLE_DOMAINS),
                                      DisposableDomain.SOURCE_BUNDLED)
        self.message_user(request, f"Bundled file import complete. {added:,} new domain(s) added, {skipped:,} "
                                   "already existed.", messages.SUCCESS)
        return self._back()

    def _view_import_manual(self, request):
        if request.method != "POST":
            return self._back()
        domains = _parse_domain_text(request.POST.get("domains_text", ""))
        if not domains:
            self.message_user(request, "No valid domains found in the pasted text.", messages.WARNING)
            return self._back()
        added, skipped = _bulk_insert(domains, DisposableDomain.SOURCE_MANUAL)
        self.message_user(request, f"Manual import complete. {added:,} new domain(s) added, {skipped:,} already "
                                   "existed.", messages.SUCCESS)
        return self._back()
