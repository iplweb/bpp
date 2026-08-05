"""Receivery rewokacji tokenów — implementacja w Task 9."""

from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver


@receiver(pre_save, sender=get_user_model())
def revoke_tokens_on_password_change(sender, instance, update_fields=None, **kwargs):
    """Zmiana hasła / dezaktywacja → skasuj tokeny OAuth usera (spec §5.7/W-D)."""
    if not instance.pk:
        return
    # Tani short-circuit (D6): np. `update last_login` przy każdym logowaniu
    # przekazuje update_fields={"last_login"} → nie ruszamy DB.
    if update_fields is not None and not (
        {"password", "is_active"} & set(update_fields)
    ):
        return
    try:
        stary = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    haslo_zmienione = stary.password != instance.password
    dezaktywowany = stary.is_active and not instance.is_active
    if haslo_zmienione or dezaktywowany:
        from oauth2_provider.models import (
            get_access_token_model,
            get_refresh_token_model,
        )

        get_access_token_model().objects.filter(user=instance).delete()
        get_refresh_token_model().objects.filter(user=instance).delete()
