"""Checking notes and usernames against the blocked words (apps.rules.models.BlockedWord).

The list is read once and cached until the admin changes it (as AgentOp caches its disposable domains). If the table
is empty or cannot be read, the words it was seeded with still hold: the list never silently becomes nothing. The
guest panel keeps its own short list too (tools/guest_panel.py BLOCKED), as a floor for when it runs on its own.
"""
import re
import unicodedata

from django.core.cache import cache

QUOTES = re.compile("[“”„«»‹›\"]")  # as tools/guest_panel.py QUOTES
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


def plain(text):
    """A note as the guest panel will deliver it (tools/guest_panel.py clean_note): lookalike letters made plain
    (NFKC: ｇｏｌｄ is gold), hidden characters dropped, one line, quote marks made plain. The site checks and sends
    this text, so what passes the blocked words is what reaches the island."""
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = "".join(" " if unicodedata.category(c) in ("Cc", "Zl", "Zp") else c for c in text
                   if unicodedata.category(c) != "Cf")
    return QUOTES.sub("'", " ".join(text.split()))


def note_blocked(text):
    """Whether a note holds a blocked word (one of its words starts with it, or the phrase is in it)."""
    text = plain(text)
    return any(re.search(r"(?<!\w)" + re.escape(w), text, re.IGNORECASE) for w in words("notes"))


def username_blocked(name):
    name = plain(name).casefold()
    return any(w.casefold().replace(" ", "") in name for w in words("usernames"))
