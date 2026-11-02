"""The viewer screen behind accounts (ADR-012, ADR-013).

The screen's page (world/viewer) is served as it is. Its API is the guest panel's (tools/guest_panel.py), relayed:
anyone may watch (/api/status), but powers and notes need an account, and the panel hears them under the account's
name and client id. A power costs its price in credits (apps.credits), taken before the world is asked and given
back if the world refuses; every call is logged (PowerCall). Every note is kept (apps.notes), viewers may report
one, and a hidden note disappears from every screen. The pace, the note length, test mode and the blocked words are
the site rules in the admin (apps.rules): the site keeps them, from the database, and the panel defers to it.
"""
import json
import mimetypes
import re
import urllib.error
import urllib.request
from datetime import timedelta

from django.conf import settings
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

PANEL_DOWN = {"ok": False, "text": "The island is out of reach. Try again in a moment."}
NOTE_POPUP_MATCH = timedelta(minutes=15)  # a note pops up when it reaches the island, minutes after it was sent


def relay(method, path, body=None):
    """Ask the guest panel; its JSON answer, or PANEL_DOWN."""
    headers = {"Content-Type": "application/json"}
    if settings.GODLING_PANEL_KEY:
        headers["X-Godling-Key"] = settings.GODLING_PANEL_KEY
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(settings.GODLING_PANEL_URL + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        try:
            return json.loads(err.read() or b"{}") or PANEL_DOWN
        except ValueError:
            return PANEL_DOWN
    except (OSError, ValueError):
        return PANEL_DOWN


def wait_after(last, every):
    """Seconds still to wait when the last one was at `last` and one may come every `every` seconds (0: none)."""
    if last is None:
        return 0
    return max(0, int(every - (timezone.now() - last).total_seconds() + 0.999))


def note_wait(user, rules):
    last = Note.objects.filter(author=user).values_list("created", flat=True).first()
    return wait_after(last, rules.note_every)


def account(request, rules):
    """What the screen shows of the viewer's account, and where to sign in, up or out, or buy credits."""
    user = request.user
    out = {"enabled": True, "signedIn": user.is_authenticated, "signIn": reverse("account_login"),
           "signUp": reverse("account_signup"), "signOut": reverse("account_logout"), "creditsPage": reverse("credits"),
           "free": rules.free_powers}
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
    """Note pop-ups get their note's id (so viewers can report it); hidden notes vanish from pop-ups and the feed."""
    popups = status.get("popups") or []
    note_popups = [p for p in popups if p.get("kind") == "note"]
    hidden = set(Note.objects.filter(status=Note.HIDDEN, created__gte=timezone.now() - timedelta(days=2))
                 .values_list("text", flat=True))
    if note_popups:
        recent = Note.objects.filter(created__gte=timezone.now() - NOTE_POPUP_MATCH).select_related("author")
        by_sender = {(n.author.username, n.text): n for n in reversed(recent)}  # the latest such note wins
        kept = []
        for p in popups:
            note = by_sender.get((p.get("name"), p.get("text"))) if p.get("kind") == "note" else None
            if note and note.status == Note.HIDDEN or p.get("kind") == "note" and p.get("text") in hidden:
                continue
            kept.append({**p, "noteId": note.pk} if note else p)
        status["popups"] = kept
    mind = status.get("mind")
    if hidden and isinstance(mind, dict) and mind.get("feed"):
        mind["feed"] = [f if not any(h in (f.get("text") or "") for h in hidden)
                        else {**f, "text": "A note drifted down; moderators have hidden it."} for f in mind["feed"]]
    return status


@require_GET
def api_status(request):
    if request.user.is_authenticated:
        client = request.user.client_id
    else:
        client = request.GET.get("client", "")
        client = client if re.fullmatch(r"[A-Za-z0-9]{6,40}", client) and not client.startswith("user") else ""
    status = relay("GET", f"/api/status?client={client}")
    if status is PANEL_DOWN:
        status = {"world": False}
    if settings.GODLING_VIEW_URL:
        status["view"] = settings.GODLING_VIEW_URL  # the island as the public reaches it (ADR-013)
    rules = Rules.get()
    queue = (status.get("notes") or {}).get("queue", 0)
    status["notes"] = {"limit": rules.note_limit, "every": rules.note_every, "queue": queue,
                       "wait": note_wait(request.user, rules) if request.user.is_authenticated else 0}
    powers = credits.powers()
    return JsonResponse({**moderate(status), "account": account(request, rules), "powers": powers,
                         "prices": {k: p["price"] for k, p in powers.items()}})


def signed_in(request):
    if request.user.is_authenticated:
        return None
    return JsonResponse({"ok": False, "signIn": True, "text": "Sign in to call powers and send notes."}, status=401)


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
    last = PowerCall.objects.filter(user=user).values_list("created", flat=True).first()
    if wait_after(last, rules.power_every):
        return JsonResponse({"ok": False, "text": "One power at a time: give the last one a moment."})
    charged = 0 if rules.free_powers else power.price
    if charged:
        try:
            credits.spend(user, charged, power.key)
        except credits.NotEnough as short:
            return JsonResponse({"ok": False, "needCredits": True, "credits": short.balance,
                                 "text": f"{power.label} costs {power.price} credits; you hold {short.balance}."})
    at = body.get("at") if isinstance(body.get("at"), list) and len(body.get("at")) == 2 else None
    answer = relay("POST", "/api/power", {"client": user.client_id, "name": user.username, "power": power.key,
                                          "at": at})
    refunded = bool(charged and not answer.get("ok"))
    if refunded:
        credits.refund(user, charged, f"{power.key}: the world refused")
    try:
        x, z = (float(at[0]), float(at[1])) if at else (None, None)
    except (TypeError, ValueError):
        x = z = None
    PowerCall.objects.create(user=user, power=power.key, price=charged, at_x=x, at_z=z, ok=bool(answer.get("ok")),
                             refunded=refunded, answer=str(answer.get("text") or "")[:200])
    return JsonResponse({**answer, "credits": credits.balance_of(user)})


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
    text = " ".join(str(body.get("text") or "").split())
    wait = note_wait(user, rules)
    if wait:
        minutes, seconds = divmod(wait, 60)
        return JsonResponse({"ok": False, "wait": wait,
                             "text": f"One note at a time: you can send another in {minutes}:{seconds:02d}."})
    if len(text) > rules.note_limit:
        return JsonResponse({"ok": False, "text": f"Notes are {rules.note_limit} characters at most."})
    if words.note_blocked(text):
        return JsonResponse({"ok": False, "text": "That note would not be kind to send."})
    answer = relay("POST", "/api/note", {"client": user.client_id, "name": user.username, "text": body.get("text")})
    if answer.get("ok"):
        # Kept as the panel will show it: one line, quote marks made plain (tools/guest_panel.py clean_note).
        Note.objects.create(author=user, text=answer.get("note") or text.replace('"', "'")[:200])
        answer["wait"] = rules.note_every
    return JsonResponse(answer)


@require_POST
def api_report(request):
    refused = signed_in(request)
    if refused:
        return refused
    body = body_of(request)
    note = Note.objects.filter(pk=body.get("note")).first() if str(body.get("note", "")).isdigit() else None
    if note is None:
        return JsonResponse({"ok": False, "text": "That note is gone."}, status=404)
    reason = body.get("reason") if body.get("reason") in dict(Report.REASONS) else Report.UNKIND
    return JsonResponse({"ok": True, "text": notes.report(note, request.user, reason)})


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
