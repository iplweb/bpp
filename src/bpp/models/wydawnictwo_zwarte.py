# -*- encoding: utf-8 -*-
import re
import warnings

from dirtyfields.dirtyfields import DirtyFieldsMixin
from django.db import models
from django.db.models import CASCADE, PROTECT
from django.db.models.expressions import RawSQL

from django.contrib.contenttypes.fields import GenericRelation

from bpp.models import (
    DodajAutoraMixin,
    MaProcentyMixin,
    ModelOpcjonalnieNieEksportowanyDoAPI,
    ModelZMiejscemPrzechowywania,
    ModelZPBN_UID,
)
from bpp.models.abstract import (
    BazaModeluOdpowiedzialnosciAutorow,
    DwaTytuly,
    ModelPunktowany,
    ModelRecenzowany,
    ModelTypowany,
    ModelWybitny,
    ModelZAbsolutnymUrl,
    ModelZAdnotacjami,
    ModelZCharakterem,
    ModelZDOI,
    ModelZeStatusem,
    ModelZeSzczegolami,
    ModelZeZnakamiWydawniczymi,
    ModelZInformacjaZ,
    ModelZISBN,
    ModelZISSN,
    ModelZKonferencja,
    ModelZLiczbaCytowan,
    ModelZOpenAccess,
    ModelZPubmedID,
    ModelZRokiem,
    ModelZSeria_Wydawnicza,
    ModelZWWW,
    Wydawnictwo_Baza,
)
from bpp.models.autor import Autor
from bpp.models.nagroda import Nagroda
from bpp.models.system import Zewnetrzna_Baza_Danych
from bpp.models.util import ZapobiegajNiewlasciwymCharakterom
from bpp.models.wydawca import Wydawca


class Wydawnictwo_Zwarte_Autor(
    DirtyFieldsMixin,
    BazaModeluOdpowiedzialnosciAutorow,
):
    """Model zawierający informację o przywiązaniu autorów do wydawnictwa
    zwartego."""

    rekord = models.ForeignKey(
        "Wydawnictwo_Zwarte", CASCADE, related_name="autorzy_set"
    )

    class Meta:
        verbose_name = "powiązanie autora z wyd. zwartym"
        verbose_name_plural = "powiązania autorów z wyd. zwartymi"
        app_label = "bpp"
        ordering = ("kolejnosc",)
        unique_together = [
            ("rekord", "autor", "typ_odpowiedzialnosci"),
            # Tu musi być autor, inaczej admin nie pozwoli wyedytować
            ("rekord", "autor", "kolejnosc"),
        ]


MIEJSCE_I_ROK_MAX_LENGTH = 256


class Wydawnictwo_Zwarte_Baza(
    Wydawnictwo_Baza,
    DwaTytuly,
    ModelZRokiem,
    ModelZeStatusem,
    ModelZWWW,
    ModelZPubmedID,
    ModelZDOI,
    ModelRecenzowany,
    ModelPunktowany,
    ModelTypowany,
    ModelZeSzczegolami,
    ModelZInformacjaZ,
    ModelZISBN,
    ModelZAdnotacjami,
    ModelZAbsolutnymUrl,
    ModelZLiczbaCytowan,
    ModelZMiejscemPrzechowywania,
    ModelOpcjonalnieNieEksportowanyDoAPI,
):
    """Baza dla klas Wydawnictwo_Zwarte oraz Praca_Doktorska_Lub_Habilitacyjna"""

    miejsce_i_rok = models.CharField(
        max_length=MIEJSCE_I_ROK_MAX_LENGTH,
        blank=True,
        null=True,
        help_text="""Przykładowo:
        Warszawa 2012. Wpisz proszę najpierw miejsce potem rok; oddziel
        spacją.""",
    )

    wydawca = models.ForeignKey(Wydawca, PROTECT, null=True, blank=True)
    wydawca_opis = models.CharField(
        "Wydawca - szczegóły", max_length=256, null=True, blank=True
    )

    oznaczenie_wydania = models.CharField(max_length=400, null=True, blank=True)

    def get_wydawnictwo(self):
        # Zwróć nazwę wydawcy + pole wydawca_opis lub samo pole wydawca_opis, jeżeli
        # wydawca (indeksowany) nie jest ustalony
        if self.wydawca_id is None:
            return self.wydawca_opis

        opis = self.wydawca_opis or ""
        try:
            if opis[0] in ".;-/,":
                # Nie wstawiaj spacji między wydawcę a opis jeżeli zaczyna się od kropki, przecinka itp
                return f"{self.wydawca.nazwa}{opis}".strip()
        except IndexError:
            pass

        return f"{self.wydawca.nazwa} {opis}".strip()

    def set_wydawnictwo(self, value):
        warnings.warn("W przyszlosci uzyj 'wydawca_opis'", DeprecationWarning)
        self.wydawca_opis = value

    wydawnictwo = property(get_wydawnictwo, set_wydawnictwo)

    redakcja = models.TextField(null=True, blank=True)

    class Meta:
        abstract = True


