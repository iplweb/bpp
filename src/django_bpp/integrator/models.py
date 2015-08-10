# -*- encoding: utf-8 -*-

from django.db import models
from django.contrib.auth import get_user_model
from bpp.models import Autor, Jednostka
from django.conf import settings

STATUSY = [
    (0, "dodany"),
    (1, "w trakcie analizy"),
    (2, "przetworzony")
]


class AutorIntegrationFile(models.Model):
    name = models.CharField("Nazwa", max_length=255)
    file = models.FileField(verbose_name="Plik", upload_to="integrator")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL)
    uploaded_on = models.DateTimeField(auto_now_add=True)
    status = models.IntegerField(choices=STATUSY, default=STATUSY[0][0])
    extra_info = models.TextField()

AUTOR_IMPORT_COLUMNS = {
    u"Tytuł/Stopień": "tytul_skrot",
    u"Nazwisko": "nazwisko",
    u"Imię": "imie",
    u"Nazwa jednostki": "nazwa_jednostki",
    u"PBN ID": "pbn_id"
}

class AutorIntegrationRecord(models.Model):
    tytul_skrot = models.TextField()
    nazwisko = models.TextField()
    imie = models.TextField()
    nazwa_jednostki = models.TextField()
    pbn_id = models.TextField()

    matching_autor = models.ForeignKey(Autor)
    matching_jednostka = models.ForeignKey(Jednostka)
    zintegrowano = models.BooleanField(default=False)
    extra_info = models.TextField()