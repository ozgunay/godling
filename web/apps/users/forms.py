"""The sign-up form: allauth's, with Cloudflare Turnstile's check when the site has its keys (apps.users.turnstile)."""
from allauth.account.forms import SignupForm as AllauthSignupForm

from apps.users import turnstile


class SignupForm(AllauthSignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if turnstile.enabled():
            self.fields["person"] = turnstile.TurnstileField()
