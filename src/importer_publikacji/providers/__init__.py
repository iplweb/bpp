from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class InputMode:
    IDENTIFIER = "identifier"
    TEXT = "text"


@dataclass
class FetchedPublication:
    """Znormalizowane dane publikacji z dowolnego dostawcy."""

    raw_data: dict
    title: str
    doi: str | None = None
    year: int | None = None
    authors: list[dict] = field(default_factory=list)
    source_title: str | None = None
    source_abbreviation: str | None = None
    issn: str | None = None
    e_issn: str | None = None
    isbn: str | None = None
    e_isbn: str | None = None
    publisher: str | None = None
    publication_type: str | None = None
    language: str | None = None
    abstract: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    url: str | None = None
    license_url: str | None = None
    keywords: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    # Pola specyficzne dla patentów (biblatex ``@patent``) — wypełniane
    # best-effort, źródło jest z natury stratne (patrz handoff Track B).
    # Operator edytuje/uzupełnia je w wizardzie przed utworzeniem rekordu.
    patent_number: str | None = None
    patent_grant_number: str | None = None
    filing_date: str | None = None
    grant_date: str | None = None
    patent_type: str | None = None
    patent_holder: str | None = None
    jurisdiction: str | None = None


@dataclass
class SplitRecord:
    """Pojedynczy rekord wyodrębniony z surowego wejścia providera.

    ``ok is False`` oznacza fragment, który się nie sparsował (np. uszkodzony
    blok BibTeX) — niesiemy go dalej, żeby nic nie znikało po cichu.
    """

    raw: str
    ok: bool = True
    title: str = ""
    error: str = ""


class DataProvider(ABC):
    """Bazowa klasa abstrakcyjna dla dostawców danych."""

    # Uczelnia kontekstu (multi-hosted) — ustawiana przez ``get_provider``.
    # Dostawcy zależni od konfiguracji PBN (``PbnProvider``) czytają z niej
    # credentiale; dostawcy niezależni (CrossRef, DSpace) ignorują.
    uczelnia = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Nazwa dostawcy, np. 'CrossRef'."""

    @property
    @abstractmethod
    def identifier_label(self) -> str:
        """Etykieta pola identyfikatora, np. 'DOI'."""

    @property
    def choice_label(self) -> str:
        """Etykieta opcji na liście wyboru źródła danych.

        Domyślnie identyczna z ``name``, ale provider może ją nadpisać,
        żeby od razu podpowiedzieć operatorowi, czego dane źródło wymaga
        (np. „CrossRef — wyszukiwanie po numerze DOI"). Wartość opcji
        (``value`` radia) pozostaje równa ``name`` — zmienia się tylko
        tekst widoczny dla użytkownika."""
        return self.name

    @property
    def input_mode(self) -> str:
        return InputMode.IDENTIFIER

    @property
    def input_placeholder(self) -> str:
        return ""

    @property
    def input_help_text(self) -> str:
        return ""

    @property
    def icon(self) -> str:
        """Klasa ikony Foundation Icons (bez kropki), np. ``fi-link``.

        Używana na kaflu wyboru źródła na stronie głównej importera.
        Domyślna ikona generycznej „strony" — providery nadpisują ją
        czymś bardziej trafnym dla swojego źródła danych."""
        return "fi-page"

    @property
    def landing_caption(self) -> str:
        """Krótki podpis „co i skąd" pod kaflem wyboru źródła.

        Domyślnie to samo co ``input_help_text``, ale ten bywa długi/
        techniczny (patrz BibTeX, WWW) — providery mogą nadpisać
        zwięźlejszą, bardziej przystępną wersją."""
        return self.input_help_text

    def split_input(self, text: str) -> list["SplitRecord"]:
        """Rozbij surowe wejście na pojedyncze rekordy.

        Domyślnie provider jest jedno-rekordowy i zwraca wejście bez zmian.
        Providery wielo-rekordowe (BibTeX) nadpisują tę metodę.
        """
        return [SplitRecord(raw=text)]

    @abstractmethod
    def fetch(self, identifier: str) -> FetchedPublication | None:
        """Pobierz dane publikacji.
        Zwraca None jeśli nie znaleziono."""

    @abstractmethod
    def validate_identifier(self, identifier: str) -> str | None:
        """Waliduj i znormalizuj identyfikator.
        Zwraca znormalizowaną formę lub None jeśli
        niepoprawny."""


_providers: dict[str, type[DataProvider]] = {}


def register_provider(
    provider_cls: type[DataProvider],
):
    instance = provider_cls()
    _providers[instance.name] = provider_cls
    return provider_cls


def get_provider(name: str, uczelnia=None) -> DataProvider:
    provider = _providers[name]()
    provider.uczelnia = uczelnia
    return provider


def get_available_providers() -> list[str]:
    return list(_providers.keys())


def get_providers_metadata() -> dict[str, dict]:
    """Zwraca metadane providerów dla formularza."""
    result = {}
    for name, cls in _providers.items():
        instance = cls()
        result[name] = {
            "name": name,
            "choice_label": instance.choice_label,
            "identifier_label": instance.identifier_label,
            "input_mode": instance.input_mode,
            "input_placeholder": instance.input_placeholder,
            "input_help_text": instance.input_help_text,
            "icon": instance.icon,
            "landing_caption": instance.landing_caption,
        }
    return result
