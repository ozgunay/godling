from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.notes.models import Note, Report
from apps.rules.models import Rules


def can_send(user):
    """None, or why this account's notes are paused."""
    if user.notes_muted:
        return "Your notes are paused while a moderator looks at a report. You can still watch and call powers."
    return None


@transaction.atomic
def report(note, reporter, reason):
    """A viewer reports a note; enough reports hide it and pause its author's notes. Returns what to tell them."""
    if note.author_id == reporter.pk:
        return "That is your own note."
    try:
        with transaction.atomic():
            Report.objects.create(note=note, reporter=reporter, reason=reason)
    except IntegrityError:
        return "You have reported that note already. Thank you."
    if note.status == Note.SENT and note.reports.count() >= Rules.get().reports_to_hide:
        note.status = Note.HIDDEN
        note.save(update_fields=["status"])
        author = note.author
        if not author.notes_muted:
            author.notes_muted, author.notes_muted_at = True, timezone.now()
            author.notes_muted_reason = f"{note.reports.count()} reports on note #{note.pk}"
            author.save(update_fields=["notes_muted", "notes_muted_at", "notes_muted_reason"])
    return "Reported. Thank you: a moderator will look at it."
