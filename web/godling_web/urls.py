from django.contrib import admin
from django.urls import include, path

from apps.users.log_views import view_logs

admin.site.site_header = "Godling admin"
admin.site.site_title = "Godling admin"
admin.site.index_title = "The island's site: viewers, prices, credits, notes"

urlpatterns = [
    path("admin/logs/", view_logs, name="admin_logs"),  # before admin/, as AgentOp has it
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("credits/", include("apps.credits.urls")),
    path("", include("apps.screen.urls")),
]
