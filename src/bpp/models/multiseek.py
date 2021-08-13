from django.db import models


class BppMultiseekVisibility(models.Model):
    field_name = models.CharField(
        "Systemowa nazwa pola", max_length=50, db_index=True, unique=True
    )
    label = models.CharField("Nazwa pola", max_length=200)
    public = models.BooleanField(
        default=True, verbose_name="Widoczne dla niezalogowanych"
    )

    authenticated = models.BooleanField(
        default=True, verbose_name="Widoczne dla zalogowanych"
    )
    staff = models.BooleanField(
        default=True, verbose_name='Widoczne dla osób "w zespole"'
    )

    sort_order = models.PositiveSmallIntegerField("Kolejność sortowania", default=0)

    class Meta:
        verbose_name = "widoczność opcji wyszukiwania"
        verbose_name_plural = "widoczność opcji wyszukiwania"
        ordering = ("sort_order",)

    def __str__(self):
        return f'Widoczność opcji wyszukiwania dla "{self.label}"'
