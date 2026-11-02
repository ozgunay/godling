"""The site's rules and its blocked words, in the database so staff change them in the admin without a deployment
(the user's wish, 2026-11-02: what someone running the site adjusts lives here, not in settings or code)."""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

NOTE_LIMIT_MAX = 140  # tools/guest_panel.py NOTE_LIMIT: the panel refuses anything longer whatever the site says


class Rules(models.Model):
    """One row: how the site treats viewers. Rules.get() reads it (and makes it with the defaults the first time)."""

    welcome_credits = models.PositiveIntegerField(default=20, help_text="Credits an account gets on confirming its "
                                                                        "email (the user's choice: 20).")
    free_powers = models.BooleanField(default=False, help_text="Test mode: powers cost nothing.")
    power_every = models.PositiveIntegerField(default=2, help_text="Seconds between one viewer's powers.")
    note_every = models.PositiveIntegerField(default=180, help_text="Seconds between one viewer's notes.")
    note_limit = models.PositiveIntegerField(
        default=NOTE_LIMIT_MAX, validators=[MinValueValidator(10), MaxValueValidator(NOTE_LIMIT_MAX)],
        help_text=f"Characters in a note, {NOTE_LIMIT_MAX} at most.")
    reports_to_hide = models.PositiveIntegerField(
        default=3, validators=[MinValueValidator(1)],
        help_text="Viewers' reports that hide a note from every screen and pause its sender's notes. Only reports from "
                  "accounts old enough (below) count, and accounts sharing one inbox count once.")
    report_min_age_hours = models.PositiveIntegerField(
        default=24, help_text="Hours an account must have existed before its reports count toward hiding a note "
                              "(fresh accounts are cheap). Moderators still see every report.")
    reports_per_hour = models.PositiveIntegerField(
        default=10, validators=[MinValueValidator(1)], help_text="Reports one viewer may send in an hour.")

    class Meta:
        verbose_name = verbose_name_plural = "site rules"

    def __str__(self):
        return "Site rules"

    def save(self, *args, **kwargs):
        self.pk = 1  # there is only ever one
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        return cls.objects.get_or_create(pk=1)[0]


class BlockedWord(models.Model):
    """A word or phrase refused in notes, in usernames, or both. Matched without regard to case: a note when one of its
    words starts with it, a username when it holds it anywhere (usernames have no spaces to tell words apart)."""

    NOTES, USERNAMES, BOTH = "notes", "usernames", "both"

    word = models.CharField(max_length=60, unique=True)
    applies_to = models.CharField(max_length=10, default=BOTH,
                                  choices=[(NOTES, "Notes"), (USERNAMES, "Usernames"), (BOTH, "Both")])
    active = models.BooleanField(default=True)
    added = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["word"]

    def __str__(self):
        return self.word

    def save(self, *args, **kwargs):
        self.word = " ".join(self.word.lower().split())
        super().save(*args, **kwargs)
