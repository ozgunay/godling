"""As AgentOp's: the blocked-domain cache is rebuilt whenever an admin changes the list."""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


@receiver([post_save, post_delete], sender="users.DisposableDomain")
def invalidate_disposable_domain_cache(sender, **kwargs):
    from apps.users.validators import invalidate_disposable_domains_cache

    invalidate_disposable_domains_cache()
