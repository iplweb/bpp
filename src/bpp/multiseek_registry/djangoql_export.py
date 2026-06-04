"""Konwersja formularza Multiseek -> zapytanie DjangoQL nad Rekord.

Czysta funkcja `multiseek_form_to_djangoql(form_json, registry)` chodzi po
ramkach `form_data` (jak multiseek.logic.get_query_recursive) i renderuje
liscie jako fragmenty DjangoQL. Domyslny dispatcher tlumaczy typowe pola;
pola trudne nadpisuja metode `to_djangoql(value, operation)`. Kazdy fragment
jest walidowany przeciw BppQLSchema(Rekord) — niepoprawne -> warning.
"""

from decimal import Decimal

from multiseek.logic import (
    CONTAINS,
    DIFFERENT_ALL,
    EQUALITY_OPS_ALL,
    GREATER_OPS_ALL,
    GREATER_OR_EQUAL_OPS_ALL,
    IN_RANGE,
    LESSER_OPS_ALL,
    LESSER_OR_EQUAL_OPS_ALL,
    NOT_CONTAINS,
    NOT_IN_RANGE,
    NOT_STARTS_WITH,
    STARTS_WITH,
)


def _build_scalar_op_map():
    diff_strs = {str(o) for o in DIFFERENT_ALL}
    m = {}
    for o in EQUALITY_OPS_ALL:
        key = str(o)
        m[key] = "!=" if key in diff_strs else "="
    for o in GREATER_OPS_ALL:
        m[str(o)] = ">"
    for o in GREATER_OR_EQUAL_OPS_ALL:
        m[str(o)] = ">="
    for o in LESSER_OPS_ALL:
        m[str(o)] = "<"
    for o in LESSER_OR_EQUAL_OPS_ALL:
        m[str(o)] = "<="
    m[str(CONTAINS)] = "~"
    m[str(NOT_CONTAINS)] = "!~"
    m[str(STARTS_WITH)] = "startswith"
    m[str(NOT_STARTS_WITH)] = "not startswith"
    return m


def scalar_operator_to_djangoql(operator):
    """DjangoQL-owy operator dla skalarnej operacji multiseek, lub None.

    Mapa jest budowana przy kazdym wywolaniu (tanio: ~20 wpisow), aby
    str() na stałych lazy-gettext rozwiazal sie pod AKTYWNYM jezykiem
    w momencie wywolania — identycznym z jezykiem formularza Multiseek.
    Cache bylby bledny: pierwszy call mrozi jezyk-kluczy na caly czas
    zycia procesu.
    """
    return _build_scalar_op_map().get(str(operator))


def range_operators() -> frozenset:
    """Zbior stringowych nazw operatorow zakresu pod aktywnym jezykiem.

    Analogicznie do scalar_operator_to_djangoql — budowane per-call,
    bez cache, aby lazy-gettext rozwiazalo sie pod biezacym jezykiem.
    """
    return frozenset({str(IN_RANGE), str(NOT_IN_RANGE)})


def render_value(value):
    """Literal DjangoQL dla wartosci skalarnej."""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, Decimal, float)):
        return str(value)
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'
