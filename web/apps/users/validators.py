"""Account-quality validators for signup: username and email standards.

Copied from AgentOp (C:/Work/agentop, apps/users/validators.py). Godling's changes: its own reserved names (the
brand, the guest panel's "Sky", its routes), a maximum length, and no offensive usernames, because a username is shown
to every viewer on the screen's pop-ups.

These enforce the standards we apply to *new* signups (and any future
username-change flow):

* a minimum username length plus a reserved-name blocklist (Django's
  ``UnicodeUsernameValidator`` on the model field still enforces the allowed
  character set on top of this);
* rejection of disposable / throwaway email domains.

The domain blocklist loading order (all sources unioned):
  1. ``DisposableDomain`` DB table — the authoritative source, managed via the
     admin UI.  Result is cached in Django's cache for 1 hour, invalidated
     automatically when any row is saved or deleted.
  2. Bundled ``data/disposable_email_domains.txt`` snapshot (~74k domains) —
     used as the initial seed and as a fallback when the DB table is still empty
     or unreachable.  Refresh with ``manage.py update_disposable_domains``.
  3. ``FALLBACK_DISPOSABLE_DOMAINS`` — a small hand-kept set of domains we have
     actually seen abused (e.g. nespf.com, immenseignite.info) that upstream
     lists may not catalogue yet.

Existing accounts are intentionally left untouched — these run at signup time
via the allauth account adapter (``apps.users.adapter.AccountAdapter``), not as
model-field validators, so editing a legacy account in the admin does not
retroactively fail.
"""

import logging
from pathlib import Path

from django.core.cache import cache
from django.core.exceptions import ValidationError

logger = logging.getLogger("apps.users")

MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 18  # as tools/guest_panel.py NAME_LIMIT: what a pop-up shows

# Django cache key for the frozen set of blocked domains.
DISPOSABLE_DOMAINS_CACHE_KEY = "disposable_domains_frozenset"
# How long (seconds) the DB result stays in cache between reloads.
DISPOSABLE_DOMAINS_CACHE_TTL = 3600  # 1 hour

# Bundled blocklist file (refreshed via `manage.py update_disposable_domains`).
DISPOSABLE_DOMAINS_FILE = (
    Path(__file__).resolve().parent / "data" / "disposable_email_domains.txt"
)

# Names that must not be claimable as usernames: system routes, role names,
# and anything usable to impersonate the platform.  Matched case-insensitively
# against the whole username.
RESERVED_USERNAMES = frozenset(
    {
        # roles / system
        "admin",
        "administrator",
        "root",
        "superuser",
        "sysadmin",
        "system",
        "staff",
        "moderator",
        "mod",
        "owner",
        "official",
        # contact / no-reply
        "support",
        "help",
        "helpdesk",
        "contact",
        "info",
        "noreply",
        "no-reply",
        "abuse",
        "postmaster",
        "webmaster",
        # platform / brand: Godling, and the guest panel's bodiless player
        "godling",
        "sky",
        "island",
        "world",
        "viewer",
        "screen",
        # infra / routes
        "api",
        "www",
        "mail",
        "smtp",
        "ftp",
        "ssl",
        "static",
        "media",
        "assets",
        "cdn",
        # auth / account routes
        "login",
        "logout",
        "signup",
        "signin",
        "register",
        "auth",
        "account",
        "accounts",
        "password",
        "security",
        "settings",
        "profile",
        "user",
        "users",
        "me",
        # app routes
        "docs",
        "doc",
        "about",
        "terms",
        "privacy",
        "legal",
        "billing",
        "pricing",
        "search",
        "sitemap",
        "robots",
        # placeholders
        "null",
        "undefined",
        "none",
        "anonymous",
        "test",
    }
)

# Domains we have actually seen abused in signups.  Always included regardless
# of whether the DB or bundled file covers them.
FALLBACK_DISPOSABLE_DOMAINS = frozenset(
    {
        "nespf.com",
        "immenseignite.info",
        "mailinator.com",
        "guerrillamail.com",
        "guerrillamailblock.com",
        "sharklasers.com",
        "10minutemail.com",
        "tempmail.com",
        "temp-mail.org",
        "throwawaymail.com",
        "yopmail.com",
        "getnada.com",
        "trashmail.com",
        "maildrop.cc",
        "fakeinbox.com",
        "dispostable.com",
        "mintemail.com",
        "mailnesia.com",
        "tempinbox.com",
        "spamgourmet.com",
        "mohmal.com",
        "discard.email",
        "emailondeck.com",
    }
)


