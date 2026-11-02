"""The island's news for every viewer at once, and who is watching (ADR-014).

Every page asks for news every 1.5 s. The guest panel is not asked each time: the first request to find the shared
copy more than a second old fetches a fresh one (holding a short lock in the cache, so only one does), and every other
request reads the copy. However many watch, the panel hears from the site about once a second.

Who is watching is counted here, across every web worker, in windows of WINDOW seconds: each page counts once a
window. A signed-in viewer always counts (an account is one viewer). Pages without an account count up to
PER_ADDRESS from one address, enough for a phone network's shared address, but not for a script inventing client ids.
"""
import http.client
import json
import time
import urllib.error
import urllib.request

from allauth.core.internal.httpkit import get_client_ip
from django.conf import settings
from django.core.cache import cache

STATUS_KEY, STATUS_LOCK = "island:status", "island:status:lock"
FRESH = 1.0  # seconds a shared copy of the news is good for
COLD_WAIT = 3.0  # seconds a request waits for the first copy while another request fetches it
WINDOW = 20  # seconds: a page that has not asked for news in this long has left (as the panel's WATCHING_FOR)
# Pages without an account counted from one address in a window. Phone networks put many people behind one address
# (carrier-grade NAT), so this is generous; a script making up client ids still stops here.
PER_ADDRESS = 64
PANEL_DOWN = {"ok": False, "text": "The island is out of reach. Try again in a moment."}


def relay(method, path, body=None, timeout=15):
    """Ask the guest panel; its JSON answer, or PANEL_DOWN."""
    headers = {"Content-Type": "application/json"}
    if settings.GODLING_PANEL_KEY:
        headers["X-Godling-Key"] = settings.GODLING_PANEL_KEY
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(settings.GODLING_PANEL_URL + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        try:
            return json.loads(err.read() or b"{}") or PANEL_DOWN
        except ValueError:
            return PANEL_DOWN
    except (OSError, ValueError, http.client.HTTPException):  # unreachable, garbled, or cut off mid-answer
        return PANEL_DOWN


def shared(build):
    """The news as `build()` makes it, at most FRESH seconds old, made by one request at a time for everyone."""
    held = cache.get(STATUS_KEY)
    if held and time.time() - held["at"] < FRESH:
        return held["status"]
    if cache.add(STATUS_LOCK, 1, timeout=10):  # this request fetches; the others keep the copy they have
        try:
            status = build()
            cache.set(STATUS_KEY, {"at": time.time(), "status": status}, timeout=60)
            return status
        finally:
            cache.delete(STATUS_LOCK)
    if held:
        return held["status"]
    deadline = time.time() + COLD_WAIT  # no copy yet (a cold start): wait for the one being fetched
    while time.time() < deadline:
        time.sleep(0.1)
        held = cache.get(STATUS_KEY)
        if held:
            return held["status"]
    return {"world": False}


def address(request):
    """The viewer's address: the one Caddy saw, read as allauth reads it for its rate limits."""
    return get_client_ip(request) or ""


def _count(key):
    cache.add(key, 0, WINDOW * 3)
    try:
        return cache.incr(key)
    except ValueError:  # expired between the two calls
        cache.set(key, 1, WINDOW * 3)
        return 1


def watching(client, where, signed_in=False):
    """Count this page (`client`, from `where`) as watching, and return how many watch."""
    window = int(time.time() // WINDOW)
    if client and cache.add(f"watch:{window}:page:{client}", 1, WINDOW * 3):  # first time this window
        if signed_in or _count(f"watch:{window}:from:{where}") <= PER_ADDRESS:
            _count(f"watch:{window}:count")
    return max(cache.get(f"watch:{window}:count", 0), cache.get(f"watch:{window - 1}:count", 0))


def seen(user):
    """A signed-in viewer's page asked for news: they are watching now (reports come only from viewers watching)."""
    cache.set(f"watch:user:{user.pk}", time.time(), WINDOW * 3)


def is_watching(user):
    return cache.get(f"watch:user:{user.pk}") is not None
