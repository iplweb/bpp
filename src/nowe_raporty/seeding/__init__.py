"""Idempotentny seed domyślnych definicji raportów.

Nie używa ``loaddata`` (robi INSERT-or-UPDATE po PK → nadpisałoby istniejące
dane). Zamiast tego ``get_or_create`` po naturalnym kluczu: ``slug`` dla
``Report``, ``label`` dla ``Table``/``Datasource``. Nigdy żadnego ``UPDATE``
ani ``delete`` — istniejące definicje są nietykane.

ContentType bazowego modelu (``bpp.Rekord``) pobieramy przez ``get_for_model``
— auto-tworzy wpis, więc seed jest odporny na kolejność handlerów
``post_migrate`` na świeżej bazie.
"""

from django.contrib.auth.models import Group
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

from bpp.const import GR_RAPORTY_WYSWIETLANIE
from bpp.models.cache import Rekord
from bpp.models.fields import OpcjaWyswietlaniaField
from nowe_raporty.models import DefinicjaRaportu

from . import definicje as d

# Mapowanie dawnej flagi Uczelnia.pokazuj_raport_* (OpcjaWyswietlaniaField) na
# uprawnienia DefinicjaRaportu: (poziom_dostepu, nazwa_grupy_lub_None, aktywny).
# Zachowuje 1:1 semantykę Uczelnia.sprawdz_uprawnienie (patrz test parytetu).
_OPCJA_NA_DOSTEP = {
    OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE: (
        DefinicjaRaportu.DOSTEP_WSZYSCY,
        None,
        True,
    ),
    OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM: (
        DefinicjaRaportu.DOSTEP_ZALOGOWANI,
        GR_RAPORTY_WYSWIETLANIE,
        True,
    ),
    OpcjaWyswietlaniaField.POKAZUJ_GDY_W_ZESPOLE: (
        DefinicjaRaportu.DOSTEP_STAFF,
        None,
        True,
    ),
    OpcjaWyswietlaniaField.POKAZUJ_NIGDY: (
        DefinicjaRaportu.DOSTEP_ZALOGOWANI,
        None,
        False,
    ),
}

# field (z definicje.RAPORTY) -> (poziom, atrybut flagi Uczelnia, kolejnosc menu)
_POZIOM_META = {
    None: (DefinicjaRaportu.POZIOM_UCZELNIA, "pokazuj_raport_uczelni", 0),
    "wydzial": (DefinicjaRaportu.POZIOM_WYDZIAL, "pokazuj_raport_wydzialow", 1),
    "jednostka": (DefinicjaRaportu.POZIOM_JEDNOSTKA, "pokazuj_raport_jednostek", 2),
    "autor": (DefinicjaRaportu.POZIOM_AUTOR, "pokazuj_raport_autorow", 3),
}


def _rekord_ct():
    return ContentType.objects.get_for_model(Rekord)


def _odczytaj_flage(attr):
    """Wartość flagi widoczności z istniejącej uczelni, lub domyślna pola."""
    from bpp.models import Uczelnia

    uczelnia = Uczelnia.objects.get_default()
    if uczelnia is not None:
        return getattr(uczelnia, attr)
    return Uczelnia._meta.get_field(attr).default


def _utworz_definicje(rdef, report):
    """Tworzy DefinicjaRaportu dla raportu, jeśli nie istnieje (po slug)."""
    if DefinicjaRaportu.objects.filter(slug=rdef["slug"]).exists():
        return
    poziom, attr_flagi, kolejnosc = _POZIOM_META[rdef["field"]]
    poziom_dostepu, nazwa_grupy, aktywny = _OPCJA_NA_DOSTEP.get(
        _odczytaj_flage(attr_flagi),
        (DefinicjaRaportu.DOSTEP_ZALOGOWANI, None, True),
    )
    definicja = DefinicjaRaportu.objects.create(
        nazwa=report.title or rdef["title"],
        slug=rdef["slug"],
        poziom=poziom,
        report=report,
        kolejnosc=kolejnosc,
        aktywny=aktywny,
        poziom_dostepu=poziom_dostepu,
    )
    if nazwa_grupy:
        definicja.wymagane_grupy.add(Group.objects.get_or_create(name=nazwa_grupy)[0])


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
    """Zakłada Report z sekcjami jeśli brak. Zwraca (report, czy_utworzony)."""
    report, utworzony = Report.objects.get_or_create(
        slug=rdef["slug"],
        defaults={"title": rdef["title"], "template": d.szablon(rdef["naglowek"])},
    )
    if not utworzony:
        return report, False

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
    return report, True


def seed_default_reports():
    """Zakłada brakujące domyślne raporty + ich DefinicjaRaportu (uprawnienia
    mapowane z Uczelnia.pokazuj_raport_*). Zwraca (utworzone, pominięte) slugi
    raportów. Idempotentne, nie nadpisuje istniejących."""
    tabela = _ensure_tabela()
    utworzone, pominiete = [], []
    for rdef in d.RAPORTY:
        report, utworzony = _utworz_raport(rdef, tabela)
        if utworzony:
            utworzone.append(rdef["slug"])
        else:
            pominiete.append(rdef["slug"])
        _utworz_definicje(rdef, report)
    return utworzone, pominiete
