"""Staff open the admin only with two-factor sign-in, in this very session (allauth.mfa; ADR-014). The admin holds
prices, credits, moderation and every viewer's account, so a password alone, guessed or phished, must not be enough.

What counts is how this session signed in (allauth's authentication records), not whether the account has an
authenticator: a session that signed in with a password alone does not become an admin session when the account sets
up an authenticator somewhere else. A staff member without an authenticator is sent to set one up; one with an
authenticator whose session has not used it lately is asked for a code (allauth's reauthentication).

Signing in to the admin goes through the site's own sign-in (godling_web/urls.py, allauth's secure_admin_login),
which asks for the code. GODLING_ADMIN_TWO_FACTOR=0 turns the rule off (development only).
"""
import inspect
import time
from urllib.parse import urlencode

from allauth.account.authentication import get_authentication_records
from allauth.mfa.utils import is_mfa_enabled
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

ADMIN = "/admin/"
TOTP = ["totp"]  # recovery codes alone do not count: they are the way back in when the phone is lost
FRESH = 12 * 3600  # seconds a code entered in this session holds for the admin
# allauth 65.21 (Python 3.11 on) ties the records to the user who made them, and gives none unless asked for that
# user's; the releases before it (the last for Python 3.10) keep them per session and take no user.
RECORDS_TAKE_USER = "user" in inspect.signature(get_authentication_records).parameters


def code_entered_lately(request):
    """Whether this session gave a second factor (a code, or a recovery code) in the last FRESH seconds."""
    now = time.time()
    records = (get_authentication_records(request, request.user) if RECORDS_TAKE_USER
               else get_authentication_records(request))
    return any(r.get("method") == "mfa" and now - float(r.get("at") or 0) < FRESH for r in records)


class AdminNeedsTwoFactor:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (settings.GODLING_ADMIN_TWO_FACTOR and request.path.startswith(ADMIN) and user is not None
                and user.is_authenticated and user.is_staff):
            if not is_mfa_enabled(user, types=TOTP):
                messages.warning(request, "Set up two-factor sign-in first: the admin opens only with it.")
                return redirect("mfa_activate_totp")
            if not code_entered_lately(request):
                return redirect(f"{reverse('mfa_reauthenticate')}?{urlencode({'next': request.get_full_path()})}")
        return self.get_response(request)
