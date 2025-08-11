from django.db import models


class Rzeczownik(models.Model):
    uid = models.CharField(max_length=20, primary_key=True)

    m = models.CharField(max_length=200, verbose_name="mianownik", help_text="kto? co?")
    d = models.CharField(
        max_length=200, verbose_name="dopełniacz", help_text="kogo? czego?"
    )
    c = models.CharField(
        max_length=200, verbose_name="celownik", help_text="komu? czemu?"
    )
    b = models.CharField(max_length=200, verbose_name="biernik", help_text="kogo? co?")
    n = models.CharField(
        max_length=200, verbose_name="narzędnik", help_text="z kim? z czym?"
    )
    ms = models.CharField(
        max_length=200, verbose_name="miejscownik", help_text="o kim? o czym?"
    )
    w = models.CharField(max_length=200, verbose_name="wołacz", help_text="o!")

    class Meta:
        verbose_name_plural = "rzeczowniki"

    def __str__(self):
        return f"Rzeczownik UID={self.uid} ({self.m}, {self.d}, {self.c}, ...)"
