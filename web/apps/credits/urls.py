from django.urls import path

from apps.credits import views

urlpatterns = [
    path("", views.credits_page, name="credits"),
    path("buy/<slug:key>/", views.buy, name="credits_buy"),
    path("test-checkout/<str:session>/", views.test_checkout, name="credits_test_checkout"),
    path("done/", views.done, name="credits_done"),
    path("stripe/webhook/", views.stripe_webhook, name="credits_stripe_webhook"),
]