class ModelZOpenAccessWydawnictwoZwarte(ModelZOpenAccess):
    openaccess_tryb_dostepu = models.ForeignKey(
        "Tryb_OpenAccess_Wydawnictwo_Zwarte", CASCADE, blank=True, null=True
    )

    class Meta:
        abstract = True


rok_regex = re.compile(r"\s[12]\d\d\d")


class Wydawnictwo_Zwarte(
    ZapobiegajNiewlasciwymCharakterom,
    Wydawnictwo_Zwarte_Baza,
    ModelZCharakterem,
    ModelZOpenAccessWydawnictwoZwarte,
    ModelZeZnakamiWydawniczymi,
    ModelZKonferencja,
    ModelZSeria_Wydawnicza,
    ModelZISSN,
    ModelWybitny,
    ModelZPBN_UID,
    MaProcentyMixin,
    DodajAutoraMixin,
    DirtyFieldsMixin,
):
    """Wydawnictwo zwarte, czyli: książki, broszury, skrypty, fragmenty,
    doniesienia zjazdowe."""

    autor_rekordu_klass = Wydawnictwo_Zwarte_Autor
    autorzy = models.ManyToManyField(Autor, through=autor_rekordu_klass)

    wydawnictwo_nadrzedne = models.ForeignKey(
        "self",
        CASCADE,
        blank=True,
        null=True,
        help_text="""Jeżeli dodajesz rozdział,
        tu wybierz pracę, w ramach której dany rozdział występuje.""",
        related_name="wydawnictwa_powiazane_set",
    )

    calkowita_liczba_autorow = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="""Jeżeli dodajesz monografię, wpisz
        tutaj całkowitą liczbę autorów monografii. Ta informacja zostanie
        użyta w eksporcie danych do PBN. Jeżeli informacja ta nie zostanie
        uzupełiona, wartość tego pola zostanie obliczona i będzie to ilość
        wszystkich autorów przypisanych do danej monografii""",
    )

    calkowita_liczba_redaktorow = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="""Jeżeli dodajesz monografię, wpisz tutaj całkowitą liczbę
        redaktorów monografii. Ta informacja zostanie użyta w eksporcie
        danych do PBN. Jeżeli pole to nie zostanie uzupełnione, wartość ta
        zostanie obliczona i będzie to ilość wszystkich redaktorów
        przypisanych do danej monografii""",
    )

    nagrody = GenericRelation(Nagroda)

    class Meta:
        verbose_name = "wydawnictwo zwarte"
        verbose_name_plural = "wydawnictwa zwarte"
        app_label = "bpp"

    def wydawnictwa_powiazane_posortowane(self):
        """
        Sortowanie wydawnictw powiązanych wg pierwszej liczby dziesiętnej występującej w polu 'Strony'
        """
        return self.wydawnictwa_powiazane_set.order_by(
            RawSQL(
                r"CAST((regexp_match(COALESCE(bpp_wydawnictwo_zwarte.strony, '99999999'), '(\d+)'))[1] AS INT)",
                "",
            )
        )


class Wydawnictwo_Zwarte_Zewnetrzna_Baza_Danych(models.Model):
    rekord = models.ForeignKey(
        Wydawnictwo_Zwarte, CASCADE, related_name="zewnetrzna_baza_danych"
    )
    baza = models.ForeignKey(Zewnetrzna_Baza_Danych, CASCADE)
    info = models.CharField(
        verbose_name="Informacje dodatkowe", max_length=512, blank=True, null=True
    )

    class Meta:
        verbose_name = "powiązanie wydawnictwa zwartego z zewnętrznymi bazami danych"
        verbose_name_plural = (
            "powiązania wydawnictw zwartych z zewnętrznymi bazami danych"
        )
