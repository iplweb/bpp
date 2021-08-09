from django.db import models

from .base import BasePBNModel

from django.contrib.postgres.fields import JSONField


class Language(BasePBNModel):
    code = models.CharField(max_length=5, primary_key=True)
    language = JSONField()

    def __str__(self):
        return self.language.get("pl") or self.language.get("en") or self.code
