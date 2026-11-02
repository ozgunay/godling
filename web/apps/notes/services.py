from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.notes.models import Note, Report
from apps.rules.models import Rules

# A note pops up for 14 s, lies on the island 4 minutes and stays in the feed a while: after this it has left every
# screen, and a report on it could only come from someone hunting through note numbers.
REPORT_WINDOW = timedelta(minutes=30)


def can_send(user):
    """None, or why this account's notes are paused."""
    if user.notes_muted:
        return "Your notes are paused while a moderator looks at a report. You can still watch and call powers."
    return None


def counted_reports(note, rules):
    """The reports that count toward hiding a note: from accounts at least report_min_age_hours old, one per inbox
    (users.User.email_key), so a handful of fresh accounts made from one address cannot silence anyone."""
    old_enough = timezone.now() - timedelta(hours=rules.report_min_age_hours)
    return (note.reports.filter(reporter__date_joined__lte=old_enough)
            .values("reporter__email_key").distinct().count())


@transaction.atomic
def report(note, reporter, reason):
    """A viewer reports a note; enough reports hide it and pause its author's notes. Returns (counted, what to tell
    them): `counted` is False when the report was refused."""
    if note.author_id == reporter.pk:
        return False, "That is your own note."
    now = timezone.now()
    if note.created < now - REPORT_WINDOW:
        return False, "That note has left the screen; a moderator can still look at it."
    rules = Rules.get()
    if Report.objects.filter(reporter=reporter, created__gte=now - timedelta(hours=1)).count() >= rules.reports_per_hour:
        return False, "You have sent a lot of reports this hour. Moderators will look at them; try again later."
    try:
        with transaction.atomic():
            Report.objects.create(note=note, reporter=reporter, reason=reason)
    except IntegrityError:
        return False, "You have reported that note already. Thank you."
    note = Note.objects.select_for_update().get(pk=note.pk)
    if note.status == Note.SENT and counted_reports(note, rules) >= rules.reports_to_hide:
        note.status = Note.HIDDEN
        note.save(update_fields=["status"])
        author = note.author
        if not author.notes_muted:
            author.notes_muted, author.notes_muted_at = True, now
            author.notes_muted_reason = f"{note.reports.count()} reports on note #{note.pk}"
            author.save(update_fields=["notes_muted", "notes_muted_at", "notes_muted_reason"])
    return True, "Reported. Thank you: a moderator will look at it."
