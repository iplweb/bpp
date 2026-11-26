"""Backendy zapytań ``flexible_reports`` dopasowane do BPP (FD#523).

``flexible_reports`` filtruje źródła danych (``Datasource``) DjangoQL-em na
DOMYŚLNYM schemacie djangoql. W BPP wszędzie indziej (wyszukiwanie
zapytaniem, adminy, eksport multiseek→DjangoQL) obowiązuje ``BppQLSchema`` —
z pickerami ``<pole>__rel`` (np. ``charakter_formalny__rel = "Artykuł [5]"``),
agregatami i bez pól z poświadczeniami. Zapytanie skopiowane stamtąd do źródła
danych raportu nie przechodziło walidacji („Unknown field:
charakter_formalny__rel"). Podmieniamy backend DjangoQL na wariant
z ``BppQLSchema`` — ten sam schemat przy walidacji i przy generowaniu raportu.

Dodatkowo oba backendy dopisują do błędu walidacji podpowiedź, gdy zapytanie
wygląda na składnię DRUGIEGO języka (``__rel``/kropka w django-dsl,
``pole__podpole`` w DjangoQL) — to najczęstsza przyczyna odrzucenia.
"""

import logging
import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from flexible_reports import query_backends as fr

#: ``<pole>__rel`` albo ścieżka z kropką (``zrodlo.nazwa``) poza cudzysłowem —
#: znaki składni DjangoQL.
_SKLADNIA_DJANGOQL = re.compile(r"\w__rel\b|\b[a-z_]+\.[a-z_]+\b")

logger = logging.getLogger(__name__)

_REL = "__rel"

PODPOWIEDZ_DSL = (
    "Zapytanie wygląda na składnię DjangoQL (pole „…__rel” albo ścieżka "
    "z kropką, np. „charakter_formalny.skrot”). Zmień „Query language” "
    "na „DjangoQL” albo zapisz pole w notacji django-dsl, np. "
    "„charakter_formalny__skrot”."
)


def _bez_napisow(query):
    """Zapytanie bez literałów w cudzysłowach i bez tagów szablonu
    (``{{ obiekt.pk }}``) — kropki/``__`` w nich nie mogą udawać składni."""
    query = re.sub(r"\{\{.*?\}\}|\{%.*?%\}", "", query or "", flags=re.S)
    return re.sub(r'"(?:[^"\\]|\\.)*"', '""', query)


def podpowiedz_notacja_orm(nazwa):
    """Podpowiedź dla nieznanego pola DjangoQL zapisanego w notacji ORM.

    ``nazwa`` to nazwa pola z wyjątku (``DjangoQLSchemaError.value``), a NIE
    tekst komunikatu — ten bywa przetłumaczony („Nieznane pole: …").
    ``autorzy__autor__nazwisko`` → ``autorzy.autor.nazwisko`` (+ picker
    ``autorzy.autor__rel``); końcowe ``__rel`` zostaje na miejscu.
    Zwraca ``None``, gdy nazwa nie wygląda na ścieżkę ORM.
    """
    if not nazwa or not isinstance(nazwa, str):
        return None
    rel = _REL if nazwa.endswith(_REL) else ""
    czesci = nazwa[: len(nazwa) - len(rel)].split("__")
    if len(czesci) < 2 or not all(czesci):
        return None
    tekst = (
        "W DjangoQL pola powiązanych obiektów zapisuje się z kropką: zamiast "
        f"„{nazwa}” wpisz „{'.'.join(czesci)}{rel}”."
    )
    if not rel:
        tekst += (
            " Konkretny obiekt z listy wybiera się końcówką „__rel”, np. "
            f"„{'.'.join(czesci[:-1])}{_REL}”."
        )
    return tekst


class BladZapytaniaZrodlaDanych(Exception):
    """Zapisane zapytanie źródła danych nie daje się wykonać przy generowaniu
    raportu (np. pole zniknęło ze schematu po aktualizacji). Widok raportu
    zamienia go na czytelny komunikat zamiast błędu 500."""

    def __init__(self, query, blad):
        self.query = query
        self.blad = blad
        super().__init__(f"{blad} (zapytanie: {query!r})")


def _dopisz(error, podpowiedz):
    """Nowy ``ValidationError`` dla ``dsl_query``: oryginał + podpowiedź."""
    komunikaty = list(error.message_dict.get("dsl_query", error.messages))
    return ValidationError({"dsl_query": [*komunikaty, podpowiedz]})


class BppDSLQueryBackend(fr.DSLQueryBackend):
    def validate(self, query, model, context=None):
        try:
            super().validate(query, model, context=context)
        except ValidationError as e:
            if _SKLADNIA_DJANGOQL.search(_bez_napisow(query)):
                raise _dopisz(e, PODPOWIEDZ_DSL) from e
            raise


class BppDjangoQLQueryBackend(fr.DjangoQLQueryBackend):
    def get_schema_class(self):
        # Hak ``flexible_reports``: z tego samego schematu korzysta edytor
        # zapytań w formularzu źródła danych (podpowiadanie pól — FD#521),
        # więc podpowiada dokładnie to, co przechodzi walidację.
        from bpp.djangoql_schema import BppQLSchema

        return BppQLSchema

    def _schema(self):
        return self.get_schema_class()

    def filter_queryset(self, base_queryset, query, context=None):
        from djangoql.exceptions import DjangoQLError
        from djangoql.queryset import apply_search

        rendered = self._render(query, context)
        try:
            return apply_search(base_queryset, rendered, schema=self._schema())
        except DjangoQLError as e:
            # Zapytanie zapisane wcześniej, którego schemat już nie przyjmuje
            # (albo model bazowy wycięty ze schematu) — logujemy z tracebackiem
            # i zgłaszamy błąd, który widok raportu pokaże jako komunikat.
            logger.exception(
                "Źródło danych raportu: niepoprawne zapytanie DjangoQL %r", rendered
            )
            raise BladZapytaniaZrodlaDanych(rendered, e) from e

    def validate(self, query, model, context=None):
        # Kopia logiki z flexible_reports, ale na ``BppQLSchema``; komunikaty
        # zostają te same (tłumaczone przez flexible_reports).
        from djangoql.exceptions import DjangoQLError, DjangoQLSchemaError
        from djangoql.queryset import apply_search

        fr._check_not_empty(query)
        rendered = self._render(query, context)
        try:
            apply_search(model.objects.all(), rendered, schema=self._schema()).first()
        except DjangoQLError as e:
            blad = ValidationError(
                {
                    "dsl_query": [
                        ValidationError(
                            _("DjangoQL query is invalid (%(error)s)"),
                            params={"error": e},
                        )
                    ]
                }
            )
            podpowiedz = (
                podpowiedz_notacja_orm(e.value)
                if isinstance(e, DjangoQLSchemaError)
                else None
            )
            if podpowiedz:
                blad = _dopisz(blad, podpowiedz)
            raise blad from e
        except Exception as e:
            # Błąd samego zapytania SQL (np. niepoprawny typ wartości) —
            # zgłaszamy go jako błąd walidacji formularza, jak flexible_reports.
            raise ValidationError(
                {
                    "dsl_query": [
                        ValidationError(
                            _(
                                "An error occured while trying to run the actual "
                                "database query (%(error)s)"
                            ),
                            params={"error": e},
                        )
                    ]
                }
            ) from e


def zainstaluj():
    """Podmień backendy w rejestrze ``flexible_reports`` (idempotentne)."""
    fr.BACKENDS[fr.DSL] = BppDSLQueryBackend()
    fr.BACKENDS[fr.DJANGOQL] = BppDjangoQLQueryBackend()
