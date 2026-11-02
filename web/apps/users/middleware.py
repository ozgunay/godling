"""Staff open the admin only with two-factor sign-in set up (allauth.mfa; ADR-014). The admin holds prices, credits,
moderation and every viewer's account, so a password alone, guessed or phished, must not be enough to reach it.

Signing in to the admin goes through the site's own sign-in (godling_web/urls.py, allauth's secure_admin_login),
which asks for the authenticator code. A staff member without an authenticator yet is sent to set one up first.
GODLING_ADMIN_TWO_FACTOR=0 turns the rule off (development only).
"""
from allauth.mfa.utils import is_mfa_enabled
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

ADMIN = "/admin/"
TOTP = ["totp"]  # recovery codes alone do not count: they are the way back in when the phone is lost


class AdminNeedsTwoFactor:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (settings.GODLING_ADMIN_TWO_FACTOR and request.path.startswith(ADMIN) and user is not None
                and user.is_authenticated and user.is_staff and not is_mfa_enabled(user, types=TOTP)):
            messages.warning(request, "Set up two-factor sign-in first: the admin opens only with it.")
            return redirect("mfa_activate_totp")
        return self.get_response(request)
