from django.db import models

from .base import BasePBNMongoDBModel


class Publisher(BasePBNMongoDBModel):
    class Meta:
        verbose_name = "Wydawca w PBN API"
        verbose_name_plural = "Wydawcy w PBN API"

    pull_up_on_save = ["publisherName", "mniswId"]

    publisherName = models.TextField(null=True, blank=True, db_index=True)
    mniswId = models.IntegerField(null=True, blank=True, db_index=True)

    def __str__(self):
        return f"{self.publisherName}, MNISW ID: {self.mniswId or '-'}"
