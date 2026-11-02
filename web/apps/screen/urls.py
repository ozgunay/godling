from django.urls import path, re_path

from apps.screen import views

urlpatterns = [
    path("api/status", views.api_status),
    path("api/power", views.api_power),
    path("api/note", views.api_note),
    path("api/report", views.api_report),
    path("api/replay/<str:what>", views.api_replay),
    path("", views.screen),
    re_path(r"^(?P<path>(?!api/|accounts/|admin/|credits/).+)$", views.screen),
]
