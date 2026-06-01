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
    slugify_function,
    strip_extra_spaces,
    strip_extra_spaces_regex,
    strip_html,
    strip_nonalpha_regex,
    strip_nonalphanumeric,
    wytnij_isbn_z_uwag,
    zrob_cache,
)
from bpp.util.xlsx import (
    _XLSX_FORMULA_INJECTION_LEAD,
    _calculate_column_width,
    _extract_hyperlink_text,
    auto_fit_columns,
    sanitize_xlsx_cell,
    sanitize_xlsx_row,
    worksheet_columns_autosize,
    worksheet_create_table,
    worksheet_create_urls,
)

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
    "slugify_function",
    "strip_extra_spaces",
    "strip_extra_spaces_regex",
    "strip_html",
    "strip_nonalpha_regex",
    "strip_nonalphanumeric",
    "wytnij_isbn_z_uwag",
    "zrob_cache",
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
