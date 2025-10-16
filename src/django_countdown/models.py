from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SiteCountdown(models.Model):
    """
    Model przechowujący informacje o odliczaniu czasu do wyłączenia serwisu.
    Każdy Site może mieć tylko jeden aktywny countdown.
    """

    site = models.OneToOneField(
        Site,
        on_delete=models.CASCADE,
        verbose_name="Serwis",
        help_text="Serwis, którego dotyczy odliczanie",
    )

    countdown_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Czas odliczania",
        help_text="Data i godzina, o której serwis zostanie zablokowany",
    )

    maintenance_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Koniec prac konserwacyjnych",
        help_text="Data i godzina zakończenia prac konserwacyjnych (opcjonalnie)",
    )

    message = models.CharField(
        max_length=200,
        verbose_name="Krótka wiadomość",
        help_text="Krótki komunikat wyświetlany w nagłówku strony (max 200 znaków)",
    )

    long_description = models.TextField(
        blank=True,
        default="",
        verbose_name="Długi opis",
        help_text="Opcjonalny dłuższy opis wyświetlany na zablokowanej stronie",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data utworzenia")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Data aktualizacji")

    class Meta:
        verbose_name = "Odliczanie do zamknięcia serwisu"
        verbose_name_plural = "Odliczania do zamknięcia serwisu"
        ordering = ["-countdown_time"]

    def __str__(self):
        return f"{self.site.domain} - {self.message} ({self.countdown_time})"

    def is_expired(self):
        """Sprawdza, czy odliczanie się zakończyło (czas minął)."""
        if self.countdown_time is None:
            return False
        return timezone.now() >= self.countdown_time

    is_expired.boolean = True
    is_expired.short_description = "Wygasło?"

    def clean(self):
        """Walidacja: nie pozwalaj na utworzenie odliczania z czasem w przeszłości."""
        super().clean()
        if self.countdown_time and self.countdown_time <= timezone.now():
            raise ValidationError(
                {
                    "countdown_time": "Czas odliczania nie może być w przeszłości. Wybierz datę w przyszłości."
                }
            )
        if self.maintenance_until and self.countdown_time:
            if self.maintenance_until <= self.countdown_time:
                raise ValidationError(
                    {
                        "maintenance_until": "Koniec prac konserwacyjnych musi być późniejszy niż czas odliczania."
                    }
                )

    def time_remaining(self):
        """Zwraca czas pozostały do zakończenia odliczania."""
        if self.countdown_time is None:
            return "Nie ustawiono"
        if self.is_expired():
            return "Wygasło"

        delta = self.countdown_time - timezone.now()
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days} dni")
        if hours > 0:
            parts.append(f"{hours} godz")
        if minutes > 0:
            parts.append(f"{minutes} min")
        if seconds > 0 or not parts:
            parts.append(f"{seconds} sek")

        return " ".join(parts)

    time_remaining.short_description = "Pozostały czas"

    def is_maintenance_finished(self):
        """Sprawdza, czy prace konserwacyjne się zakończyły."""
        if self.maintenance_until is None:
            return False
        return timezone.now() >= self.maintenance_until

    is_maintenance_finished.boolean = True
    is_maintenance_finished.short_description = "Konserwacja zakończona?"

    def maintenance_time_remaining(self):
        """Zwraca czas pozostały do zakończenia prac konserwacyjnych."""
        if self.maintenance_until is None:
            return None
        if self.is_maintenance_finished():
            return None

        delta = self.maintenance_until - timezone.now()
        return int(delta.total_seconds())

    def maintenance_duration_minutes(self):
        """Zwraca zaplanowany czas przerwy technicznej w minutach (różnica między maintenance_until a countdown_time)."""
        if self.maintenance_until is None or self.countdown_time is None:
            return None

        delta = self.maintenance_until - self.countdown_time
        return int(delta.total_seconds() / 60)
