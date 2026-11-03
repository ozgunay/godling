from django.urls import path

from apps.feedback import views

urlpatterns = [
    path("api/feedback", views.api_feedback),
]
