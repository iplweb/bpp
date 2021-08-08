from django.db import models

from .base import BasePBNModel


class Country(BasePBNModel):
    code = models.CharField(max_length=5, primary_key=True)
    description = models.CharField(max_length=200)
