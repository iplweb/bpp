from django.db import models
from django.conf import settings

# Create your models here.
from bpp.models.struktura import Wydzial


class PlikEksportuPBN(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL)
    created_on = models.DateTimeField(auto_now_add=True)
    file = models.FileField(verbose_name="Plik", upload_to="eksport_pbn")

    wydzial = models.ForeignKey(Wydzial)
    rok = models.IntegerField()