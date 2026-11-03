"""Cloudflare Turnstile on sign-up (ADR-016): a check that a person, not a script, is signing up, with no puzzle to
solve. On only when the site has both keys (GODLING_TURNSTILE_SITE_KEY, GODLING_TURNSTILE_SECRET_KEY); Cloudflare
answers whether the browser passed. Fake accounts are what spam notes and farm welcome credits, so this sits at the
door they come through."""
import json
import urllib.parse
import urllib.request

from django import forms
from django.conf import settings
from django.utils.html import format_html

SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js"
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
RESPONSE_FIELD = "cf-turnstile-response"  # where Cloudflare's widget puts its token in the form


def enabled():
    return bool(settings.GODLING_TURNSTILE_SITE_KEY and settings.GODLING_TURNSTILE_SECRET_KEY)


def verify(token, remote_ip=None):
    """Whether Cloudflare says `token` is a fresh pass for this site. No answer counts as no pass."""
    fields = {"secret": settings.GODLING_TURNSTILE_SECRET_KEY, "response": token}
    if remote_ip:
        fields["remoteip"] = remote_ip
    request = urllib.request.Request(VERIFY_URL, data=urllib.parse.urlencode(fields).encode(), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read()).get("success") is True
    except (OSError, ValueError):
        return False


class TurnstileWidget(forms.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        return format_html('<div class="cf-turnstile" data-sitekey="{}" data-action="signup"></div>'
                           '<script src="{}" async defer></script>', settings.GODLING_TURNSTILE_SITE_KEY, SCRIPT_URL)

    def value_from_datadict(self, data, files, name):
        return data.get(RESPONSE_FIELD, "")

    def value_omitted_from_data(self, data, files, name):
        return False


class TurnstileField(forms.Field):
    widget = TurnstileWidget
    default_error_messages = {"robot": "Please let the check below confirm you are a person, then sign up again."}

    def __init__(self, remote_ip=None, **kwargs):
        super().__init__(label="", required=False, **kwargs)
        self.remote_ip = remote_ip

    def validate(self, value):
        if not value or not verify(value, self.remote_ip):
            raise forms.ValidationError(self.error_messages["robot"], code="robot")
