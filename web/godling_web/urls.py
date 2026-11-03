from allauth.account.decorators import secure_admin_login
from django.contrib import admin
from django.urls import include, path

from apps.users.log_views import view_logs

admin.site.site_header = "Godling admin"
admin.site.site_title = "Godling admin"
admin.site.index_title = "The island's site: viewers, prices, credits, notes"
# The admin's sign-in is the site's own (allauth): one sign-in page, its rate limits, and the two-factor code staff
# must have (apps.users.middleware). Django's own admin form would skip both.
admin.site.login = secure_admin_login(admin.site.login)

urlpatterns = [
    path("admin/logs/", view_logs, name="admin_logs"),  # before admin/, as AgentOp has it
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("credits/", include("apps.credits.urls")),
    path("", include("apps.feedback.urls")),
    path("", include("apps.screen.urls")),
]
