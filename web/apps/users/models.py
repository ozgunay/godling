"""Viewer accounts. Copied from AgentOp's users app (C:/Work/agentop, apps/users) and trimmed to what Godling needs:
the user model and the disposable-domain blocklist. AgentOp's profiles, followers and signup attribution stay there.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class DisposableDomain(models.Model):
    """A single disposable / throwaway email domain that is blocked at signup.

    The authoritative list lives here in the DB so it can be managed through
    the Django admin without a deployment.  The bundled text file
    (``apps/users/data/disposable_email_domains.txt``) remains as the initial
    seed and offline fallback.
    """

    SOURCE_MANUAL = "manual"
    SOURCE_BUNDLED = "bundled"
    SOURCE_ONLINE = "online"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Added manually"),
        (SOURCE_BUNDLED, "Imported from bundled file"),
        (SOURCE_ONLINE, "Synced from online sources"),
    ]

    domain = models.CharField(max_length=253, unique=True, db_index=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    added_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["domain"]
        verbose_name = "Disposable Domain"
        verbose_name_plural = "Disposable Domains"

    def __str__(self):
        return self.domain

    def save(self, *args, **kwargs):
        self.domain = self.domain.lower().strip()
        super().save(*args, **kwargs)


class User(AbstractUser):
    """A viewer's account. Signs in by email; the username is what other viewers see on the screen's pop-ups."""

    email = models.EmailField(unique=True)
    # Moderation (apps.notes): a muted account still watches and calls powers, but sends no notes.
    notes_muted = models.BooleanField(default=False)
    notes_muted_at = models.DateTimeField(null=True, blank=True)
    notes_muted_reason = models.CharField(max_length=120, blank=True)
    # The viewer's pace (apps.screen): when they last took a turn for a power or a note. Taken in one conditional
    # update before the island is asked, so two requests at once cannot both pass.
    last_power_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_note_at = models.DateTimeField(null=True, blank=True, editable=False)
    # The inbox behind the email (validators.canonical_email): accounts made from one inbox (me+1@, me+2@…) share one
    # welcome gift and count once in reports. Not unique: making another account is allowed, farming it is not.
    email_key = models.CharField(max_length=254, blank=True, db_index=True, editable=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        from apps.users.validators import canonical_email

        self.email_key = canonical_email(self.email)
        if kwargs.get("update_fields") is not None and "email" in kwargs["update_fields"]:
            kwargs["update_fields"] = {*kwargs["update_fields"], "email_key"}
        super().save(*args, **kwargs)

    @property
    def client_id(self):
        """How the guest panel knows this account: its per-viewer limits on powers and notes hold per account."""
        return f"user{self.pk:06d}"
