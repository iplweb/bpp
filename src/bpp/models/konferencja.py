# -*- encoding: utf-8 -*-

from django.db import models

from bpp.models.abstract import ModelZAdnotacjami, ModelZNazwa


class Konferencja(ModelZNazwa, ModelZAdnotacjami):
    nazwa = models.TextField(
        max_length=512,
        db_index=True)

    skrocona_nazwa = models.CharField(
        "Skrócona nazwa",
        max_length=250,
        null=True,
        blank=True
    )

    rozpoczecie = models.DateField(
        "Rozpoczęcie"
    )

    zakonczenie = models.DateField(
        "Zakończenie"
    )

    miasto = models.CharField(
        "Miasto",
        max_length=100
    )

    panstwo = models.CharField(
        "Państwo",
        max_length=100
    )

    baza_scopus = models.BooleanField(
        "Indeksowana w SCOPUS?",
        default=False
    )

    baza_wos = models.BooleanField(
        "Indeksowana w WOS?",
        default=False
    )

    baza_inna = models.CharField(
        "Indeksowana w...",
        max_length=200,
        help_text="Wpisz nazwę innej bazy w której indeksowana jest ta "
                  "konferencja",
        blank=True,
        null=True,
    )

    class Meta:
        unique_together = ('nazwa', 'rozpoczecie')
        ordering = ('-rozpoczecie', 'nazwa')
        verbose_name = 'konferencja'
        verbose_name_plural = 'konferencje'

    def __str__(self):
        return self.nazwa

