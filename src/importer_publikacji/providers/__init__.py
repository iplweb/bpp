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


class DataProvider(ABC):
    """Bazowa klasa abstrakcyjna dla dostawców danych."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nazwa dostawcy, np. 'CrossRef'."""

    @property
    @abstractmethod
    def identifier_label(self) -> str:
        """Etykieta pola identyfikatora, np. 'DOI'."""

    @property
    def input_mode(self) -> str:
        return InputMode.IDENTIFIER

    @property
    def input_placeholder(self) -> str:
        return ""

    @property
    def input_help_text(self) -> str:
        return ""

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


def get_provider(name: str) -> DataProvider:
    return _providers[name]()


def get_available_providers() -> list[str]:
    return list(_providers.keys())


def get_providers_metadata() -> dict[str, dict]:
    """Zwraca metadane providerów dla formularza."""
    result = {}
    for name, cls in _providers.items():
        instance = cls()
        result[name] = {
            "name": name,
            "identifier_label": instance.identifier_label,
            "input_mode": instance.input_mode,
            "input_placeholder": instance.input_placeholder,
            "input_help_text": instance.input_help_text,
        }
    return result
