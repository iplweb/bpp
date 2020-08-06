from django.db import models


class Grant(models.Model):
    nazwa_projektu = models.TextField(blank=True, null=True)
    zrodlo_finansowania = models.TextField(blank=True, null=True)
    numer_projektu = models.CharField(max_length=200, unique=True)
    rok = models.PositiveSmallIntegerField(null=True, blank=True)
