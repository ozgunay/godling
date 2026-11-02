from django.urls import path, re_path

from apps.screen import views

urlpatterns = [
    path("api/status", views.api_status),
    path("api/power", views.api_power),
    path("api/power/<int:call>", views.api_power_result),
    path("api/note", views.api_note),
    path("api/report", views.api_report),
    path("", views.screen),
    re_path(r"^(?P<path>(?!api/|accounts/|admin/|credits/).+)$", views.screen),
]
