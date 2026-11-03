"""What viewers tell the people who make the island: bug reports, questions and ideas, sent from the screen's bottle
(world/viewer/feedback.js) while the site is in beta. Notes fly in to Godling; these drift out to the makers, and
Godling never reads them. Staff read them in the admin, and each is emailed to the inbox the site rules name."""
from datetime import datetime, timezone

from django.conf import settings
from django.db import models

TEXT_LIMIT = 2000  # world/viewer/feedback.js LIMIT


class Feedback(models.Model):
    BUG, QUESTION, IDEA = "bug", "question", "idea"
    KINDS = [(BUG, "Bug"), (QUESTION, "Question"), (IDEA, "Idea")]
    NEW, LOOKING, DONE = "new", "looking", "done"
    STATUSES = [(NEW, "New"), (LOOKING, "Being looked at"), (DONE, "Done")]

    # Kept when its account goes: a bug report is still a bug report (AgentOp keeps them so too).
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="feedback")
    kind = models.CharField(max_length=10, choices=KINDS, default=BUG)
    text = models.TextField(max_length=TEXT_LIMIT)
    screen = models.JSONField(default=dict, blank=True,
                              help_text="What the viewer's screen showed, attached when they chose to: live or replay, "
                                        "the island's hour, the camera, the window's size, the browser and system. "
                                        "Never more than that (views.screen_facts).")
    status = models.CharField(max_length=10, choices=STATUSES, default=NEW)
    staff_note = models.TextField(blank=True, help_text="For staff only; the viewer never sees it.")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = verbose_name_plural = "feedback"

    def __str__(self):
        return f"{self.get_kind_display()} from {self.author or 'a deleted account'}: {self.text[:60]}"

    def facts(self):
        """What the screen showed, as lines for staff (the admin and the email); [] when nothing was attached."""
        s = self.screen or {}
        lines = []
        if s.get("view") == "replay":
            moment = s.get("moment")
            at = datetime.fromtimestamp(moment / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if moment else ""
            lines.append(f"Watching: the island's past{', at ' + at if at else ''}")
        elif s.get("view"):
            lines.append("Watching: live")
        if "day" in s or "hour" in s:
            hour = s.get("hour")
            clock = f"{int(hour % 24):02d}:{int(hour % 1 * 60):02d}" if isinstance(hour, (int, float)) else ""
            lines.append("Island: " + ", ".join(p for p in (f"day {s['day']}" if "day" in s else "", clock) if p))
        if s.get("stream"):
            lines.append(f"Island stream: {s['stream']}")
        if s.get("camera"):
            lines.append("Camera: " + ("following Godling" if s["camera"] == "follow" else "free"))
        window = " ".join(p for p in (s.get("size", ""), f"at {s['pixels']}x" if "pixels" in s else "",
                                      "(touch)" if s.get("touch") else "") if p)
        if window:
            lines.append(f"Window: {window}")
        if s.get("browser") or s.get("system"):
            lines.append("Browser: " + " on ".join(p for p in (s.get("browser"), s.get("system")) if p))
        return lines
