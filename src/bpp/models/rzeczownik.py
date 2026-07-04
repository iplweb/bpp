from django.db import models


class Rzeczownik(models.Model):
    uid = models.CharField(max_length=20, primary_key=True)
    m = models.CharField(
        max_length=200,
        verbose_name="mianownik (lemat)",
        help_text=(
            "Mianownik liczby pojedynczej, np. „wydział” lub „dział”. "
            "Pozostałe przypadki i liczbę mnogą generuje automatycznie "
            "polish-inflection."
        ),
    )

    class Meta:
        verbose_name_plural = "rzeczowniki"

    def __str__(self):
        return f"Rzeczownik {self.uid} = {self.m}"

    @property
    def mianownik(self):
        return self.m
