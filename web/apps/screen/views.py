"""The viewer screen behind accounts (ADR-012, ADR-013, ADR-014).

The screen's page (world/viewer) is served as it is. Its API is the guest panel's (tools/guest_panel.py), relayed:
anyone may watch (/api/status), but powers and notes need an account, and the panel hears them under the account's
name and client id. A power costs its price in credits (apps.credits), taken before the world is asked and given
back if the world refuses; every call is logged (PowerCall). Every note is kept (apps.notes), viewers may report
one, and a hidden note disappears from every screen. The pace, the note length, test mode and the blocked words are
the site rules in the admin (apps.rules): the site keeps them, from the database, and the panel defers to it.

No request waits on the island for long (ADR-014): the news is fetched once a second for everyone (island.shared),
a power is queued for the worker (tasks.call_power) and the screen asks how it went (api_power_result), and a note,
which the panel only queues, gets a few seconds.
"""
import json
import math
import mimetypes
import re
import urllib.parse
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from apps.credits import services as credits
from apps.credits.models import Power, PowerCall
from apps.notes import services as notes
from apps.notes.models import Note, Report
from apps.rules import words
from apps.rules.models import Rules
from apps.screen import island, tasks

PANEL_DOWN = island.PANEL_DOWN
STATUS_TIMEOUT = 3  # seconds: the shared news waits no longer than this for the panel
NOTE_TIMEOUT = 5  # seconds: the panel only puts a note in its queue, so it answers at once


def wait_after(last, every):
    """Seconds still to wait when the last one was at `last` and one may come every `every` seconds (0: none)."""
    if last is None:
        return 0
    return max(0, int(every - (timezone.now() - last).total_seconds() + 0.999))


def note_wait(user, every):
    """Seconds until this viewer's next note may go, one every `every` seconds (the site rules' note_every)."""
    return wait_after(user.last_note_at, every)


def take_turn(user, field, every):
    """Take the viewer's turn for a power or a note (`field`: last_power_at or last_note_at), or the seconds to wait.

    One conditional update, so two requests at once cannot both pass: the database lets one of them change the row,
    and the other then finds the turn taken. Returns (turn, 0), with `turn` for give_back(), or (None, wait)."""
    now = timezone.now()
    rows = get_user_model().objects.filter(pk=user.pk)
    before = rows.values_list(field, flat=True).first()
    free = Q(**{f"{field}__isnull": True}) | Q(**{f"{field}__lte": now - timedelta(seconds=every)})
    if rows.filter(free).update(**{field: now}):
        return (field, now, before), 0
    return None, max(1, wait_after(rows.values_list(field, flat=True).first(), every))


def give_back(user, turn):
    """Give back a turn nothing came of (too few credits, or the island refused a note), unless a later one has been
    taken since."""
    field, now, before = turn
    get_user_model().objects.filter(pk=user.pk, **{field: now}).update(**{field: before})


def account(request, free):
    """What the screen shows of the viewer's account, and where to sign in, up or out, or buy credits. `free`: test
    mode, from the site rules."""
    user = request.user
    out = {"enabled": True, "signedIn": user.is_authenticated, "signIn": reverse("account_login"),
           "signUp": reverse("account_signup"), "signOut": reverse("account_logout"), "creditsPage": reverse("credits"),
           "free": free}
    if user.is_authenticated:
        out.update(username=user.username, credits=credits.balance_of(user), notesMuted=user.notes_muted)
    return out


def body_of(request):
    try:
        body = json.loads(request.body or b"{}")
        return body if isinstance(body, dict) else {}
    except ValueError:
        return {}


