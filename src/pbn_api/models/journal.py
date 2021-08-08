from django.db import models

from .base import BasePBNMongoDBModel


class Journal(BasePBNMongoDBModel):
    class Meta:
        verbose_name = "Zródło w PBN API"
        verbose_name_plural = "Zródła w PBN API"

    title = models.TextField(null=True, blank=True, db_index=True)
    websiteLink = models.TextField(null=True, blank=True, db_index=True)
    issn = models.TextField(null=True, blank=True, db_index=True)
    eissn = models.TextField(null=True, blank=True, db_index=True)
    mniswId = models.IntegerField(null=True, blank=True, db_index=True)

    pull_up_on_save = ["title", "websiteLink", "issn", "eissn", "mniswId"]

    def __str__(self):
        return (
            f"{self.title}, ISSN: {self.issn or '-'}, "
            f"EISSN: {self.eissn or '-'}, MNISW ID: {self.mniswId or '-'}"
        )
