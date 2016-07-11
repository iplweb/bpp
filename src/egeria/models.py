from django.conf import settings
from django.db import models


class EgeriaImport(models.Model):
    created_on = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True)
    file = models.FileField(upload_to="egeria_xls")


class EgeriaRow(models.Model):
    parent = models.ForeignKey(EgeriaImport)

    lp = models.IntegerField()
    tytul_stopien = models.CharField(max_length=100)
    nazwisko = models.CharField(max_length=200)
    imie = models.CharField(max_length=200)
    pesel_md5 = models.CharField(max_length=32)
    stanowisko = models.CharField(max_length=50)
    nazwa_jednostki = models.CharField(max_length=300)
    wydzial = models.CharField(max_length=150)
