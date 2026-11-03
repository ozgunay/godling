"""Each viewer's message is emailed to the inbox the site rules name, by a worker of its own.

The task goes to the "mail" queue (settings CELERY_TASK_ROUTES), which only the `mailer` worker takes (deploy/). The
powers' worker never sees it, so a slow or silent mail server can hold back other emails, but never a viewer's power.
The time limits end a send that hangs; the message itself is kept in the admin either way.
"""
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.feedback.models import Feedback
from apps.rules.models import Rules

MAIL_QUEUE = "mail"


@shared_task(ignore_result=True, soft_time_limit=60, time_limit=90)
def tell_staff(feedback_id, admin_url=""):
    to = Rules.get().feedback_email
    if not to:  # the inbox was emptied since the message was queued
        return
    feedback = Feedback.objects.select_related("author").filter(pk=feedback_id).first()
    if feedback is None:
        return
    context = {"feedback": feedback, "who": feedback.who, "email": feedback.author.email if feedback.author else "",
               "facts": feedback.facts(), "admin_url": admin_url}
    send_mail(f"[Godling beta] {feedback.get_kind_display()} from {feedback.who}",
              render_to_string("feedback/email.txt", context), None, [to])
