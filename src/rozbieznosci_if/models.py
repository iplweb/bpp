from django.db import models

from django.contrib.contenttypes.fields import GenericForeignKey


class IgnorujRozbieznoscIf(models.Model):
    object = GenericForeignKey()

    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField("Rekord", db_index=True)
    created_on = models.DateTimeField("Utworzono", auto_now_add=True)

    class Meta:
        verbose_name = "ignorowanie rozbieżności impact factor"
        verbose_name = "ignorowanie rozbieżności impact factor"

    def __str__(self):
        try:
            return f"Ignoruj rozbieżności punktacji IF dla rekordu {self.object}"
        except BaseException:
            return 'Ignoruj rozbieżności punktacji IF dla rekordu "[brak rekordu, został usunięty]"'