def _load_bundled_domains():
    """Read the bundled blocklist file into a set (empty set if missing)."""
    try:
        with DISPOSABLE_DOMAINS_FILE.open(encoding="utf-8") as fh:
            return {
                line
                for raw in fh
                if (line := raw.strip().lower()) and not line.startswith("#")
            }
    except FileNotFoundError:
        logger.warning(
            "Bundled disposable-domains file missing at %s; run "
            "`manage.py update_disposable_domains` to generate it.",
            DISPOSABLE_DOMAINS_FILE,
        )
        return set()


def _load_db_domains():
    """Return active domains from the DisposableDomain table.

    Returns an empty set (not raising) if the table doesn't exist yet or if any
    other DB error occurs — important for management commands that run before
    migrations.
    """
    try:
        from apps.users.models import DisposableDomain  # local import avoids circular

        return set(
            DisposableDomain.objects.filter(is_active=True).values_list(
                "domain", flat=True
            )
        )
    except Exception:
        return set()


def get_disposable_domains():
    """Return the frozen set of blocked disposable email domains.

    Result is served from Django's cache (TTL = 1 h) and rebuilt from:
      DB table  →  bundled file (fallback when DB is empty)  →  FALLBACK set
    """
    cached = cache.get(DISPOSABLE_DOMAINS_CACHE_KEY)
    if cached is not None:
        return cached

    domains = set(FALLBACK_DISPOSABLE_DOMAINS)

    db_domains = _load_db_domains()
    if db_domains:
        # DB is seeded — it's the authoritative source.
        domains |= db_domains
    else:
        # DB empty (e.g. fresh deploy not yet seeded) — use the bundled file.
        domains |= _load_bundled_domains()

    result = frozenset(domains)
    cache.set(DISPOSABLE_DOMAINS_CACHE_KEY, result, DISPOSABLE_DOMAINS_CACHE_TTL)
    return result


def invalidate_disposable_domains_cache():
    """Clear the cached blocklist so the next validation reloads from DB."""
    cache.delete(DISPOSABLE_DOMAINS_CACHE_KEY)


# ─── username / email validators ─────────────────────────────────────────────


def validate_username(value):
    """Enforce the minimum length and reserved-name rules for a username."""
    cleaned = (value or "").strip()
    if len(cleaned) < MIN_USERNAME_LENGTH:
        raise ValidationError(
            "Username must be at least %(min)d characters long."
            % {"min": MIN_USERNAME_LENGTH},
            code="username_too_short",
        )
    if len(cleaned) > MAX_USERNAME_LENGTH:
        raise ValidationError(
            "Usernames are %(max)d characters at most: that is what the screen shows." % {"max": MAX_USERNAME_LENGTH},
            code="username_too_long",
        )
    from apps.rules.words import username_blocked  # the admin's blocked words: a username is shown to everyone

    if username_blocked(cleaned):
        raise ValidationError(
            "Everyone watching sees your username. Please choose another.",
            code="username_offensive",
        )
    if cleaned.lower() in RESERVED_USERNAMES:
        raise ValidationError(
            "This username is reserved and cannot be used. Please choose another.",
            code="username_reserved",
        )


def normalize_email(value):
    """Lowercase the domain part of an email address."""
    email = (value or "").strip()
    if "@" not in email:
        return email
    local, _, domain = email.rpartition("@")
    return f"{local}@{domain.lower()}"


def validate_email_not_disposable(value):
    """Reject email addresses on known disposable / throwaway domains."""
    domain = (value or "").rpartition("@")[2].lower()
    if domain and domain in get_disposable_domains():
        raise ValidationError(
            "Please use a permanent email address. Temporary or disposable "
            "email providers are not allowed.",
            code="email_disposable",
        )
