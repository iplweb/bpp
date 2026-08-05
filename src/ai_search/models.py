from decimal import Decimal

from django.conf import settings
from django.db import models


class AISearchQuery(models.Model):
    """Log pojedynczego zapytania NL->DSL wraz z kosztem."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    model = models.CharField(max_length=100)
    pytanie = models.TextField()
    wygenerowany_query = models.TextField(blank=True, default="")
    wybrany_model_danych = models.CharField(max_length=32)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    cache_read_tokens = models.IntegerField(default=0)
    cache_write_tokens = models.IntegerField(default=0)
    cost_usd = models.DecimalField(
        max_digits=12, decimal_places=6, default=Decimal("0")
    )
    fx_rate = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("0"))
    cost_pln = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal("0")
    )
    success = models.BooleanField(default=False)
    error = models.TextField(null=True, blank=True)  # noqa: DJ001
    retried = models.BooleanField(default=False)

    class Meta:
        verbose_name = "zapytanie AI"
        verbose_name_plural = "zapytania AI"
        ordering = ("-created",)

    def __str__(self):
        return f"{self.created:%Y-%m-%d %H:%M} {self.pytanie[:60]}"


class FxRate(models.Model):
    """Trwały fallback ostatniego znanego kursu USD->PLN (gdy Redis+NBP padną)."""

    rate = models.DecimalField(max_digits=10, decimal_places=4)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-fetched_at", "-id")

    @classmethod
    def latest(cls):
        return cls.objects.first()

    @classmethod
    def store(cls, rate):
        return cls.objects.create(rate=Decimal(str(rate)))
