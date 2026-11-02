"""Custom django-allauth account adapter (copied from AgentOp's apps/users/adapter.py).

It re-applies the account-quality rules on top of allauth: the reserved-username blocklist and length limits, and
disposable-email rejection (``apps.users.validators``). AgentOp also routes account emails through its Celery queue;
Godling sends them directly, through Django's email backend (the console in development).
"""

from allauth.account.adapter import DefaultAccountAdapter
from django.core.exceptions import ValidationError as DjangoValidationError
from django.forms import ValidationError as FormValidationError

from apps.users.validators import normalize_email, validate_email_not_disposable, validate_username


class AccountAdapter(DefaultAccountAdapter):
    def clean_username(self, username, shallow=False):
        """Enforce the length limits and the reserved-name blocklist on top of allauth."""
        username = super().clean_username(username, shallow=shallow)
        try:
            validate_username(username)
        except DjangoValidationError as exc:
            raise FormValidationError(exc.messages[0]) from exc
        return username

    def clean_email(self, email):
        """Normalize the domain and reject disposable email providers."""
        email = super().clean_email(email)
        email = normalize_email(email)
        try:
            validate_email_not_disposable(email)
        except DjangoValidationError as exc:
            raise FormValidationError(exc.messages[0]) from exc
        return email
