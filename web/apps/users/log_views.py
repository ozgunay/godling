"""The admin's log viewer (borrowed from AgentOp's apps/core/log_views.py): the tail of the live run's logs, for staff.

GODLING_RUN_DIR is the run the island is on (the world's, the mind's and the panel's logs live there)."""
from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render

LOGS = {"world": "world.log", "mind": "console.log", "thoughts": "mind/log.jsonl", "panel": "panel.log",
        "replay": "replay.log"}
TAIL_BYTES = 200_000
TAIL_LINES = 200


@staff_member_required
def view_logs(request):
    which = request.GET.get("log", "mind")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if not settings.GODLING_RUN_DIR:
            return JsonResponse({"content": "GODLING_RUN_DIR is not set: the site does not know where the run is."})
        path = Path(settings.GODLING_RUN_DIR) / LOGS.get(which, LOGS["mind"])
        try:
            with path.open("rb") as f:
                f.seek(max(0, path.stat().st_size - TAIL_BYTES))
                lines = f.read().decode("utf-8", "replace").splitlines()[-TAIL_LINES:]
            return JsonResponse({"content": "\n".join(lines)})
        except FileNotFoundError:
            return JsonResponse({"content": f"{path.name} is not there (yet)."})
    return render(request, "admin/log_viewer.html", {"logs": LOGS, "which": which, "title": "The island's logs"})
