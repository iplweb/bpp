from django.db import models


class Cache_Liczba_N_Last_Updated(models.Model):
    wymaga_przeliczenia = models.BooleanField(default=True)
