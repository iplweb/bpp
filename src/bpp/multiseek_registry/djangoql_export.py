"""Konwersja formularza Multiseek -> zapytanie DjangoQL nad Rekord.

Czysta funkcja `multiseek_form_to_djangoql(form_json, registry)` chodzi po
ramkach `form_data` (jak multiseek.logic.get_query_recursive) i renderuje
liscie jako fragmenty DjangoQL. Domyslny dispatcher tlumaczy typowe pola;
pola trudne nadpisuja metode `to_djangoql(value, operation)`. Kazdy fragment
jest walidowany przeciw BppQLSchema(Rekord) — niepoprawne -> warning.
"""

import logging
from decimal import Decimal

from djangoql.parser import DjangoQLParser
from multiseek.logic import (
    AUTOCOMPLETE,
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

from bpp.djangoql_schema import BppQLSchema
from bpp.models import Rekord

logger = logging.getLogger(__name__)

# Schema introspekcja jest kosztowna (rekursywny obchod grafu modeli) i bezstanowa
# po zbudowaniu -> jeden wspoldzielony singleton. Parser tworzymy per-call
# (wspoldzielony lexer nie jest thread-safe pod wielowatkowym WSGI).
_REKORD_SCHEMA = BppQLSchema(Rekord)


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


def _orm_path_to_djangoql(field_name):
    """field_name multiseek (ORM, '__') -> sciezka DjangoQL ('.')."""
    return field_name.replace("__", ".")


def is_valid_rekord_djangoql(fragment):
    """Czy fragment parsuje sie i waliduje wzgledem BppQLSchema(Rekord)."""
    try:
        ast = DjangoQLParser().parse(fragment)
        _REKORD_SCHEMA.validate(ast)
    except Exception:  # noqa: BLE001 — best-effort validity gate (klasyfikuje, nie tlumi)
        return False
    return True


def _autocomplete_leaf(field, value, operation):
    """value to pk; resolwujemy obiekt i emitujemy '<sciezka>__rel = "L [pk]"'."""
    op = str(operation)
    diff_strs = {str(o) for o in DIFFERENT_ALL}
    equal_strs = {str(o) for o in EQUALITY_OPS_ALL} - diff_strs
    if op in diff_strs:
        rel_op = "!="
    elif op in equal_strs:
        rel_op = "="
    else:
        return None
    try:
        obj = field.value_from_web(value)
    except Exception:  # noqa: BLE001 — nieoczekiwany blad resolucji pk -> nieprzekladalne
        logger.debug(
            "value_from_web zawiodlo dla pola %r (value=%r)",
            getattr(field, "label", field),
            value,
            exc_info=True,
        )
        return None
    if obj is None:
        return None
    rel_path = _orm_path_to_djangoql(field.field_name) + "__rel"
    label = str(obj).replace("\\", "\\\\").replace('"', '\\"')
    return f'{rel_path} {rel_op} "{label} [{obj.pk}]"'


def _range_leaf(name, value, operation):
    """IN_RANGE/NOT_IN_RANGE: value to [low, high]."""
    if not (isinstance(value, (list, tuple)) and len(value) == 2):
        return None
    if str(operation) == str(NOT_IN_RANGE):
        return None  # brak unary not(...) w DjangoQL -> warning (Task 5/6)
    low, high = value
    path = _orm_path_to_djangoql(name)
    return f"({path} >= {render_value(low)} and {path} <= {render_value(high)})"


def _default_leaf(field, value, operation):
    op = str(operation)
    if getattr(field, "type", None) == AUTOCOMPLETE:
        return _autocomplete_leaf(field, value, operation)
    name = getattr(field, "field_name", None)
    if not name:
        return None
    if op in range_operators():
        return _range_leaf(name, value, operation)
    dql_op = scalar_operator_to_djangoql(op)
    if dql_op is None:
        return None
    return f"{_orm_path_to_djangoql(name)} {dql_op} {render_value(value)}"


def leaf_to_djangoql(registry, leaf):
    """Fragment DjangoQL dla pojedynczego warunku, albo None (nieprzekladalny).

    None gdy: nieznane pole, nieobslugiwana operacja, albo fragment nie
    waliduje sie wzgledem schematu Rekord.
    """
    field = registry.field_by_name.get(leaf["field"])
    if field is None:
        return None
    override = getattr(field, "to_djangoql", None)
    if callable(override):
        frag = override(leaf["value"], leaf["operator"])
    else:
        frag = _default_leaf(field, leaf["value"], leaf["operator"])
    if frag is None:
        return None
    return frag if is_valid_rekord_djangoql(frag) else None
