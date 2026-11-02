from django.apps import AppConfig


class RulesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rules"
    verbose_name = "Site rules"

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from apps.rules import words

        def forget(sender, **kwargs):
            words.forget()

        for signal in (post_save, post_delete):
            signal.connect(forget, sender="rules.BlockedWord", dispatch_uid=f"godling_blocked_words_{signal}",
                           weak=False)
