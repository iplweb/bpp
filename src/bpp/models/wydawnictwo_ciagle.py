# -*- encoding: utf-8 -*-
from pprint import pprint

from dirtyfields.dirtyfields import DirtyFieldsMixin
from django.db import models
from django.db.models import CASCADE, SET_NULL
from django.db.models.signals import post_delete
from django.dispatch import receiver

from django.utils import timezone

from bpp.exceptions import WillNotExportError
from bpp.models import (
    AktualizujDatePBNNadrzednegoMixin,
    MaProcentyMixin,
    ModelOpcjonalnieNieEksportowanyDoAPI,
    ModelZMiejscemPrzechowywania,
    ModelZPBN_UID,
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
    ModelZAktualizacjaDlaPBN,
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
    PBNSerializerHelperMixin,
    Wydawnictwo_Baza,
)
from bpp.models.const import (
    RODZAJ_PBN_ARTYKUL,
    RODZAJ_PBN_KSIAZKA,
    RODZAJ_PBN_ROZDZIAL,
    TYP_OGOLNY_DO_PBN,
)
from bpp.models.system import Zewnetrzna_Baza_Danych
from bpp.models.util import ZapobiegajNiewlasciwymCharakterom


class Wydawnictwo_Ciagle_Autor(
    AktualizujDatePBNNadrzednegoMixin,
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

    def pbn_get_json(self):
        ret = {
            "orcid": True if self.autor.orcid else False,
            "type": TYP_OGOLNY_DO_PBN.get(
                self.typ_odpowiedzialnosci.typ_ogolny, "AUTHOR"
            ),
        }
        if self.dyscyplina_naukowa_id is not None:
            ret["disciplineId"] = self.dyscyplina_naukowa.kod_dla_pbn()

        # if self.jednostka.pbn_uid_id:
        #    ret["institutionId"] = self.jednostka.pbn_uid.pk

        if self.autor.pbn_uid_id:
            ret["personId"] = self.autor.pbn_uid.pk

        if self.autor.orcid:
            ret["personOrcidId"] = self.autor.orcid

        ret["statementDate"] = str(self.rekord.ostatnio_zmieniony_dla_pbn.date())

        return ret


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
    PBNSerializerHelperMixin,
    ModelZOpenAccessWydawnictwoCiagle,
    ModelZeZnakamiWydawniczymi,
    ModelZAktualizacjaDlaPBN,
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

    def pbn_get_json(self):
        ret = {
            "title": self.tytul_oryginalny,
            "year": self.rok,
            # "issue" ??
        }

        if self.tom:
            ret["volume"] = self.tom

        if self.strony:
            ret["pagesFromTo"] = self.strony

        if self.doi:
            ret["doi"] = self.doi

        if self.jezyk.pbn_uid_id is None:
            raise WillNotExportError(
                f'Język rekordu "{self.jezyk}" nie ma określonego odpowiednika w PBN'
            )

        ret["mainLanguage"] = self.jezyk.pbn_uid.code

        if self.charakter_formalny.rodzaj_pbn == RODZAJ_PBN_ARTYKUL:
            ret["type"] = "ARTICLE"
        elif self.charakter_formalny.rodzaj_pbn == RODZAJ_PBN_KSIAZKA:
            ret["type"] = "BOOK"
        elif self.charakter_formalny.rodzaj_pbn == RODZAJ_PBN_ROZDZIAL:
            ret["type"] = "CHAPTER"
        else:
            raise WillNotExportError(
                f"Rodzaj dla PBN nie określony dla charakteru formalnego {self.charakter_formalny}"
            )

        if self.public_www:
            ret["publicUri"] = self.public_www
        elif self.www:
            ret["publicUri"] = self.www

        ret["journal"] = self.zrodlo.pbn_get_json()

        authors = []
        statements = []
        for elem in self.autorzy_set.all():
            authors.append(elem.autor.pbn_get_json())
            statements.append(elem.pbn_get_json())
        ret["authors"] = authors
        ret["statements"] = statements

        pprint(ret)

        return ret


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


@receiver(post_delete, sender=Wydawnictwo_Ciagle_Autor)
def wydawnictwo_ciagle_autor_post_delete(sender, instance, **kwargs):
    rec = instance.rekord
    rec.ostatnio_zmieniony_dla_pbn = timezone.now()
    rec.save(update_fields=["ostatnio_zmieniony_dla_pbn"])
