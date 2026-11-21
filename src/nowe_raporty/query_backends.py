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

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from flexible_reports import query_backends as fr

#: ``<pole>__rel`` albo ścieżka z kropką (``zrodlo.nazwa``) poza cudzysłowem —
#: znaki składni DjangoQL.
_SKLADNIA_DJANGOQL = re.compile(r"\w__rel\b|\b[a-z_]+\.[a-z_]+\b")

#: ``Unknown field: a__b`` w komunikacie DjangoQL — ścieżka w notacji ORM.
_NIEZNANE_POLE_ORM = re.compile(r"Unknown field: (\w+?)__(\w+)")

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
    def _schema(self):
        from bpp.djangoql_schema import BppQLSchema

        return BppQLSchema

    def filter_queryset(self, base_queryset, query, context=None):
        from djangoql.queryset import apply_search

        return apply_search(
            base_queryset, self._render(query, context), schema=self._schema()
        )

    def validate(self, query, model, context=None):
        # Kopia logiki z flexible_reports, ale na ``BppQLSchema``; komunikaty
        # zostają te same (tłumaczone przez flexible_reports).
        from djangoql.exceptions import DjangoQLError
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
            orm = _NIEZNANE_POLE_ORM.search(str(e))
            if orm and orm.group(2) != "rel":
                blad = _dopisz(
                    blad,
                    "W DjangoQL pola powiązanych obiektów zapisuje się "
                    f"z kropką, np. „{orm.group(1)}.{orm.group(2)}”, a obiekt "
                    f"z listy wybiera się przez „{orm.group(1)}__rel”.",
                )
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
