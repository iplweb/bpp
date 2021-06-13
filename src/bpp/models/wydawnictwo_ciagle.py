# -*- encoding: utf-8 -*-

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
from bpp.util import strip_html


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
        if (
            not self.afiliuje
            or not self.jednostka.skupia_pracownikow
            or self.jednostka.pk < 0
        ):
            return

        ret = {
            # to NIE jest ta flaga; to jest flaga dot. czy dane są w indeksie ORCID
            # a nie czy autor ma Orcid ID
            "type": TYP_OGOLNY_DO_PBN.get(
                self.typ_odpowiedzialnosci.typ_ogolny, "AUTHOR"
            ),
        }

        if self.profil_orcid:
            ret["orcid"] = True

        if self.dyscyplina_naukowa_id is not None:
            ret["disciplineId"] = self.dyscyplina_naukowa.kod_dla_pbn()
        else:
            return

        # if self.jednostka.pbn_uid_id:
        #    ret["institutionId"] = self.jednostka.pbn_uid.pk

        if self.autor.pbn_uid_id:
            scientist = self.autor.pbn_uid

            pesel = scientist.value(
                "object", "externalIdentifiers", "PESEL", return_none=True
            )
            if pesel:
                ret["personNaturalId"] = pesel

            ret["personObjectId"] = scientist.pk

        else:
            if self.autor.orcid:  # and self.autor.orcid_w_pbn:
                ret["personOrcidId"] = self.autor.orcid

        if not ret.get("personOrcidId") and not ret.get("personObjectId"):
            return

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

    # def pbn_pull_author_data(self):
    #     from django.conf import settings
    #     uczelnia = Uczelnia.objects.get_default()
    #     client = self.get_client(uczelnia.pbn_app_id, uczelnia.pbn_app_token, base_url)
    #     client.exec(command)

    def pbn_get_json(self):
        ret = {
            "title": strip_html(self.tytul_oryginalny),
            "year": self.rok,
            # "issue" ??
        }

        # "openAccess": {
        #     "releaseDate": "2021-05-19T00:56:06.872Z",
        #     "releaseDateMonth": "JANUARY",
        #     "releaseDateYear": 0,
        #   },

        oa = {}
        if self.openaccess_wersja_tekstu_id is not None:
            #     "textVersion": "ORIGINAL_AUTHOR"
            oa["textVersion"] = self.openaccess_wersja_tekstu.skrot
        if self.openaccess_licencja_id is not None:
            #     "license": "CC_BY",
            oa["license"] = self.openaccess_licencja.skrot.replace("-", "_")
        if self.openaccess_czas_publikacji_id is not None:
            # "releaseDateMode": "BEFORE_PUBLICATION",
            oa["releaseDateMode"] = self.openaccess_czas_publikacji.skrot

        if oa.get("releaseDateMode") == "AFTER_PUBLICATION":
            # https://pbn.nauka.gov.pl/centrum-pomocy/faq-kategoria/dodawanie-publikacji/
            # tylko w przypadku udostępnienia po opublikowaniu należy podać liczbę miesięcy
            # jakie upłynęły od dnia opublikowania do dnia udostępnienia publikacji w sposób otwarty
            if self.openaccess_ilosc_miesiecy is not None:
                #     "months": 0,
                oa["months"] = str(self.openaccess_ilosc_miesiecy)

        if self.openaccess_tryb_dostepu_id is not None:
            # XX: dla zwartego bedzie modeMonograph
            #     "modeMonograph": "PUBLISHER_WEBSITE",
            #     "modeArticle": "OPEN_JOURNAL",
            oa["modeArticle"] = self.openaccess_tryb_dostepu.skrot
        if self.public_dostep_dnia is not None:
            oa["releaseDate"] = str(self.public_dostep_dnia)
        elif self.dostep_dnia is not None:
            oa["releaseDate"] = str(self.dostep_dnia)

        if (
            oa.get("license")
            and oa.get("textVersion")
            and oa.get("modeArticle")
            and oa.get("releaseDateMode")
        ):
            ret["openAccess"] = oa

        if self.tom:
            ret["volume"] = self.tom

        zakres_stron = self.zakres_stron()
        if zakres_stron:
            ret["pagesFromTo"] = zakres_stron

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

        if not ret.get("doi") and not ret.get("publicUri"):
            raise WillNotExportError("Musi być DOI lub adres WWW")

        ret["journal"] = self.zrodlo.pbn_get_json()

        authors = []
        statements = []
        institutions = []
        jednostki = set()
        for elem in self.autorzy_set.all():
            author = elem.autor.pbn_get_json()

            jednostka = elem.jednostka
            if (
                elem.afiliuje
                and jednostka.pk != -1
                and elem.jednostka.skupia_pracownikow
            ):
                if jednostka.pbn_uid_id is None:
                    # raise WillNotExportError(
                    #     f"Jednostka {jednostka} nie ma ustawionego odpowiednika w PBN"
                    # )
                    pass
                else:
                    author["affiliations"] = [jednostka.pbn_uid_id]
                    jednostki.add(elem.jednostka)

                statement = elem.pbn_get_json()
                if statement:
                    statements.append(statement)

            authors.append(author)

        ret["authors"] = authors
        ret["statements"] = statements

        institutions = {}
        for jednostka in jednostki:
            institutions[jednostka.pbn_uid_id] = {
                "objectId": jednostka.pbn_uid_id,
                # "polonUuid": jednostka.pbn_uid.value("object", "polonUuid"),
                # "versionHash": jednostka.pbn_uid.value("object", "versionHash"),
            }
        ret["institutions"] = institutions

        return ret

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


@receiver(post_delete, sender=Wydawnictwo_Ciagle_Autor)
def wydawnictwo_ciagle_autor_post_delete(sender, instance, **kwargs):
    rec = instance.rekord
    rec.ostatnio_zmieniony_dla_pbn = timezone.now()
    rec.save(update_fields=["ostatnio_zmieniony_dla_pbn"])
