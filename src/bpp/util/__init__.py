"""Facade re-exporting helpers split into submodules.

Każda funkcja/klasa zachowuje publiczną ścieżkę ``bpp.util.X`` — nowy kod
może importować z konkretnego podmodułu (``bpp.util.text``, ``bpp.util.orm``,
itp.), ale istniejące ``from bpp.util import X`` działa bez zmian.
"""

from bpp.util.algorithms import (
    DEC2INT,
    _build_knapsack_table,
    _reconstruct_knapsack_items,
    intsack,
    knapsack,
)
from bpp.util.bpp_specific import (
    crispy_form_html,
    dont_log_anonymous_crud_events,
    formdefaults_html_after,
    formdefaults_html_before,
    get_fixture,
    pbar,
    site_url_for_request,
    year_last_month,
)
from bpp.util.concurrency import (
    disable_multithreading_by_monkeypatching_pool,
    no_threads,
    partition,
    partition_count,
    partition_ids,
)
from bpp.util.orm import (
    FulltextSearchMixin,
    Getter,
    NewGetter,
    PerformanceFailure,
    fail_if_seq_scan,
    get_copy_from_db,
    get_original_object,
    has_changed,
    rebuild_contenttypes,
    rebuild_instances_of_models,
    remove_old_objects,
    set_seq,
    usun_nieuzywany_typ_charakter,
)
from bpp.util.text import (
    fulltext_tokenize,
    isbn_regex,
    non_url,
    safe_html,
    safe_html_defaults,
    safe_streszczenie_html,
    sanitize_multiseek_title,
    slugify_function,
    strip_extra_spaces,
    strip_extra_spaces_regex,
    strip_html,
    strip_nonalpha_regex,
    strip_nonalphanumeric,
    wytnij_isbn_z_uwag,
    zrob_cache,
)
from bpp.util.wyjatki import zaloguj_polkniety_wyjatek

# bpp.util jest importowany tranzytywnie przez niemal każdy moduł
# admin/models, więc eager ``from bpp.util.xlsx import ...`` wciągał openpyxl
# (a przez nie numpy — patrz openpyxl/compat/numbers.py: opcjonalny
# ``try: import numpy``) do KAŻDEGO procesu już na etapie ``django.setup()``,
# w tym do workera web/ASGI, który nigdy nie buduje arkusza.
#
# PEP 562 module-level ``__getattr__`` zachowuje publiczne
# ``from bpp.util import worksheet_columns_autosize`` (i ``import *`` via
# ``__all__``), ale odkłada import openpyxl/numpy do pierwszego faktycznego
# użycia którejś z funkcji xlsx. Zysk: ~kilkadziesiąt MB RSS na proces, który
# nigdy nie eksportuje xlsx (realizowany razem z worker admin-autodiscover skip).
# Guard: bpp/tests/test_imports/test_lazy_heavy_imports.py.
_XLSX_LAZY_NAMES = frozenset(
    {
        "_XLSX_FORMULA_INJECTION_LEAD",
        "_calculate_column_width",
        "_extract_hyperlink_text",
        "auto_fit_columns",
        "sanitize_xlsx_cell",
        "sanitize_xlsx_row",
        "worksheet_columns_autosize",
        "worksheet_create_table",
        "worksheet_create_urls",
    }
)


def __getattr__(name):
    # PEP 562: wołane tylko dla atrybutów nieznalezionych normalnym lookupem,
    # więc dostęp do już-zaimportowanych helperów (text/orm/...) jest bez zmian.
    if name in _XLSX_LAZY_NAMES:
        from bpp.util import xlsx

        return getattr(xlsx, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # algorithms
    "DEC2INT",
    "_build_knapsack_table",
    "_reconstruct_knapsack_items",
    "intsack",
    "knapsack",
    # bpp_specific
    "crispy_form_html",
    "dont_log_anonymous_crud_events",
    "formdefaults_html_after",
    "formdefaults_html_before",
    "get_fixture",
    "pbar",
    "site_url_for_request",
    "year_last_month",
    # concurrency
    "disable_multithreading_by_monkeypatching_pool",
    "no_threads",
    "partition",
    "partition_count",
    "partition_ids",
    # orm
    "FulltextSearchMixin",
    "Getter",
    "NewGetter",
    "PerformanceFailure",
    "fail_if_seq_scan",
    "get_copy_from_db",
    "get_original_object",
    "has_changed",
    "rebuild_contenttypes",
    "rebuild_instances_of_models",
    "remove_old_objects",
    "set_seq",
    "usun_nieuzywany_typ_charakter",
    # text
    "fulltext_tokenize",
    "isbn_regex",
    "non_url",
    "safe_html",
    "safe_html_defaults",
    "safe_streszczenie_html",
    "sanitize_multiseek_title",
    "slugify_function",
    "strip_extra_spaces",
    "strip_extra_spaces_regex",
    "strip_html",
    "strip_nonalpha_regex",
    "strip_nonalphanumeric",
    "wytnij_isbn_z_uwag",
    "zrob_cache",
    # wyjatki
    "zaloguj_polkniety_wyjatek",
    # xlsx
    "_XLSX_FORMULA_INJECTION_LEAD",
    "_calculate_column_width",
    "_extract_hyperlink_text",
    "auto_fit_columns",
    "sanitize_xlsx_cell",
    "sanitize_xlsx_row",
    "worksheet_columns_autosize",
    "worksheet_create_table",
    "worksheet_create_urls",
]
