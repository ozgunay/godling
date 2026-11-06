"""Powers go to the island from the Celery worker, not from the viewer's request (ADR-014).

The guest panel calls the sky one power at a time and waits for the world's answer (up to 1.5 s, longer when powers
queue), so a request that waited for it held a web thread meanwhile: a few viewers calling at once could hold every
thread, sign-in and Stripe's webhook included. Now the request queues the call (its price already taken) and returns;
the worker, one call at a time as the island takes them, relays it and settles it; the screen asks how it went
(views.api_power_result).
"""
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.credits import services as credits
from apps.credits.models import PowerCall
from apps.screen import island

# A queued call the worker has not taken in this long is given up: its credits come back and the screen says so. The
# worker skips a call that waited this long, so a late worker never calls a power its viewer was refunded for. Long
# enough for a burst: the island takes about one power a second, so a hundred queued at once still go through.
STALE = timedelta(minutes=3)
# A call the worker took to the island but never settled (the worker died with it): given up too, credits back.
LOST = timedelta(minutes=4)
REPLY_KEYS = ("ok", "text", "id", "kind", "name", "power", "time", "wait")


NO_ANSWER = {"ok": False, "text": "The island did not answer in time; your credits are back."}


@shared_task(ignore_result=True)
def call_power(call_id):
    """Take a queued power to the island, once, and settle it with the world's answer."""
    claimed = PowerCall.objects.filter(pk=call_id, status=PowerCall.QUEUED,
                                       created__gt=timezone.now() - STALE).update(status=PowerCall.SENDING)
    if not claimed:  # settled already, or waited too long: then it is given up here, its credits back
        late = PowerCall.objects.filter(pk=call_id).first()
        if late:
            give_up_if_stale(late)
        return
    call = PowerCall.objects.select_related("user").get(pk=call_id)
    at = [call.at_x, call.at_z] if call.at_x is not None and call.at_z is not None else None
    answer = island.relay("POST", "/api/power", {"client": call.user.client_id, "name": call.user.username,
                                                 "power": call.power, "at": at,
                                                 **({"spots": call.spots} if call.spots else {})})
    settle(call_id, answer, PowerCall.SENDING, PowerCall.DONE)


@transaction.atomic
def settle(call_id, answer, was, now):
    """Close a call that is still `was` with the world's answer: refunded unless the world did it. Returns the call."""
    call = PowerCall.objects.select_for_update().select_related("user").get(pk=call_id)
    if call.status != was:
        return call  # someone settled it meanwhile (the worker, or a viewer's look that gave it up)
    call.ok = bool(answer.get("ok"))
    call.refunded = bool(call.price and not call.ok)
    if call.refunded:
        credits.refund(call.user, call.price, f"{call.power}: " + ("the world refused" if now == PowerCall.DONE
                                                                   else "the island did not answer"))
    call.status = now
    call.answer = str(answer.get("text") or "")[:200]
    call.reply = {k: answer[k] for k in REPLY_KEYS if k in answer}
    call.save(update_fields=["ok", "refunded", "status", "answer", "reply"])
    return call


def give_up_if_stale(call):
    """A call the island never answered is given up (credits back), so a viewer is never left waiting forever."""
    late = timezone.now() - call.created
    if call.status == PowerCall.QUEUED and late > STALE or call.status == PowerCall.SENDING and late > LOST:
        return settle(call.pk, NO_ANSWER, call.status, PowerCall.EXPIRED)
    return call


@shared_task(ignore_result=True)
def expire_stale_powers():
    """Every minute (Celery beat, settings.CELERY_BEAT_SCHEDULE): give up the calls nobody will take, credits back,
    whether or not their viewer is still looking: the page closed, the answer lost, or the queue's message gone with
    a restart of Redis."""
    now = timezone.now()
    stale = (PowerCall.objects.filter(status=PowerCall.QUEUED, created__lte=now - STALE)
             | PowerCall.objects.filter(status=PowerCall.SENDING, created__lte=now - LOST))
    for call_id, status in stale.values_list("pk", "status")[:500]:
        settle(call_id, NO_ANSWER, status, PowerCall.EXPIRED)
