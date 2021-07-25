# -*- encoding: utf-8 -*-

from dirtyfields.dirtyfields import DirtyFieldsMixin
from django.db import models
from django.db.models import CASCADE, SET_NULL

from bpp.models import (
    MaProcentyMixin,
    ModelOpcjonalnieNieEksportowanyDoAPI,
    ModelZMiejscemPrzechowywania,
    ModelZPBN_UID,
    parse_informacje,
    wez_zakres_stron,
)
from bpp.models.abstract import (
    BazaModeluOdpowiedzialnosciAutorow,
    DodajAutoraMixin,
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
    ModelZISSN,
    ModelZKonferencja,
    ModelZLiczbaCytowan,
    ModelZNumeremZeszytu,
    ModelZOpenAccess,
    ModelZPubmedID,
    ModelZRokiem,
    ModelZWWW,
    Wydawnictwo_Baza,
)
from bpp.models.system import Zewnetrzna_Baza_Danych
from bpp.models.util import ZapobiegajNiewlasciwymCharakterom


class Wydawnictwo_Ciagle_Autor(
    DirtyFieldsMixin,
    BazaModeluOdpowiedzialnosciAutorow,
):
    """Powiązanie autora do wydawnictwa ciągłego."""

    rekord = models.ForeignKey(
        "Wydawnictwo_Ciagle", CASCADE, related_name="autorzy_set"
    )

    class Meta:
        verbose_name = "powiązanie autora z wyd. ciągłym"
        verbose_name_plural = "powiązania autorów z wyd. ciągłymi"
        app_label = "bpp"
        ordering = ("kolejnosc",)
        unique_together = [
            ("rekord", "autor", "typ_odpowiedzialnosci"),
            # Tu musi być autor, inaczej admin nie pozwoli wyedytować
            ("rekord", "autor", "kolejnosc"),
        ]


class ModelZOpenAccessWydawnictwoCiagle(ModelZOpenAccess):
    openaccess_tryb_dostepu = models.ForeignKey(
        "Tryb_OpenAccess_Wydawnictwo_Ciagle",
        SET_NULL,
        verbose_name="OpenAccess: tryb dostępu",
        blank=True,
        null=True,
    )

    class Meta:
        abstract = True


class Wydawnictwo_Ciagle(
    ZapobiegajNiewlasciwymCharakterom,
    Wydawnictwo_Baza,
    DwaTytuly,
    ModelZRokiem,
    ModelZeStatusem,
    ModelZAbsolutnymUrl,
    ModelZWWW,
    ModelZPubmedID,
    ModelZDOI,
    ModelRecenzowany,
    ModelPunktowany,
    ModelTypowany,
    ModelZeSzczegolami,
    ModelZISSN,
    ModelZInformacjaZ,
    ModelZAdnotacjami,
    ModelZCharakterem,
    ModelZOpenAccessWydawnictwoCiagle,
    ModelZeZnakamiWydawniczymi,
    ModelZNumeremZeszytu,
    ModelZKonferencja,
    ModelWybitny,
    ModelZPBN_UID,
    ModelZLiczbaCytowan,
    ModelZMiejscemPrzechowywania,
    ModelOpcjonalnieNieEksportowanyDoAPI,
    MaProcentyMixin,
    DodajAutoraMixin,
    DirtyFieldsMixin,
):
    """Wydawnictwo ciągłe, czyli artykuły z czasopism, komentarze, listy
    do redakcji, publikacje w suplemencie, etc."""

    autor_rekordu_klass = Wydawnictwo_Ciagle_Autor
    autorzy = models.ManyToManyField("Autor", through=autor_rekordu_klass)

    zrodlo = models.ForeignKey(
        "Zrodlo", null=True, verbose_name="Źródło", on_delete=models.SET_NULL
    )

    # To pole nie służy w bazie danych do niczego - jedyne co, to w adminie
    # w wygodny sposób chcemy wyświetlić przycisk 'uzupelnij punktacje', jak
    # się okazuje, przy używaniu standardowych procedur w Django jest to
    # z tego co na dziś dzień umiem, mocno utrudnione.
    uzupelnij_punktacje = models.BooleanField(default=False)

    class Meta:
        verbose_name = "wydawnictwo ciągłe"
        verbose_name_plural = "wydawnictwa ciągłe"
        app_label = "bpp"

    def punktacja_zrodla(self):
        """Funkcja - skrót do użycia w templatkach, zwraca punktację zrodla
        za rok z tego rekordu (self)"""

        from bpp.models.zrodlo import Punktacja_Zrodla

        if hasattr(self, "zrodlo_id") and self.zrodlo_id is not None:
            try:
                return self.zrodlo.punktacja_zrodla_set.get(rok=self.rok)
            except Punktacja_Zrodla.DoesNotExist:
                pass

    def numer_wydania(self):  # issue
        if hasattr(self, "nr_zeszytu"):
            if self.nr_zeszytu:
                return self.nr_zeszytu.strip()

        res = parse_informacje(self.informacje, "numer")
        if res is not None:
            return res.strip()

        return

    def numer_tomu(self):
        if hasattr(self, "tom"):
            if self.tom:
                return self.tom
        return parse_informacje(self.informacje, "tom")

    def zakres_stron(self):
        if self.strony:
            return self.strony
        else:
            strony = wez_zakres_stron(self.szczegoly)
            if strony:
                return strony


class Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych(models.Model):
    rekord = models.ForeignKey(
        Wydawnictwo_Ciagle, CASCADE, related_name="zewnetrzna_baza_danych"
    )
    baza = models.ForeignKey(Zewnetrzna_Baza_Danych, CASCADE)
    info = models.CharField(
        verbose_name="Informacje dodatkowe", max_length=512, blank=True, null=True
    )

    class Meta:
        verbose_name = "powiązanie wydawnictwa ciągłego z zewnętrznymi bazami danych"
        verbose_name_plural = (
            "powiązania wydawnictw ciągłych z zewnętrznymi bazami danych"
        )
