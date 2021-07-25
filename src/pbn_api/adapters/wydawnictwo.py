from ..exceptions import WillNotExportError
from .zrodlo import ZrodloPBNAdapter

from bpp.models import const
from bpp.util import strip_html


class WydawnictwoPBNAdapter:
    def __init__(self, original):
        self.original = original

    def pbn_get_json(self):
        ret = {
            "title": strip_html(self.original.tytul_oryginalny),
            "year": self.original.rok,
            # "issue" ??
        }

        # "openAccess": {
        #     "releaseDate": "2021-05-19T00:56:06.872Z",
        #     "releaseDateMonth": "JANUARY",
        #     "releaseDateYear": 0,
        #   },

        oa = {}
        if self.original.openaccess_wersja_tekstu_id is not None:
            #     "textVersion": "ORIGINAL_AUTHOR"
            oa["textVersion"] = self.original.openaccess_wersja_tekstu.skrot
        if self.original.openaccess_licencja_id is not None:
            #     "license": "CC_BY",
            oa["license"] = self.original.openaccess_licencja.skrot.replace("-", "_")
        if self.original.openaccess_czas_publikacji_id is not None:
            # "releaseDateMode": "BEFORE_PUBLICATION",
            oa["releaseDateMode"] = self.original.openaccess_czas_publikacji.skrot

        if oa.get("releaseDateMode") == "AFTER_PUBLICATION":
            # https://pbn.nauka.gov.pl/centrum-pomocy/faq-kategoria/dodawanie-publikacji/
            # tylko w przypadku udostępnienia po opublikowaniu należy podać liczbę miesięcy
            # jakie upłynęły od dnia opublikowania do dnia udostępnienia publikacji w sposób otwarty
            if self.original.openaccess_ilosc_miesiecy is not None:
                #     "months": 0,
                oa["months"] = str(self.original.openaccess_ilosc_miesiecy)

        if self.original.openaccess_tryb_dostepu_id is not None:
            # XX: dla zwartego bedzie modeMonograph
            #     "modeMonograph": "PUBLISHER_WEBSITE",
            #     "modeArticle": "OPEN_JOURNAL",
            oa["modeArticle"] = self.original.openaccess_tryb_dostepu.skrot
        if self.original.public_dostep_dnia is not None:
            oa["releaseDate"] = str(self.original.public_dostep_dnia)
        elif self.original.dostep_dnia is not None:
            oa["releaseDate"] = str(self.original.dostep_dnia)

        if oa.get("releaseDate") is None:
            oa["releaseDateMonth"] = "JANUARY"
            oa["releaseDateYear"] = str(self.original.rok)

        if (
            oa.get("license")
            and oa.get("textVersion")
            and oa.get("modeArticle")
            and oa.get("releaseDateMode")
        ):
            ret["openAccess"] = oa

        if self.original.tom:
            ret["volume"] = self.original.tom

        if hasattr(self.original, "zakres_stron"):
            zakres_stron = self.original.zakres_stron()
            if zakres_stron:
                ret["pagesFromTo"] = zakres_stron

        if self.original.doi:
            ret["doi"] = self.original.doi

        if self.original.jezyk.pbn_uid_id is None:
            raise WillNotExportError(
                f'Język rekordu "{self.original.jezyk}" nie ma określonego odpowiednika w PBN'
            )

        ret["mainLanguage"] = self.original.jezyk.pbn_uid.code

        if self.original.charakter_formalny.rodzaj_pbn == const.RODZAJ_PBN_ARTYKUL:
            ret["type"] = "ARTICLE"
        elif self.original.charakter_formalny.rodzaj_pbn == const.RODZAJ_PBN_KSIAZKA:
            ret["type"] = "BOOK"
        elif self.original.charakter_formalny.rodzaj_pbn == const.RODZAJ_PBN_ROZDZIAL:
            ret["type"] = "CHAPTER"
        else:
            raise WillNotExportError(
                f"Rodzaj dla PBN nie określony dla charakteru formalnego {self.original.charakter_formalny}"
            )

        if self.original.public_www:
            ret["publicUri"] = self.original.public_www
        elif self.original.www:
            ret["publicUri"] = self.original.www

        if not ret.get("doi") and not ret.get("publicUri"):
            raise WillNotExportError("Musi być DOI lub adres WWW")

        if hasattr(self.original, "zrodlo"):
            ret["journal"] = ZrodloPBNAdapter(self.original.zrodlo).pbn_get_json()

        authors = []
        statements = []
        institutions = []
        jednostki = set()
        for elem in self.original.autorzy_set.all():
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
