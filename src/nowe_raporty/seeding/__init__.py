"""Idempotentny seed domyślnych definicji raportów.

Nie używa ``loaddata`` (robi INSERT-or-UPDATE po PK → nadpisałoby istniejące
dane). Zamiast tego ``get_or_create`` po naturalnym kluczu: ``slug`` dla
``Report``, ``label`` dla ``Table``/``Datasource``. Nigdy żadnego ``UPDATE``
ani ``delete`` — istniejące definicje są nietykane.

ContentType bazowego modelu (``bpp.Rekord``) pobieramy przez ``get_for_model``
— auto-tworzy wpis, więc seed jest odporny na kolejność handlerów
``post_migrate`` na świeżej bazie.
"""

from django.contrib.contenttypes.models import ContentType
from flexible_reports.models import (
    Column,
    ColumnOrder,
    Datasource,
    Report,
    ReportElement,
    Table,
)
from flexible_reports.models.report import (
    DATA_FROM_DATASOURCE,
    DATA_FROM_EXCEPT_CATCHALL,
)

from bpp.models.cache import Rekord

from . import definicje as d


def _rekord_ct():
    return ContentType.objects.get_for_model(Rekord)


def _ensure_tabela():
    """Zakłada wspólną tabelę z kolumnami; istniejącej (po label) nie tyka."""
    tabela, utworzona = Table.objects.get_or_create(
        label=d.TABELA_LABEL,
        defaults={
            "base_model": _rekord_ct(),
            "sort_option": d.TABELA["sort_option"],
            "attrs": d.TABELA["attrs"],
            "group_prefix": d.TABELA["group_prefix"],
            "empty_template": d.TABELA["empty_template"],
        },
    )
    if utworzona:
        kolumny = {}
        for kdef in d.KOLUMNY:
            kolumny[kdef["label"]] = Column.objects.create(parent=tabela, **kdef)
        for label, pozycja, malejaco in d.KOLEJNOSC:
            ColumnOrder.objects.create(
                table=tabela,
                column=kolumny[label],
                position=pozycja,
                desc=malejaco,
            )
    return tabela


def _ensure_datasource(label, dsl_query):
    datasource, _ = Datasource.objects.get_or_create(
        label=label,
        defaults={
            "base_model": _rekord_ct(),
            "dsl_query": dsl_query,
            "distinct": True,
        },
    )
    return datasource


def _datasource_dla(rodzaj, field):
    """Zwraca Datasource dla danej sekcji (wspólny albo per-obiekt 2.x)."""
    if rodzaj in d.WSPOLNE_DATASOURCE:
        label, query = d.WSPOLNE_DATASOURCE[rodzaj]
        return _ensure_datasource(label, query)

    label_bazowy, query_bazowe = d.DATASOURCE_2X_BAZA[rodzaj]
    label = f"{label_bazowy} - {d.OBJ_LABEL[field]}"
    query = query_bazowe + d.klauzula_obiektu(field)
    return _ensure_datasource(label, query)


def _utworz_raport(rdef, tabela):
    """Tworzy raport z sekcjami, jeśli nie istnieje. Zwraca True gdy utworzony."""
    report, utworzony = Report.objects.get_or_create(
        slug=rdef["slug"],
        defaults={"title": rdef["title"], "template": d.szablon(rdef["naglowek"])},
    )
    if not utworzony:
        return False

    for pozycja, (slug, tytul, rodzaj) in enumerate(d.SEKCJE):
        if rodzaj == "catchall":
            ReportElement.objects.create(
                parent=report,
                slug=slug,
                title=tytul,
                position=pozycja,
                data_from=DATA_FROM_EXCEPT_CATCHALL,
                datasource=None,
                base_model=_rekord_ct(),
                table=tabela,
            )
        else:
            ReportElement.objects.create(
                parent=report,
                slug=slug,
                title=tytul,
                position=pozycja,
                data_from=DATA_FROM_DATASOURCE,
                datasource=_datasource_dla(rodzaj, rdef["field"]),
                base_model=None,
                table=tabela,
            )
    return True


def seed_default_reports():
    """Zakłada brakujące domyślne raporty. Zwraca (utworzone, pominięte) slugi."""
    tabela = _ensure_tabela()
    utworzone, pominiete = [], []
    for rdef in d.RAPORTY:
        if _utworz_raport(rdef, tabela):
            utworzone.append(rdef["slug"])
        else:
            pominiete.append(rdef["slug"])
    return utworzone, pominiete
