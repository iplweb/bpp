# -*- encoding: utf-8 -*-
from django.db import models
from django.db.models import CASCADE, SET_NULL

from bpp.models import (
    Autor,
    BazaModeluOdpowiedzialnosciAutorow,
    Charakter_Formalny,
    Jezyk,
    ModelPunktowany,
    ModelRecenzowany,
    ModelZAdnotacjami,
    ModelZeStatusem,
    ModelZeSzczegolami,
    ModelZInformacjaZ,
    ModelZRokiem,
    ModelZWWW,
    ModelOpcjonalnieNieEksportowanyDoAPI,
)
from bpp.models.abstract import (
    DodajAutoraMixin,
    MaProcentyMixin,
    ModelZAbsolutnymUrl,
    RekordBPPBaza,
)

from django.utils.functional import cached_property

from bpp.util import safe_html


class Patent_Autor(BazaModeluOdpowiedzialnosciAutorow):
    """Powiązanie autora do patentu."""

    rekord = models.ForeignKey("Patent", CASCADE, related_name="autorzy_set")

    class Meta:
        verbose_name = "powiązanie autora z patentem"
        verbose_name_plural = "powiązania autorów z patentami"
        app_label = "bpp"
        ordering = ("kolejnosc",)
        unique_together = [
            ("rekord", "autor", "typ_odpowiedzialnosci"),
            # Tu musi być autor, inaczej admin nie pozwoli wyedytować
            ("rekord", "autor", "kolejnosc"),
        ]


class Patent(
    RekordBPPBaza,
    ModelZRokiem,
    ModelZeStatusem,
    ModelZWWW,
    ModelRecenzowany,
    ModelPunktowany,
    ModelZeSzczegolami,
    ModelZInformacjaZ,
    ModelZAdnotacjami,
    MaProcentyMixin,
    DodajAutoraMixin,
    ModelZAbsolutnymUrl,
    ModelOpcjonalnieNieEksportowanyDoAPI,
):
    tytul_oryginalny = models.TextField("Tytuł oryginalny", db_index=True)

    data_zgloszenia = models.DateField("Data zgłoszenia", null=True, blank=True)

    numer_zgloszenia = models.CharField(
        "Numer zgłoszenia", max_length=255, null=True, blank=True
    )

    data_decyzji = models.DateField(null=True, blank=True)

    numer_prawa_wylacznego = models.CharField(
        "Numer prawa wyłącznego", max_length=255, null=True, blank=True
    )

    rodzaj_prawa = models.ForeignKey(
        "bpp.Rodzaj_Prawa_Patentowego", CASCADE, null=True, blank=True
    )

    wdrozenie = models.NullBooleanField("Wdrożenie",)

    wydzial = models.ForeignKey("bpp.Wydzial", SET_NULL, null=True, blank=True)

    autor_rekordu_klass = Patent_Autor
    autorzy = models.ManyToManyField(Autor, through=autor_rekordu_klass)

    class Meta:
        verbose_name = "patent"
        verbose_name_plural = "patenty"
        app_label = "bpp"

    def __str__(self):
        return self.tytul_oryginalny

    @cached_property
    def charakter_formalny(self):
        return Charakter_Formalny.objects.get(skrot="PAT")

    @cached_property
    def jezyk(self):
        return Jezyk.objects.get(skrot_dla_pbn="PL")

    def clean(self):
        self.tytul_oryginalny = safe_html(self.tytul_oryginalny)
