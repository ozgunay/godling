"""The bottle's one call: a signed-in viewer's bug report, question or idea, kept for staff (apps.feedback.models).

Sending needs an account, as notes and powers do (the user's choice, 2026-11-03): staff can write back, and spam stays
out. A viewer sends at most the site rules' feedback_per_hour in an hour. The screen's facts come along only when the
viewer leaves them attached, and only in the shapes the screen sends them (screen_facts). Whatever else arrives is
refused or dropped, never an error. The email to staff goes from its own worker, so neither the request nor the powers'
worker ever waits on a mail server (tasks.tell_staff).
"""
import logging
import math
import re
import unicodedata
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.feedback import tasks
from apps.feedback.models import TEXT_LIMIT, Feedback
from apps.rules.models import Rules
from apps.screen.views import body_of

log = logging.getLogger("godling.feedback")

TEXT_MIN = 3  # characters: "ok" says nothing a maker can act on
HOUR = timedelta(hours=1)
STREAMS = ("connecting", "reconnecting", "paused", "live", "offline", "restarting")  # viewer.js liveWord, lower case
WORD = re.compile(r"[A-Za-z][A-Za-z0-9 .]{0,29}")  # a browser's or a system's name and version: "Chrome 142"
SIZE = re.compile(r"[0-9]{2,5}x[0-9]{2,5}")
# Characters that hide or reorder what is written: zero widths and the bidi embeddings, overrides and isolates.
# Joiners stay (U+200C, U+200D, emoji tags): they make one emoji, or one word, of the parts around them.
HIDDEN = {chr(c) for c in (0x200B, 0x2060, 0xFEFF, *range(0x202A, 0x202F), *range(0x2066, 0x206A))}


def plain_text(text):
    """The message as staff will read it: line and paragraph separators made plain line breaks; control characters,
    lone surrogates (which no database can store) and the HIDDEN characters dropped. Everything else is kept as it was
    written."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", "\n").replace(" ", "\n")
    return "".join(c for c in text if c in "\n\t" or c not in HIDDEN and unicodedata.category(c) not in ("Cc", "Cs")
                   ).strip()


def number(v, low, high):
    """A JSON number from low to high. Compared before anything converts it, so a 400-digit integer, infinity and
    NaN are simply out of range."""
    return type(v) in (int, float) and low <= v <= high


def one_of(*choices):
    return lambda v: v if isinstance(v, str) and v in choices else None


# What the screen may attach (world/viewer/viewer.js screenFacts), each in the one shape it sends it.
FACTS = {
    "view": one_of("live", "replay"),
    "moment": lambda v: int(v) if number(v, 1.5e12, 4.2e12) else None,  # the replay's playhead, UTC ms
    "day": lambda v: v if type(v) is int and 0 < v < 1_000_000 else None,
    "minute": lambda v: v if type(v) is int and 0 <= v < 1440 else None,  # of the island's day, as its clock shows it
    "camera": one_of("follow", "free"),
    "stream": one_of(*STREAMS),
    "size": lambda v: v if isinstance(v, str) and SIZE.fullmatch(v) else None,
    "pixels": lambda v: round(v, 2) if number(v, 0.25, 8) else None,
    "touch": lambda v: True if v is True else None,
    "browser": lambda v: v if isinstance(v, str) and WORD.fullmatch(v) else None,
    "system": lambda v: v if isinstance(v, str) and WORD.fullmatch(v) else None,
}


def screen_facts(raw):
    """The facts the viewer saw listed under "Attach what my screen shows", checked one by one. Whatever else arrives
    is dropped, not stored: this field is the viewer's to fill, and staff read it in the admin."""
    if not isinstance(raw, dict):
        return {}
    facts = {key: check(raw.get(key)) for key, check in FACTS.items()}
    return {key: value for key, value in facts.items() if value is not None}


def refuse(text, status=400, **more):
    return JsonResponse({"ok": False, "text": text, **more}, status=status)


@require_POST
def api_feedback(request):
    if not request.user.is_authenticated:
        return refuse("Sign in to send the makers a message.", 401, signIn=True)
    body = body_of(request)
    kind = body.get("kind")
    if not isinstance(kind, str) or kind not in dict(Feedback.KINDS):
        return refuse("Say what it is: a bug, a question or an idea.")
    text = plain_text(body["text"]) if isinstance(body.get("text"), str) else ""
    if len(text) < TEXT_MIN:
        return refuse("Write a few words first.")
    if len(text) > TEXT_LIMIT:
        return refuse(f"Messages are {TEXT_LIMIT:,} characters at most.")
    rules = Rules.get()
    every = rules.feedback_per_hour
    with transaction.atomic():
        # One viewer's sends are counted one at a time, so two at once cannot both slip under the hour's limit.
        get_user_model().objects.select_for_update().filter(pk=request.user.pk).first()
        now = timezone.now()
        sent = list(Feedback.objects.filter(author=request.user, created__gt=now - HOUR)
                    .order_by("created").values_list("created", flat=True))
        if len(sent) >= every:
            wait = max(1, math.ceil((sent[-every] + HOUR - now).total_seconds()))
            minutes, seconds = divmod(wait, 60)
            return refuse(f"That is {len(sent)} messages this hour. The next can go in {minutes}:{seconds:02d}.", 429,
                          wait=wait)
        feedback = Feedback.objects.create(author=request.user, kind=kind, text=text,
                                           screen=screen_facts(body.get("screen")))
    if rules.feedback_email:  # no inbox named: the admin's list is enough, and nothing is queued
        admin_url = request.build_absolute_uri(reverse("admin:feedback_feedback_change", args=[feedback.pk]))
        try:
            tasks.tell_staff.delay(feedback.pk, admin_url)
        except Exception:  # noqa: BLE001 (the message is kept either way; the email is a courtesy, never why a send fails)
            log.exception("feedback %s: could not email staff", feedback.pk)
    return JsonResponse({"ok": True, "text": "Corked and sent."})
