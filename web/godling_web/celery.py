"""The site's Celery app (as AgentOp's config/celery.py): the worker relays powers to the island (apps.screen.tasks).

    celery -A godling_web worker --concurrency 1     (deploy/: the `worker` service)

One at a time is the island's own pace: the guest panel calls the sky one power after another.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "godling_web.settings")

app = Celery("godling_web")
app.config_from_object("django.conf:settings", namespace="CELERY")  # every CELERY_* setting
app.autodiscover_tasks()  # each app's tasks.py
