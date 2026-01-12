from __future__ import annotations

from django.utils.functional import cached_property

from bpp import const
from bpp.const import TO_REDAKTOR, TO_REDAKTOR_TLUMACZENIA, TO_TLUMACZ
from bpp.models import BazaModeluOdpowiedzialnosciAutorow, Uczelnia
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.util import strip_html
from import_common.normalization import normalize_isbn, normalize_issn

from ..exceptions import (
    CharakterFormalnyMissingPBNUID,
    DaneLokalneWymagajaAktualizacjiException,
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


class OplataZaWydawnictwoPBNAdapter:
    def __init__(self, original: Wydawnictwo_Ciagle | Wydawnictwo_Zwarte):
        self.original = original

    def pbn_get_json(self):
        fee = {}

        if hasattr(self.original, "opl_pub_amount") and hasattr(
            self.original, "opl_pub_cost_free"
        ):
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

        return fee


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

        self.pbn_wysylaj_bez_oswiadczen = False

        if request is not None and uczelnia is None:
            uczelnia = Uczelnia.objects.get_for_request(request)

        if uczelnia is None:
            uczelnia = Uczelnia.objects.get_default()

        if uczelnia is not None:
            if uczelnia.pbn_api_nie_wysylaj_prac_bez_pk:
                self.export_pk_zero = False

            if uczelnia.pbn_wysylaj_bez_oswiadczen:
                self.pbn_wysylaj_bez_oswiadczen = True

        if export_pk_zero is not None:
            self.export_pk_zero = export_pk_zero

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

    def pbn_get_json_statements(self, _lst=None):
        """
        Extract and return only the discipline statements for this publication.

        Returns:
            list: List of statement dictionaries containing discipline information
        """
        statements = []

        if _lst is None:
            _lst = self.original.autorzy_set.all().select_related(
                "jednostka",
                "typ_odpowiedzialnosci",
                "dyscyplina_naukowa",
                "autor__pbn_uid",
                "autor",
            )

        for elem in _lst:
            statement = WydawnictwoAutorToStatementPBNAdapter(elem).pbn_get_json()
            if statement:
                statements.append(statement)
        return statements

    def pbn_get_api_statements(self):
        """
        Zwraca oświadczenia publikacji wraz z jej ID w formie słownika JSON który może być
        wysłany do API.
        """

        def _convert_stmt(statement):
            if "disciplineId" in statement and "disciplineUuid" in statement:
                del statement["disciplineId"]

            if "type" in statement:
                statement["personRole"] = statement.pop("type")

            statement.pop("personNaturalId", None)

            return statement

        publicationUuid = self.original.get_pbn_uuid()
        if not publicationUuid:
            raise DaneLokalneWymagajaAktualizacjiException(
                "Nie jestem w stanie ustalić lokalnie identyfikatora UUID dla publikacji "
                f"{self.original.pbn_uid}. Pobierz dane z profilu instytucji o publikacjach przez "
                f"API V2 przez CLI lub wyślij tą publikację w całości do PBN. ",
                self.original.pbn_uid,
            )

        return {
            "publicationUuid": str(publicationUuid),
            "statements": [
                _convert_stmt(stmt) for stmt in self.pbn_get_json_statements()
            ],
        }

    def _build_open_access_base_fields(self) -> dict:
        """Build base OpenAccess fields."""
        oa = {}
        if self.original.openaccess_wersja_tekstu_id is not None:
            oa["textVersion"] = self.original.openaccess_wersja_tekstu.skrot
        if self.original.openaccess_licencja_id is not None:
            oa["license"] = self.original.openaccess_licencja.skrot.replace("-", "_")
        if self.original.openaccess_czas_publikacji_id is not None:
            oa["releaseDateMode"] = self.original.openaccess_czas_publikacji.skrot
        return oa

    def _build_open_access_release_date(self, oa: dict) -> None:
        """Add release date fields to OpenAccess dict."""
        if self.original.public_dostep_dnia is not None:
            oa["releaseDate"] = str(self.original.public_dostep_dnia)
        elif self.original.dostep_dnia is not None:
            oa["releaseDate"] = str(self.original.dostep_dnia)

        if oa.get("releaseDate") is None:
            oa["releaseDateMonth"] = "JANUARY"
            oa["releaseDateYear"] = str(self.original.rok)

    def _build_open_access(self, pub_type: str) -> dict | None:
        """Build OpenAccess data structure if all required fields are present."""
        oa = self._build_open_access_base_fields()

        if oa.get("releaseDateMode") == "AFTER_PUBLICATION":
            if self.original.openaccess_ilosc_miesiecy is not None:
                oa["months"] = str(self.original.openaccess_ilosc_miesiecy)
            else:
                oa["months"] = "0"

        if self.original.openaccess_tryb_dostepu_id is not None:
            if pub_type == "ARTICLE":
                oa["modeArticle"] = self.original.openaccess_tryb_dostepu.skrot
            else:
                oa["modeMonograph"] = self.original.openaccess_tryb_dostepu.skrot

        self._build_open_access_release_date(oa)

        # Only return if all required fields present
        has_required = (
            oa.get("license")
            and oa.get("textVersion")
            and oa.get("modeArticle")
            and oa.get("releaseDateMode")
        )
        return oa if has_required else None

    def _build_pages(self) -> str | None:
        """Get pages from strony field or zakres_stron method."""
        if hasattr(self.original, "strony"):
            strony = self.original.strony
            if strony:
                return strony

        if hasattr(self.original, "zakres_stron"):
            zakres_stron = self.original.zakres_stron()
            if zakres_stron:
                return zakres_stron
        return None

    def _build_language_data(self, ret: dict) -> None:
        """Add mainLanguage and optionally originalLanguage to ret dict."""
        if self.original.jezyk.pbn_uid_id is None:
            raise LanguageMissingPBNUID(
                f'Język rekordu "{self.original.jezyk}" nie ma określonego '
                "odpowiednika w PBN"
            )

        ret["mainLanguage"] = self.original.jezyk.pbn_uid.code

        if self.original.jezyk_orig:
            if self.original.jezyk_orig.pbn_uid_id is None:
                raise LanguageMissingPBNUID(
                    f'Język *oryginalny* rekordu "{self.original.jezyk}" '
                    "nie ma określonego odpowiednika w PBN"
                )
            ret["originalLanguage"] = self.original.jezyk_orig.pbn_uid.code

    def _build_public_uri(self, ret: dict) -> None:
        """Determine and set public URI from www fields or parent publication."""
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
            ret["publicUri"] = (
                self.original.wydawnictwo_nadrzedne.public_www
                or self.original.wydawnictwo_nadrzedne.www
            )

    def _build_author_data(self, elem: BazaModeluOdpowiedzialnosciAutorow) -> dict:
        """Build author data dict for a single author record."""
        if elem.dyscyplina_naukowa_id is None or elem.przypieta is False:
            return AutorSimplePBNAdapter(elem.autor).pbn_get_json()
        return AutorZDyscyplinaPBNAdapter(elem.autor).pbn_get_json()

    def _add_author_affiliation(
        self, author: dict, elem: BazaModeluOdpowiedzialnosciAutorow, jednostki: set
    ) -> None:
        """Add affiliation to author dict and update jednostki set."""
        jednostka = elem.jednostka
        if not (
            elem.afiliuje and jednostka.pk != -1 and elem.jednostka.skupia_pracownikow
        ):
            return

        if self.always_affiliate_to_uid:
            author["affiliations"] = [self.always_affiliate_to_uid]
            jednostki.add(self.fake_jednostka)
        elif jednostka.pbn_uid_id is not None:
            author["affiliations"] = [jednostka.pbn_uid_id]
            jednostki.add(elem.jednostka)

    def _categorize_author(
        self,
        elem: BazaModeluOdpowiedzialnosciAutorow,
        author: dict,
        authors: list,
        editors: list,
        translators: list,
        translation_editors: list,
    ) -> None:
        """Categorize author into appropriate list based on responsibility type."""
        typ_ogolny = elem.typ_odpowiedzialnosci.typ_ogolny
        if typ_ogolny == const.TO_REDAKTOR:
            editors.append(author)
        elif typ_ogolny == const.TO_TLUMACZ:
            translators.append(author)
        elif typ_ogolny == const.TO_REDAKTOR_TLUMACZENIA:
            translation_editors.append(author)
        else:
            authors.append(author)

    def _build_authors_and_statements(self, ret: dict) -> set:
        """Build authors, editors, translators, statements. Returns jednostki set."""
        authors, editors, translators, translation_editors = [], [], [], []
        jednostki = set()

        _lst = self.original.autorzy_set.all().select_related()
        statements = self.pbn_get_json_statements(_lst)
        if statements:
            ret["statements"] = statements

        for elem in _lst:
            author = self._build_author_data(elem)
            self._add_author_affiliation(author, elem, jednostki)
            self._categorize_author(
                elem, author, authors, editors, translators, translation_editors
            )

        if authors:
            ret["authors"] = authors
        if translators:
            ret["translators"] = translators
        if editors:
            ret["editors"] = editors
        if translation_editors:
            ret["translationEditors"] = translation_editors

        return jednostki

    def _build_isbn(self) -> str | None:
        """Get normalized ISBN or e-ISBN."""
        if hasattr(self.original, "isbn"):
            if self.original.isbn:
                return normalize_isbn(self.original.isbn)
            elif hasattr(self.original, "e_isbn") and self.original.e_isbn:
                return normalize_isbn(self.original.e_isbn)
        return None

    def _build_issn(self) -> str | None:
        """Get normalized ISSN."""
        if hasattr(self.original, "issn") and self.original.issn:
            return normalize_issn(self.original.issn)
        return None

    def _build_issue(self) -> str | None:
        """Get issue number."""
        if hasattr(self.original, "numer_wydania"):
            nr_wydania = self.original.numer_wydania()
            if nr_wydania:
                return nr_wydania
        return None

    def _build_series_data(self, ret: dict) -> None:
        """Add series and numberInSeries to ret dict."""
        if hasattr(self.original, "seria_wydawnicza_id"):
            seria = self.original.seria_wydawnicza_id
            if seria is not None:
                ret["series"] = self.original.seria_wydawnicza.nazwa

        if hasattr(self.original, "numer_w_serii"):
            if self.original.numer_w_serii:
                ret["numberInSeries"] = self.original.numer_w_serii

    def _build_publication_place(self) -> str | None:
        """Extract publication place from miejsce_i_rok."""
        if hasattr(self.original, "miejsce_i_rok"):
            if self.original.miejsce_i_rok:
                miejsce = " ".join(self.original.miejsce_i_rok.split(" ")[:-1]).strip()
                if miejsce:
                    return miejsce
        return None

    def _build_publisher(self) -> dict | None:
        """Build publisher data structure."""
        if hasattr(self.original, "wydawca"):
            if self.original.wydawca_id:
                return WydawcaPBNAdapter(self.original.wydawca).pbn_get_json()
            else:
                if self.original.wydawca_opis:
                    return {"name": self.original.wydawca_opis}
        return None

    def _build_parent_publication(self, ret: dict) -> None:
        """Add book (parent publication) data to ret dict."""
        if hasattr(self.original, "wydawnictwo_nadrzedne_id"):
            if self.original.wydawnictwo_nadrzedne_id is not None:
                ret["book"] = WydawnictwoNadrzednePBNAdapter(
                    self.original.wydawnictwo_nadrzedne
                ).pbn_get_json()

        if ret.get("book") is None:
            if hasattr(self.original, "wydawnictwo_nadrzedne_w_pbn_id"):
                if self.original.wydawnictwo_nadrzedne_w_pbn_id is not None:
                    ret["book"] = {
                        "objectId": self.original.wydawnictwo_nadrzedne_w_pbn_id
                    }

    def _build_institutions(self, jednostki: set) -> dict | None:
        """Build institutions dictionary from jednostki set."""
        institutions = {}
        for jednostka in jednostki:
            institutions[jednostka.pbn_uid_id] = {
                "objectId": jednostka.pbn_uid_id,
            }
        return institutions if institutions else None

    def _build_keywords(self, main_language: str) -> list | None:
        """Build languageData keywords section."""
        if (
            hasattr(self.original, "slowa_kluczowe")
            and self.original.slowa_kluczowe.exists()
        ):
            slowa_kluczowe = list(
                self.original.slowa_kluczowe.all().values_list("name", flat=True)
            )
            return [{"keywords": slowa_kluczowe, "lang": main_language}]
        return None

    def _build_abstracts(self) -> list | None:
        """Build languageData abstracts section."""
        if not hasattr(self.original, "streszczenia"):
            return None
        if not self.original.streszczenia.exists():
            return None

        abstracts = []
        for streszczenie in self.original.streszczenia.all():
            if streszczenie.jezyk_streszczenia_id is None:
                streszczenie.jezyk_streszczenia = self.original.jezyk

            if (
                streszczenie.streszczenie is None
                or not streszczenie.streszczenie.strip()
            ):
                continue

            abstracts.append(
                {
                    "lang": streszczenie.jezyk_streszczenia.pbn_uid.code,
                    "text": streszczenie.streszczenie,
                }
            )
        return abstracts if abstracts else None

    def _build_language_data_extended(self, ret: dict) -> None:
        """Add keywords and abstracts to languageData in ret dict."""
        keywords = self._build_keywords(ret["mainLanguage"])
        if keywords:
            if "languageData" not in ret:
                ret["languageData"] = {}
            ret["languageData"]["keywords"] = keywords

        abstracts = self._build_abstracts()
        if abstracts:
            if "languageData" not in ret:
                ret["languageData"] = {}
            ret["languageData"]["abstracts"] = abstracts

    @staticmethod
    def _is_polish(skrot: str) -> bool:
        """Check if language abbreviation is Polish."""
        return skrot.lower().rstrip(".") in ("pol", "pl")

    def _build_evaluation_model_fields(self, ret: dict) -> None:
        """Add model-based PBN evaluation fields to ret dict."""
        field_mapping = [
            ("pbn_czy_projekt_fnp", "evaluationBookProjectFNP"),
            ("pbn_czy_projekt_ncn", "evaluationBookProjectNCN"),
            ("pbn_czy_projekt_nprh", "evaluationBookProjectNPHR"),
            ("pbn_czy_projekt_ue", "evaluationBookProjectUE"),
            ("pbn_czy_czasopismo_indeksowane", "evaluationIndexedJournal"),
            ("pbn_czy_artykul_recenzyjny", "evaluationIsReview"),
            ("pbn_czy_edycja_naukowa", "evaluationScientificEdition"),
        ]
        for model_field, json_field in field_mapping:
            value = getattr(self.original, model_field)
            if value is not None:
                ret[json_field] = value

    def _build_evaluation_translation_fields(self, ret: dict) -> None:
        """Add translation direction evaluation fields to ret dict."""
        if self.original.jezyk_orig_id is None:
            return

        jezyk_orig_kod = self.original.jezyk_orig.skrot
        jezyk_kod = self.original.jezyk.skrot
        orig_is_polish = self._is_polish(jezyk_orig_kod)
        current_is_polish = self._is_polish(jezyk_kod)

        if orig_is_polish and not current_is_polish:
            ret["evaluationTranslationFromPolish"] = True
        elif current_is_polish and not orig_is_polish:
            ret["evaluationTranslationToPolish"] = True

    def _build_evaluation_fields(self, ret: dict) -> None:
        """Add PBN/SEDN evaluation fields to ret dict."""
        self._build_evaluation_model_fields(ret)
        self._build_evaluation_translation_fields(ret)

        # evaluationWosConference: from konferencja.baza_wos
        if (
            hasattr(self.original, "konferencja_id")
            and self.original.konferencja_id is not None
            and self.original.konferencja.baza_wos
        ):
            ret["evaluationWosConference"] = True

    def _validate_export(self, ret: dict) -> None:
        """Final validation before export."""
        if ret["type"] not in [
            WydawnictwoPBNAdapter.ARTICLE,
            WydawnictwoPBNAdapter.CHAPTER,
        ]:
            return

        if self.export_pk_zero is False:
            if hasattr(self.original, "punkty_kbn"):
                if self.original.punkty_kbn == 0:
                    raise PKZeroExportDisabled(
                        "Eksport prac typu artykuł i typu rozdział z PK równym "
                        "zero jest wyłączony w konfiguracji systemu "
                        "(obiekt Uczelnia). "
                    )

        if not ret.get("statements") and not self.pbn_wysylaj_bez_oswiadczen:
            raise StatementsMissing(
                "Nie wyślę rekordu artykułu lub rozdziału bez zadeklarowanych "
                "oświadczeń autorów (dyscyplin). "
            )

    def _build_volume_pages_doi(self, ret: dict) -> None:
        """Add volume, pages, and DOI to ret dict."""
        if volume := self.nr_tomu():
            ret["volume"] = volume
        if pages := self._build_pages():
            ret["pagesFromTo"] = pages
        if self.original.doi:
            ret["doi"] = self.original.doi

    def _build_identifiers(self, ret: dict) -> None:
        """Add ISBN, ISSN, issue, and object ID to ret dict."""
        if isbn := self._build_isbn():
            ret["isbn"] = isbn
        if issn := self._build_issn():
            ret["issn"] = issn
        if issue := self._build_issue():
            ret["issue"] = issue
        if self.original.pbn_uid_id is not None:
            ret["objectId"] = self.original.pbn_uid_id

    def _build_publishing_info(self, ret: dict) -> None:
        """Add publication place, publisher, and translation to ret dict."""
        if place := self._build_publication_place():
            ret["publicationPlace"] = place
        if publisher := self._build_publisher():
            ret["publisher"] = publisher
        ret["translation"] = self.get_translation()

    def pbn_get_json(self):
        """Build and return JSON export data for PBN API."""
        ret = {
            "title": strip_html(self.original.tytul_oryginalny),
            "year": self.original.rok,
            "type": self.get_type(),
        }

        # Open Access
        if oa := self._build_open_access(ret["type"]):
            ret["openAccess"] = oa

        # Volume, pages, DOI
        self._build_volume_pages_doi(ret)

        # Language and URI
        self._build_language_data(ret)
        self._build_public_uri(ret)

        # Validate DOI or WWW exists
        if not ret.get("doi") and not ret.get("publicUri"):
            raise DOIorWWWMissing("Musi być DOI lub adres WWW")

        # Journal (for articles)
        if hasattr(self.original, "zrodlo"):
            ret["journal"] = ZrodloPBNAdapter(self.original.zrodlo).pbn_get_json()

        # Authors, editors, translators, statements
        jednostki = self._build_authors_and_statements(ret)

        # Identifiers and series
        self._build_identifiers(ret)
        self._build_series_data(ret)

        # Publishing info and parent publication
        self._build_publishing_info(ret)
        self._build_parent_publication(ret)

        # Institutions
        if institutions := self._build_institutions(jednostki):
            ret["institutions"] = institutions

        # Keywords and abstracts
        self._build_language_data_extended(ret)

        # Fee
        fee = OplataZaWydawnictwoPBNAdapter(self.original).pbn_get_json()
        if fee:
            ret["fee"] = fee

        # PBN evaluation fields and validation
        self._build_evaluation_fields(ret)
        self._validate_export(ret)

        return ret