def moderate(status):
    """Note pop-ups get their note's id (so viewers can report it); hidden notes vanish from pop-ups and the feed.

    The id came with the note through the panel (its pop-up's `ref`), so a report always reaches the note that was
    shown, never another account's note with the same words. A note pop-up without one has no Report button."""
    popups = status.get("popups") or []
    hidden = set(Note.objects.filter(status=Note.HIDDEN, created__gte=timezone.now() - timedelta(days=2))
                 .values_list("text", flat=True))
    refs = [p["ref"] for p in popups if p.get("kind") == "note" and type(p.get("ref")) is int]
    if refs or hidden:
        by_id = Note.objects.in_bulk(refs)
        kept = []
        for p in popups:
            if p.get("kind") != "note":
                kept.append(p)
                continue
            p = dict(p)
            note = by_id.get(p.pop("ref", None))
            if note and note.status == Note.HIDDEN or p.get("text") in hidden:
                continue
            kept.append({**p, "noteId": note.pk} if note else p)
        status["popups"] = kept
    mind = status.get("mind")
    if hidden and isinstance(mind, dict) and mind.get("feed"):
        mind["feed"] = [f if not any(h in (f.get("text") or "") for h in hidden)
                        else {**f, "text": "A note drifted down; moderators have hidden it."} for f in mind["feed"]]
    return status


def public_status():
    """The news every viewer shares: the panel's, moderated, with the admin's powers and prices (island.shared)."""
    status = island.relay("GET", "/api/status", timeout=STATUS_TIMEOUT)
    if status is PANEL_DOWN:
        status = {"world": False}
    if settings.GODLING_VIEW_URL:
        status["view"] = settings.GODLING_VIEW_URL  # the island as the public reaches it (ADR-013, ADR-014)
    rules = Rules.get()
    status["notes"] = {"limit": rules.note_limit, "every": rules.note_every,
                       "queue": (status.get("notes") or {}).get("queue", 0)}
    powers = credits.powers()
    return {**moderate(status), "powers": powers, "prices": {k: p["price"] for k, p in powers.items()},
            "free": rules.free_powers}


@require_GET
def api_status(request):
    """The shared news, with this viewer's part added: who they are, when their next note may go, and the count of
    who is watching. A signed-out viewer's poll reads the shared copy and the cache, never the database."""
    status = dict(island.shared(public_status))
    free = bool(status.pop("free", False))
    notes_now = {**(status.get("notes") or {}), "wait": 0}
    if request.user.is_authenticated:
        client = request.user.client_id
        island.seen(request.user)
        notes_now["wait"] = note_wait(request.user, notes_now.get("every") or 0)
    else:
        client = request.GET.get("client", "")
        client = client if re.fullmatch(r"[A-Za-z0-9]{6,40}", client) and not client.startswith("user") else ""
    status["notes"] = notes_now
    status["watching"] = island.watching(client, island.address(request), request.user.is_authenticated)
    return JsonResponse({**status, "account": account(request, free)})


def signed_in(request):
    if request.user.is_authenticated:
        return None
    return JsonResponse({"ok": False, "signIn": True, "text": "Sign in to call powers and send notes."}, status=401)


def spot(at):
    """Where the viewer aimed, as two finite numbers, or None (the sky chooses), as the panel checks it."""
    if not (isinstance(at, list) and len(at) == 2):
        return None, None
    try:
        x, z = float(at[0]), float(at[1])
    except (TypeError, ValueError):
        return None, None
    return (round(x, 2), round(z, 2)) if all(math.isfinite(v) and abs(v) < 2000 for v in (x, z)) else (None, None)


def power_answer(call):
    """What the screen hears of a call: still on its way (`pending`, ask again), or the world's answer."""
    if call.status in (PowerCall.QUEUED, PowerCall.SENDING):
        return {"ok": True, "pending": call.pk, "text": f"{call.power}: on its way to the island…",
                "credits": credits.balance_of(call.user)}
    return {**call.reply, "ok": call.ok, "text": call.answer or call.reply.get("text", ""),
            "credits": credits.balance_of(call.user)}


