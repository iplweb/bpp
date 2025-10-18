from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class MenuClick(models.Model):
    """Model do śledzenia kliknięć w menu admin przez użytkowników"""

    MAX_CLICKS_PER_USER = 1000

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Użytkownik",
        db_index=True,
    )
    menu_label = models.CharField(
        max_length=100, verbose_name="Nazwa pozycji menu", db_index=True
    )
    menu_url = models.CharField(max_length=500, verbose_name="URL pozycji menu")
    clicked_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Data kliknięcia", db_index=True
    )

    class Meta:
        verbose_name = "Kliknięcie w menu"
        verbose_name_plural = "Kliknięcia w menu"
        ordering = ["-clicked_at"]
        indexes = [
            models.Index(fields=["user", "menu_label"]),
            models.Index(fields=["user", "-clicked_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.menu_label} ({self.clicked_at})"


@receiver(post_save, sender=MenuClick)
def cleanup_old_menu_clicks(sender, instance, created, **kwargs):
    """Automatycznie kasuje najstarsze wpisy po przekroczeniu limitu 1000 na użytkownika"""
    if created:
        # Sprawdź liczbę wpisów dla tego użytkownika
        user_clicks_count = MenuClick.objects.filter(user=instance.user).count()

        if user_clicks_count > MenuClick.MAX_CLICKS_PER_USER:
            # Oblicz ile wpisów należy usunąć
            to_delete_count = user_clicks_count - MenuClick.MAX_CLICKS_PER_USER

            # Pobierz ID najstarszych wpisów do usunięcia
            old_clicks_ids = (
                MenuClick.objects.filter(user=instance.user)
                .order_by("clicked_at")
                .values_list("id", flat=True)[:to_delete_count]
            )

            # Usuń najstarsze wpisy
            MenuClick.objects.filter(id__in=list(old_clicks_ids)).delete()
