# -*- encoding: utf-8 -*-

from django.db import models

from bpp.models.abstract import ModelZAdnotacjami, ModelZNazwa


class Konferencja(ModelZNazwa, ModelZAdnotacjami):
    skrocona_nazwa = models.TextField(
        "Skrócona nazwa",
        max_length=250)

    rozpoczecie = models.DateField(
        "Rozpoczęcie"
    )

    zakonczenie = models.DateField(
        "Zakończenie"
    )

    miasto = models.TextField(
        "Miasto",
        max_length=100
    )

    panstwo = models.TextField(
        "Państwo",
        max_length=100
    )

    bazy_scopus = models.BooleanField(
        "Indeksowana w SCOPUS?",
        default=False
    )

    bazy_wos = models.BooleanField(
        "Indeksowana w WOS?",
        default=False
    )

    baza_inna = models.TextField(
        "Indeksowana w...",
        help_text="Wpisz nazwę innej bazy w której indeksowana jest ta "
                  "konferencja",
        blank=True,
        null=True,
    )
