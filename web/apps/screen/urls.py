from django.urls import path, re_path
from django.views.generic import RedirectView

from apps.screen import views

urlpatterns = [
    path("api/status", views.api_status),
    path("api/power", views.api_power),
    path("api/power/<int:call>", views.api_power_result),
    path("api/note", views.api_note),
    path("api/report", views.api_report),
    path("api/replay/<str:what>", views.api_replay),
    # The landing page at the front; the screen at /watch (ADR-024). Its files keep their place at the root, so the
    # page's relative links (viewer.js, demo/…) find them from /watch as they did from /.
    path("", views.landing, name="landing"),
    path("watch", views.screen, name="watch"),
    path("watch/", RedirectView.as_view(url="/watch", query_string=True)),
    re_path(r"^(?P<path>(?!api/|accounts/|admin/|credits/).+)$", views.screen),
]
