from import_common.normalization import normalize_isbn, normalize_issn
from ..exceptions import WillNotExportError
from .autor import AutorSimplePBNAdapter, AutorZDyscyplinaPBNAdapter
from .wydawca import WydawcaPBNAdapter
from .wydawnictwo_autor import WydawnictwoAutorToStatementPBNAdapter
from .wydawnictwo_nadrzedne import WydawnictwoNadrzednePBNAdapter
from .zrodlo import ZrodloPBNAdapter

from django.utils.functional import cached_property

from bpp.models import const
from bpp.models.const import TO_REDAKTOR, TO_REDAKTOR_TLUMACZENIA, TO_TLUMACZ
from bpp.util import strip_html


class WydawnictwoPBNAdapter:
    def __init__(self, original):
        self.original = original

    @cached_property
    def typy_ogolne_autorow(self):
        return set(
            self.original.autorzy_set.order_by()
            .values_list("typ_odpowiedzialnosci__typ_ogolny", flat=True)
            .distinct()
        )

    def pod_redakcja(self):
        # zwraca True jezeli self.original to praca 'pod redakcja' czyli ze ma tylko
        # redaktorow

        if (
            len(self.typy_ogolne_autorow) == 1
            and TO_REDAKTOR in self.typy_ogolne_autorow
        ):
            return True
        return False

    def get_translation(self):
        # Jeżeli praca ma wyłącznie tłumaczy lub redaktorów tłumaczy to jest tłumaczeniem

        lst = list(self.typy_ogolne_autorow)
        if TO_REDAKTOR_TLUMACZENIA in lst:
            lst.remove(TO_REDAKTOR_TLUMACZENIA)
        if TO_TLUMACZ in lst:
            lst.remove(TO_TLUMACZ)
        if not lst:
            return True

        # Praca ma jeszcze jakieś typu autorów więc potencjalnie może nie być tlumaczeniem
        return False

    def nr_tomu(self):
        if hasattr(self.original, "numer_tomu"):
            ntomu = self.original.numer_tomu()
            if ntomu is not None:
                return ntomu

        if hasattr(self.original, "tom"):
            if self.original.tom:
                return self.original.tom

    def get_type(self):

        if self.original.charakter_formalny.rodzaj_pbn == const.RODZAJ_PBN_ARTYKUL:
            return "ARTICLE"
        elif self.original.charakter_formalny.rodzaj_pbn == const.RODZAJ_PBN_KSIAZKA:
            if self.pod_redakcja():
                return "EDITED_BOOK"
            return "BOOK"
        elif self.original.charakter_formalny.rodzaj_pbn == const.RODZAJ_PBN_ROZDZIAL:
            return "CHAPTER"
        else:
            raise WillNotExportError(
                f"Rodzaj dla PBN nie określony dla charakteru formalnego {self.original.charakter_formalny}"
            )

    def pbn_get_json(self):
        ret = {
            "title": strip_html(self.original.tytul_oryginalny),
            "year": self.original.rok,
            "type": self.get_type(),
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
            if ret["type"] == "ARTICLE":
                oa["modeArticle"] = self.original.openaccess_tryb_dostepu.skrot
            else:
                oa["modeMonograph"] = self.original.openaccess_tryb_dostepu.skrot
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

        volume = self.nr_tomu()
        if volume:
            ret["volume"] = volume

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
        if self.original.jezyk_orig:

            if self.original.jezyk_orig.pbn_uid_id is None:
                raise WillNotExportError(
                    f'Język *oryginalny* rekordu "{self.original.jezyk}" nie ma określonego odpowiednika w PBN'
                )

            ret["originalLanguage"] = self.original.jezyk_orig.pbn_uid.code

        if self.original.public_www:
            ret["publicUri"] = self.original.public_www
        elif self.original.www:
            ret["publicUri"] = self.original.www

        if not ret.get("doi") and not ret.get("publicUri"):
            raise WillNotExportError("Musi być DOI lub adres WWW")

        if hasattr(self.original, "zrodlo"):
            ret["journal"] = ZrodloPBNAdapter(self.original.zrodlo).pbn_get_json()

        authors = []
        editors = []
        translators = []
        translationEditors = []
        statements = []
        institutions = []
        jednostki = set()
        for elem in self.original.autorzy_set.all().select_related():
            #
            # Jeżeli dany rekord Wydawnictwo_..._Autor ma dyscyplinę, to takiego autora
            # eksportujemy 'w pełni' tzn ze wszystkimi posiadanymi przez niego identyfikatorami
            # typu PBN UID czy ORCID:
            #

            if elem.dyscyplina_naukowa_id is None:
                #
                # Autor nie ma dyscypliny -- prosty eksport imie + nazwisko
                #
                author = AutorSimplePBNAdapter(elem.autor).pbn_get_json()
            else:
                author = AutorZDyscyplinaPBNAdapter(elem.autor).pbn_get_json()

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

                statement = WydawnictwoAutorToStatementPBNAdapter(elem).pbn_get_json()
                if statement:
                    statements.append(statement)

            if elem.typ_odpowiedzialnosci.typ_ogolny == const.TO_REDAKTOR:
                editors.append(author)
            elif elem.typ_odpowiedzialnosci.typ_ogolny == const.TO_TLUMACZ:
                translators.append(author)
            elif elem.typ_odpowiedzialnosci.typ_ogolny == const.TO_REDAKTOR_TLUMACZENIA:
                translationEditors.append(author)
            else:
                authors.append(author)

        if authors:
            ret["authors"] = authors
        if translators:
            ret["translators"] = translators
        if editors:
            ret["editors"] = editors
        if translationEditors:
            ret["translationEditors"] = translationEditors
        if statements:
            ret["statements"] = statements

        if hasattr(self.original, "isbn"):
            if self.original.isbn:
                ret["isbn"] = normalize_isbn(self.original.isbn)

        if hasattr(self.original, "issn"):
            if self.original.issn:
                ret["issn"] = normalize_issn(self.original.issn)

        if hasattr(self.original, "numer_wydania"):
            nr_wydania = self.original.numer_wydania()
            if nr_wydania:
                ret["issue"] = nr_wydania

        if hasattr(self.original, "seria_wydawnicza_id"):
            seria = self.original.seria_wydawnicza_id
            if seria is not None:
                ret["series"] = self.original.seria_wydawnicza.nazwa

        if hasattr(self.original, "numer_w_serii"):
            if self.original.numer_w_serii:
                ret["numberInSeries"] = self.original.numer_w_serii

        if self.original.pbn_uid_id is not None:
            ret["objectId"] = self.original.pbn_uid_id

        if hasattr(self.original, "miejsce_i_rok"):
            if self.original.miejsce_i_rok:
                miejsce = " ".join(self.original.miejsce_i_rok.split(" ")[:-1]).strip()
                if miejsce:
                    ret["publicationPlace"] = miejsce

        if hasattr(self.original, "wydawca"):
            if self.original.wydawca_id:
                ret["publisher"] = WydawcaPBNAdapter(
                    self.original.wydawca
                ).pbn_get_json()
            else:
                if self.original.wydawca_opis:
                    ret["publisher"] = {"name": self.original.wydawca_opis}

        ret["translation"] = self.get_translation()

        if hasattr(self.original, "wydawnictwo_nadrzedne_id"):
            if self.original.wydawnictwo_nadrzedne_id is not None:
                ret["book"] = WydawnictwoNadrzednePBNAdapter(
                    self.original.wydawnictwo_nadrzedne
                ).pbn_get_json()

        institutions = {}
        for jednostka in jednostki:
            institutions[jednostka.pbn_uid_id] = {
                "objectId": jednostka.pbn_uid_id,
                # "polonUuid": jednostka.pbn_uid.value("object", "polonUuid"),
                # "versionHash": jednostka.pbn_uid.value("object", "versionHash"),
            }
        ret["institutions"] = institutions

        return ret
