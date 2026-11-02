"""Checking notes and usernames against the blocked words (apps.rules.models.BlockedWord).

The list is read once and cached until the admin changes it (as AgentOp caches its disposable domains). If the table
is empty or cannot be read, the words it was seeded with still hold: the list never silently becomes nothing. The
guest panel keeps its own short list too (tools/guest_panel.py BLOCKED), as a floor for when it runs on its own.
"""
import re

from django.core.cache import cache

CACHE_KEY = "godling_blocked_words"
CACHE_SECONDS = 3600
# What the table was seeded with (migrations 0002): the panel's note words and the username words that were in code.
SEED = {
    "fuck": "both", "shit": "both", "cunt": "both", "bitch": "both", "whore": "both", "nigg": "both",
    "retard": "both", "fag": "notes", "rape": "notes", "kill yourself": "notes", "nazi": "usernames",
    "hitler": "usernames",
}


def _load():
    try:
        from apps.rules.models import BlockedWord

        rows = list(BlockedWord.objects.filter(active=True).values_list("word", "applies_to"))
        if rows or BlockedWord.objects.exists():
            return rows
    except Exception:  # noqa: BLE001 (before migrations, or the database away: the seed still holds)
        pass
    return list(SEED.items())


def words(scope):
    """The active words for "notes" or "usernames"."""
    rows = cache.get(CACHE_KEY)
    if rows is None:
        rows = _load()
        cache.set(CACHE_KEY, rows, CACHE_SECONDS)
    return [w for w, applies in rows if applies in (scope, "both")]


def forget():
    cache.delete(CACHE_KEY)


def note_blocked(text):
    """Whether a note holds a blocked word (one of its words starts with it, or the phrase is in it)."""
    return any(re.search(r"(?<!\w)" + re.escape(w), text or "", re.IGNORECASE) for w in words("notes"))


def username_blocked(name):
    name = (name or "").lower()
    return any(w.replace(" ", "") in name for w in words("usernames"))
