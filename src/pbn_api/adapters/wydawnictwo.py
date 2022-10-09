from __future__ import annotations

from import_common.normalization import normalize_isbn, normalize_issn
from ..exceptions import (
    CharakterFormalnyMissingPBNUID,
    DOIorWWWMissing,
    LanguageMissingPBNUID,
    PKZeroExportDisabled,
    StatementsMissing,
)
from .autor import AutorSimplePBNAdapter, AutorZDyscyplinaPBNAdapter
from .wydawca import WydawcaPBNAdapter
from .wydawnictwo_autor import WydawnictwoAutorToStatementPBNAdapter
from .wydawnictwo_nadrzedne import WydawnictwoNadrzednePBNAdapter
from .zrodlo import ZrodloPBNAdapter

from django.utils.functional import cached_property

from bpp import const
from bpp.const import TO_REDAKTOR, TO_REDAKTOR_TLUMACZENIA, TO_TLUMACZ
from bpp.models import BazaModeluOdpowiedzialnosciAutorow, Uczelnia
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.util import strip_html


class WydawnictwoPBNAdapter:
    CHAPTER = "CHAPTER"
    BOOK = "BOOK"
    ARTICLE = "ARTICLE"
    EDITED_BOOK = "EDITED_BOOK"

    export_pk_zero = True
    always_affiliate_to_uid = None

    def __init__(
        self,
        original: Wydawnictwo_Ciagle | Wydawnictwo_Zwarte,
        request=None,
        uczelnia=None,
        export_pk_zero=None,
        always_affiliate_to_uid=None,
    ):
        """
        :param always_affiliate_to_uid: jeżeli podany, użyj właśnie tego UID jako UID jako
        każdej afiliacji we własnej jednostce (czyli w nie-obcej i zatrudniającej pracowników
        i gdzie autor ma afiliację). W ten sposób każdy autor, który afiliuje na jednostkę
        uczelni i jest w jednostce która skupia pracowników będzie miał wysłaną afiliację na
        uczelnię -- niezależnie od wypełnienia uid jednostki lub nie.
        """
        self.original = original

        if export_pk_zero is not None:
            self.export_pk_zero = export_pk_zero
        else:
            if request is not None and uczelnia is None:
                uczelnia = Uczelnia.objects.get_for_request(request)

            if uczelnia is not None:
                if uczelnia.pbn_api_nie_wysylaj_prac_bez_pk:
                    self.export_pk_zero = False

        if always_affiliate_to_uid is not None:
            self.always_affiliate_to_uid = always_affiliate_to_uid

            class FakeJednostka:
                pbn_uid_id = self.always_affiliate_to_uid

            self.fake_jednostka = FakeJednostka()

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
            return WydawnictwoPBNAdapter.ARTICLE
        elif self.original.charakter_formalny.rodzaj_pbn == const.RODZAJ_PBN_KSIAZKA:
            if self.pod_redakcja():
                return WydawnictwoPBNAdapter.EDITED_BOOK
            return WydawnictwoPBNAdapter.BOOK
        elif self.original.charakter_formalny.rodzaj_pbn == const.RODZAJ_PBN_ROZDZIAL:
            return WydawnictwoPBNAdapter.CHAPTER
        else:
            raise CharakterFormalnyMissingPBNUID(
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
            else:
                oa["months"] = "0"

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

        # Jeżeli pole "Strony" istnieje i ma jakąś wartość, to weź jego wartość
        if hasattr(self.original, "strony"):
            strony = self.original.strony
            if strony:
                ret["pagesFromTo"] = strony

        # Jeżeli pole "Strony" było puste a mamy funkcję "zakres_stron" i ono coś zwróci,
        # to weź tą wartość:
        if hasattr(self.original, "zakres_stron") and not ret.get("pagesFromTo"):
            zakres_stron = self.original.zakres_stron()
            if zakres_stron:
                ret["pagesFromTo"] = zakres_stron

        if self.original.doi:
            ret["doi"] = self.original.doi

        if self.original.jezyk.pbn_uid_id is None:
            raise LanguageMissingPBNUID(
                f'Język rekordu "{self.original.jezyk}" nie ma określonego odpowiednika w PBN'
            )

        ret["mainLanguage"] = self.original.jezyk.pbn_uid.code
        if self.original.jezyk_orig:

            if self.original.jezyk_orig.pbn_uid_id is None:
                raise LanguageMissingPBNUID(
                    f'Język *oryginalny* rekordu "{self.original.jezyk}" nie ma określonego odpowiednika w PBN'
                )

            ret["originalLanguage"] = self.original.jezyk_orig.pbn_uid.code

        if self.original.public_www:
            ret["publicUri"] = self.original.public_www
        elif self.original.www:
            ret["publicUri"] = self.original.www
        elif (
            ret["type"] == WydawnictwoPBNAdapter.CHAPTER
            and hasattr(self.original, "wydawnictwo_nadrzedne_id")
            and self.original.wydawnictwo_nadrzedne_id is not None
            and (
                self.original.wydawnictwo_nadrzedne.public_www
                or self.original.wydawnictwo_nadrzedne.www
            )
        ):
            # W sytuacji, gdy eksportujemy rozdział, jako adres WWW można spróbować użyć
            # adres WWW wydawnictwa nadrzędnego:
            ret["publicUri"] = (
                self.original.wydawnictwo_nadrzedne.public_www
                or self.original.wydawnictwo_nadrzedne.www
            )

        if not ret.get("doi") and not ret.get("publicUri"):
            raise DOIorWWWMissing("Musi być DOI lub adres WWW")

        if hasattr(self.original, "zrodlo"):
            ret["journal"] = ZrodloPBNAdapter(self.original.zrodlo).pbn_get_json()

        authors = []
        editors = []
        translators = []
        translationEditors = []
        statements = []
        jednostki = set()
        for elem in self.original.autorzy_set.all().select_related():
            elem: BazaModeluOdpowiedzialnosciAutorow
            #
            # Jeżeli dany rekord Wydawnictwo_..._Autor ma dyscyplinę, to takiego autora
            # eksportujemy 'w pełni' tzn ze wszystkimi posiadanymi przez niego identyfikatorami
            # typu PBN UID czy ORCID:
            #

            if elem.dyscyplina_naukowa_id is None or elem.przypieta is False:
                #
                # Autor nie ma dyscypliny lub ma odpiętą dyscyplinę -- prosty eksport w formacie imię + nazwisko
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
                if self.always_affiliate_to_uid:
                    author["affiliations"] = [self.always_affiliate_to_uid]
                    jednostki.add(self.fake_jednostka)
                else:
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
            elif hasattr(self.original, "e_isbn"):
                # Jeżeli nie ma ISBN a jest wartość w polu E-ISBN, to użyj jej:
                if self.original.e_isbn:
                    ret["isbn"] = normalize_isbn(self.original.e_isbn)

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
        if institutions:
            ret["institutions"] = institutions

        if (
            hasattr(self.original, "slowa_kluczowe")
            and self.original.slowa_kluczowe.exists()
        ):
            if "languageData" not in ret:
                ret["languageData"] = {}

            slowa_kluczowe = list(
                self.original.slowa_kluczowe.all().values_list("name", flat=True)
            )
            # Zakładamy, że wszystkie słowa kluczowe są w języku rekordu nadrzędnego
            ret["languageData"]["keywords"] = [
                {"keywords": slowa_kluczowe, "lang": ret["mainLanguage"]}
            ]

        if hasattr(self.original, "streszczenia"):
            if "languageData" not in ret:
                ret["languageData"] = {}

            if self.original.streszczenia.exists():
                ret["languageData"]["abstracts"] = []

                for streszczenie in self.original.streszczenia.all():
                    if streszczenie.jezyk_streszczenia_id is None:
                        streszczenie.jezyk_streszczenia = self.original.jezyk

                    if (
                        streszczenie.streszczenie is None
                        or not streszczenie.streszczenie.strip()
                    ):
                        continue

                    ret["languageData"]["abstracts"].append(
                        {
                            "lang": streszczenie.jezyk_streszczenia.pbn_uid.code,
                            "text": streszczenie.streszczenie,
                        }
                    )

        if hasattr(self.original, "opl_pub_amount") and hasattr(
            self.original, "opl_pub_cost_free"
        ):
            # ModelZOplataZaPublikacje
            fee = {}

            if self.original.opl_pub_cost_free is True:
                fee["amount"] = 0
                fee["costFreePublication"] = True
                fee["other"] = False
                fee["researchOrDevelopmentProjectsFinancialResources"] = False
                fee["researchPotentialFinancialResources"] = False

            if (
                self.original.opl_pub_amount is not None
                and self.original.opl_pub_amount > 0
            ):
                fee["amount"] = str(self.original.opl_pub_amount)
                fee["costFreePublication"] = False
                fee["other"] = self.original.opl_pub_other or False
                fee["researchOrDevelopmentProjectsFinancialResources"] = (
                    self.original.opl_pub_research_or_development_projects or False
                )
                fee["researchPotentialFinancialResources"] = (
                    self.original.opl_pub_research_potential or False
                )

            if fee:
                ret["fee"] = fee

        if ret["type"] in [
            WydawnictwoPBNAdapter.ARTICLE,
            WydawnictwoPBNAdapter.CHAPTER,
        ]:

            if self.export_pk_zero is False:
                if hasattr(self.original, "punkty_kbn"):
                    if self.original.punkty_kbn == 0:
                        raise PKZeroExportDisabled(
                            "Eksport prac typu artykuł i typu rozdział z PK równym zero jest wyłączony w konfiguracji "
                            "systemu (obiekt Uczelnia). "
                        )

            if not ret.get("statements"):
                raise StatementsMissing(
                    "Nie wyślę rekordu artykułu lub rozdziału bez zadeklarowanych oświadczeń autorów (dyscyplin). "
                )

        return ret
