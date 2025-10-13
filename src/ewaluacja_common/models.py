from django.db import models


class Rodzaj_Autora(models.Model):
    nazwa = models.CharField(max_length=100, verbose_name="Nazwa")
    skrot = models.CharField(max_length=1, unique=True, verbose_name="Skrót")
    sort = models.PositiveSmallIntegerField(verbose_name="Sortowanie")
    jest_w_n = models.BooleanField(
        default=False, verbose_name="Określa czy dany rodzaj autora wchodzi do liczby N"
    )
    licz_sloty = models.BooleanField(
        default=False, verbose_name="Określa, czy dany rodzaj autora ma obliczane sloty"
    )

    class Meta:
        verbose_name = "Rodzaj autora"
        verbose_name_plural = "Rodzaje autorów"
        ordering = ["sort"]

    def __str__(self):
        return f"{self.skrot} - {self.nazwa}"
