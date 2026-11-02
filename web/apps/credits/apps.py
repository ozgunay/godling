from django.apps import AppConfig


class CreditsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.credits"
    verbose_name = "Credits and prices"

    def ready(self):
        from allauth.account.signals import email_confirmed

        from apps.credits.services import welcome

        def on_confirmed(sender, request, email_address, **kwargs):
            welcome(email_address.user)

        email_confirmed.connect(on_confirmed, dispatch_uid="godling_welcome_credits", weak=False)
