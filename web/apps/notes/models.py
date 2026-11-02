"""Notes viewers sent Godling, and viewers' reports on them (ADR-013; the user's choice: report after delivery).

A note goes to the island at once. Any signed-in viewer may report one they saw; when enough different viewers have
(the site rules' reports_to_hide), the note is hidden from every screen and its author's notes pause until a
moderator looks (the admin: restore or hide notes, mute, unmute or ban accounts).
"""
from django.conf import settings
from django.db import models


class Note(models.Model):
    SENT, HIDDEN = "sent", "hidden"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notes")
    text = models.CharField(max_length=200)
    status = models.CharField(max_length=8, default=SENT, choices=[(SENT, "Sent"), (HIDDEN, "Hidden")])
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.author}: {self.text[:60]}"


class Report(models.Model):
    UNKIND, SPAM, PERSONAL, OTHER = "unkind", "spam", "personal", "other"
    REASONS = [(UNKIND, "Unkind or hateful"), (SPAM, "Spam or advertising"), (PERSONAL, "Personal information"),
               (OTHER, "Something else")]

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made")
    reason = models.CharField(max_length=10, choices=REASONS, default=UNKIND)
    created = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False, help_text="A moderator has looked at it.")

    class Meta:
        ordering = ["-created"]
        constraints = [models.UniqueConstraint(fields=["note", "reporter"], name="one_report_per_viewer")]

    def __str__(self):
        return f"{self.reporter} on #{self.note_id}: {self.reason}"