@require_POST
def api_power(request):
    refused = signed_in(request)
    if refused:
        return refused
    body = body_of(request)
    user = request.user
    power = Power.objects.filter(key=str(body.get("power", "")), enabled=True).first()
    if power is None:
        return JsonResponse({"ok": False, "text": "That power is not on offer right now."}, status=400)
    rules = Rules.get()
    turn, wait = take_turn(user, "last_power_at", rules.power_every)
    if wait:
        return JsonResponse({"ok": False, "text": "One power at a time: give the last one a moment."})
    charged = 0 if rules.free_powers else power.price
    x, z = spot(body.get("at"))
    try:
        with transaction.atomic():  # the credits go and the call is kept together, or neither
            if charged:
                credits.spend(user, charged, power.key)
            call = PowerCall.objects.create(user=user, power=power.key, price=charged, at_x=x, at_z=z,
                                            status=PowerCall.QUEUED)
    except credits.NotEnough as short:
        give_back(user, turn)
        return JsonResponse({"ok": False, "needCredits": True, "credits": short.balance,
                             "text": f"{power.label} costs {power.price} credits; you hold {short.balance}."})
    try:
        tasks.call_power.delay(call.pk)
    except Exception:  # noqa: BLE001 (the queue is down: give the call up now rather than leave it waiting)
        tasks.settle(call.pk, PANEL_DOWN, PowerCall.QUEUED, PowerCall.EXPIRED)
    call.refresh_from_db()
    return JsonResponse(power_answer(call))


@require_GET
def api_power_result(request, call):
    """How a queued power went: the screen asks every half second until the world has answered."""
    refused = signed_in(request)
    if refused:
        return refused
    found = PowerCall.objects.filter(pk=call, user=request.user).select_related("user").first()
    if found is None:
        raise Http404
    return JsonResponse(power_answer(tasks.give_up_if_stale(found)))


@require_POST
def api_note(request):
    refused = signed_in(request)
    if refused:
        return refused
    user = request.user
    paused = notes.can_send(user)
    if paused:
        return JsonResponse({"ok": False, "text": paused})
    body = body_of(request)
    rules = Rules.get()
    # Checked as it will be delivered: the panel makes the same text of it (words.plain), so ｂｌｏｃｋｅｄ is blocked.
    text = words.plain(body.get("text"))
    wait = note_wait(user, rules.note_every)
    if wait:
        return note_later(wait)
    if len(text) > rules.note_limit:
        return JsonResponse({"ok": False, "text": f"Notes are {rules.note_limit} characters at most."})
    if words.note_blocked(text):
        return JsonResponse({"ok": False, "text": "That note would not be kind to send."})
    turn, wait = take_turn(user, "last_note_at", rules.note_every)
    if wait:
        return note_later(wait)
    # Kept before it is sent, so its id travels with it (the panel's pop-up `ref`, for reports: moderate).
    note = Note.objects.create(author=user, text=text[:200])
    answer = island.relay("POST", "/api/note", {"client": user.client_id, "name": user.username, "text": text,
                                                "ref": note.pk}, timeout=NOTE_TIMEOUT)
    if answer.get("ok"):
        shown = (answer.get("note") or text)[:200]  # kept as the panel shows it
        if shown != note.text:
            Note.objects.filter(pk=note.pk).update(text=shown)
        answer["wait"] = rules.note_every
    else:
        note.delete()
        give_back(user, turn)
    return JsonResponse(answer)


def note_later(wait):
    minutes, seconds = divmod(wait, 60)
    return JsonResponse({"ok": False, "wait": wait,
                         "text": f"One note at a time: you can send another in {minutes}:{seconds:02d}."})


@require_POST
def api_report(request):
    refused = signed_in(request)
    if refused:
        return refused
    body = body_of(request)
    note = Note.objects.filter(pk=body.get("note")).first() if str(body.get("note", "")).isdigit() else None
    if note is None:
        return JsonResponse({"ok": False, "text": "That note is gone."}, status=404)
    if not island.is_watching(request.user):  # a note is reported from the screen it popped up on
        return JsonResponse({"ok": False, "text": "Reports come from the screen: watch the island to report a note."})
    reason = body.get("reason") if body.get("reason") in dict(Report.REASONS) else Report.UNKIND
    ok, text = notes.report(note, request.user, reason)
    return JsonResponse({"ok": ok, "text": text})


