"""Each viewer's message is emailed to the inbox the site rules name, from the Celery worker, so a slow mail server
never holds the viewer's request (as powers go to the island from it: ADR-014). No inbox named: the admin's list is
enough, and nothing is sent."""
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.feedback.models import Feedback
from apps.rules.models import Rules


@shared_task(ignore_result=True)
def tell_staff(feedback_id, admin_url=""):
    to = Rules.get().feedback_email
    feedback = Feedback.objects.select_related("author").filter(pk=feedback_id).first()
    if not to or feedback is None:
        return
    who = feedback.author.username if feedback.author else "a deleted account"
    context = {"feedback": feedback, "who": who, "email": feedback.author.email if feedback.author else "",
               "facts": feedback.facts(), "admin_url": admin_url}
    send_mail(f"[Godling beta] {feedback.get_kind_display()} from {who}",
              render_to_string("feedback/email.txt", context), None, [to])