HIDDEN_NOTE = "A note drifted down; moderators have hidden it."
REPLAY_PARTS = ("index", "tracks", "marks", "sky")


def moderate_past(tracks):
    """A replay's tracks as viewers may see them (ADR-016): looked up now, never baked into the recording, so a note
    hidden since, or an account deleted since, is gone from the past too. Notes hidden by moderation vanish from the
    pop-ups, and lines of Godling's mind that quote one are hidden; a name with no account any more is "Someone"."""
    lead, entries, acts = tracks.get("lead") or [], tracks.get("entries") or [], tracks.get("acts") or []
    try:
        start = datetime.fromtimestamp(int(tracks["from"]) / 1000, dt_timezone.utc) - timedelta(days=2)
        end = datetime.fromtimestamp(int(tracks["to"]) / 1000, dt_timezone.utc) + timedelta(days=1)
    except (KeyError, TypeError, ValueError):
        return {"ok": False}
    hidden = set(Note.objects.filter(status=Note.HIDDEN, created__range=(start, end)).values_list("text", flat=True))
    refs = [a["ref"] for a in acts if a.get("kind") == "note" and type(a.get("ref")) is int]
    by_id = Note.objects.in_bulk(refs)
    names = set(get_user_model().objects.filter(username__in={a.get("name") for a in acts})
                .values_list("username", flat=True))
    kept = []
    for a in acts:
        a = dict(a)
        note = by_id.get(a.pop("ref", None))
        if a.get("kind") == "note" and (note and note.status == Note.HIDDEN or a.get("text") in hidden):
            continue
        if a.get("name") not in names:
            a["name"] = "Someone"
        kept.append({**a, "noteId": note.pk} if note else a)
    for e in lead + entries:
        for key in ("text", "thought", "needs"):
            if hidden and any(h in str(e.get(key) or "") for h in hidden):
                e[key] = HIDDEN_NOTE if key == "text" else "…"
    return {**tracks, "acts": kept}


@require_GET
def api_replay(request, what):
    """The island's past (ADR-016): anyone may watch it all (D1). The panel reads it from the run; the site moderates
    what it says about viewers. Chunks never pass through here: Caddy serves them from the runs volume, or the browser
    fetches them from object storage (GODLING_REPLAY_URL)."""
    if what not in REPLAY_PARTS:
        raise Http404
    query = urllib.parse.urlencode({k: request.GET[k] for k in ("from", "to") if k in request.GET})
    answer = island.relay("GET", f"/api/replay/{what}" + (f"?{query}" if query else ""))
    if answer is PANEL_DOWN:
        return JsonResponse({"ok": False, "text": "The island's past is out of reach. Try again in a moment."}, status=503)
    if what == "index" and isinstance(answer, dict):
        answer["chunks"] = answer.get("chunks_url") or settings.GODLING_REPLAY_URL  # the bucket's, or Caddy's
    elif what == "tracks" and isinstance(answer, dict):
        answer = moderate_past(answer)
    return JsonResponse(answer, safe=False)


@ensure_csrf_cookie
def screen(request, path=""):
    """The viewer's files, from world/viewer; the page itself sets the CSRF cookie its posts need."""
    viewer = settings.VIEWER_DIR.resolve()
    target = (viewer / (path or "index.html")).resolve()
    if not target.is_relative_to(viewer) or not target.is_file():
        raise Http404
    kind = "text/javascript" if target.suffix == ".js" else mimetypes.guess_type(target.name)[0]
    response = FileResponse(target.open("rb"), content_type=kind or "application/octet-stream")
    response["Cache-Control"] = "no-cache"
    return response
