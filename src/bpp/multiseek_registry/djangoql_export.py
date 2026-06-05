"""Konwersja formularza Multiseek -> zapytanie DjangoQL nad Rekord.

Czysta funkcja `multiseek_form_to_djangoql(form_json, registry)` chodzi po
ramkach `form_data` (jak multiseek.logic.get_query_recursive) i renderuje
liscie jako fragmenty DjangoQL. Domyslny dispatcher tlumaczy typowe pola;
pola trudne nadpisuja metode `to_djangoql(value, operation)`. Kazdy fragment
jest walidowany przeciw BppQLSchema(Rekord) — niepoprawne -> warning.
"""

import logging
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from decimal import Decimal
from urllib.parse import urlencode

from django.urls import reverse
from djangoql.parser import DjangoQLParser
from multiseek.logic import (
    AND,
    ANDNOT,
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
    OR,
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


def _orm_name(field):
    """Realna ścieżka ORM pola: djangoql_field_name (override) albo field_name."""
    return getattr(field, "djangoql_field_name", None) or getattr(
        field, "field_name", None
    )


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
    name = _orm_name(field)
    if not name:
        return None
    rel_path = _orm_path_to_djangoql(name) + "__rel"
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
    name = _orm_name(field)
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
    if not isinstance(leaf, dict):
        return None
    field = registry.field_by_name.get(leaf.get("field"))
    if field is None:
        return None
    value = leaf.get("value")
    operation = leaf.get("operator")
    if operation is None:
        return None
    override = getattr(field, "to_djangoql", None)
    if callable(override):
        frag = override(value, operation)
    else:
        frag = _default_leaf(field, value, operation)
    if frag is None:
        return None
    return frag if is_valid_rekord_djangoql(frag) else None


@dataclass
class ConversionResult:
    query: str
    warnings: list = dataclass_field(default_factory=list)

    @property
    def editor_url(self):
        base = reverse("bpp:zapytanie")
        if not self.query:
            return f"{base}?{urlencode({'model': 'rekord'})}"
        return f"{base}?{urlencode({'model': 'rekord', 'query': self.query})}"


def _logical_keyword(prev_op):
    """'and'/'or' dla operatora laczacego multiseek; None gdy nie AND/OR.

    AND/OR to zwykle stringi w multiseek.logic; str() jest defensywne,
    nie lokalizacyjne.
    """
    s = str(prev_op)
    if s == str(AND):
        return "and"
    if s == str(OR):
        return "or"
    return None


def _is_andnot(prev_op):
    return prev_op is not None and str(prev_op) == str(ANDNOT)


def _leaf_label(leaf):
    return f"{leaf.get('field')} {leaf.get('operator')}".strip()


def _join_parts(parts):
    """Łączy fragmenty LEWOSTRONNIE, zgodnie z multiseek (ret = ret & q / | q).

    DjangoQL daje `and` wyższy priorytet niż `or`, więc płaskie złączenie
    `A or B and C` znaczyłoby `A or (B and C)`. Multiseek liczy `(A or B) and C`.
    Dlatego nawiasujemy lewy akumulator, gdy dołączamy `and`, a akumulator ma
    na szczycie `or`. Czysty łańcuch `and`/`or` zostaje bez zbędnych nawiasów.
    parts: list[(joiner, fragment)]; joiner pierwszego elementu jest ignorowany,
    a `frag` to atom (pojedyncze porównanie) albo już-nawiasowana podramka.
    """
    if not parts:
        return ""
    out = parts[0][1]
    has_top_or = False
    for joiner, frag in parts[1:]:
        j = joiner or "and"
        if j == "and" and has_top_or:
            out = f"({out})"
            has_top_or = False
        out = f"{out} {j} {frag}"
        if j == "or":
            has_top_or = True
    return out


_INVERT = {
    "=": "!=",
    "!=": "=",
    "~": "!~",
    "!~": "~",
    ">": "<=",
    ">=": "<",
    "<": ">=",
    "<=": ">",
    "startswith": "not startswith",
    "not startswith": "startswith",
}


def _invert_fragment(frag):
    """Zaneguj fragment-liścia podmieniając operator (De Morgan na pojedynczym
    porównaniu). Zwraca zanegowany fragment albo None, gdy się nie da.

    Fragmenty złożone (zakres `(a >= x and a <= y)`, grupy) nie podlegają
    prostej inwersji operatora -> None. Operator jest zakotwiczony tuż za LHS
    (ścieżka pola nie zawiera spacji), więc znaki operatorowe wewnątrz wartości
    (np. `~ "a = b"`) nie mylą parsera.
    """
    if frag.startswith("("):
        return None
    try:
        lhs, rest = frag.split(" ", 1)
    except ValueError:
        return None
    for op in sorted(_INVERT, key=len, reverse=True):
        prefix = op + " "
        if rest.startswith(prefix):
            return f"{lhs} {_INVERT[op]} {rest[len(prefix) :]}"
    return None


def _append_leaf(registry, leaf, parts, warnings):
    prev_op = leaf.get("prev_op")
    if _is_andnot(prev_op):
        frag = leaf_to_djangoql(registry, leaf)
        if frag is None:
            warnings.append(
                f"Pominięto zanegowany warunek: {_leaf_label(leaf)} (nieprzekładalny)"
            )
            return
        inverted = _invert_fragment(frag)
        if inverted is None:
            warnings.append(
                f"Pominięto zanegowany warunek: {_leaf_label(leaf)} "
                "(nie da się odwrócić operatora)"
            )
            return
        parts.append(("and", inverted))
        return
    frag = leaf_to_djangoql(registry, leaf)
    if frag is None:
        warnings.append(f"Pominięto warunek: {_leaf_label(leaf)} (nieprzekładalny)")
        return
    kw = _logical_keyword(prev_op)
    if prev_op is not None and kw is None:
        warnings.append(
            f"Nieznany operator łączący {prev_op!r} dla: {_leaf_label(leaf)} "
            "— przyjęto 'and'"
        )
    parts.append((kw, frag))


def _append_subframe(registry, subframe, parts, warnings):
    prev_op = subframe[0] if subframe else None
    if _is_andnot(prev_op):
        warnings.append(
            "Pominięto zanegowaną grupę warunków (DjangoQL nie ma `not(...)`)"
        )
        return
    sub = _walk_frame(registry, subframe, warnings)
    if not sub:
        return
    kw = _logical_keyword(prev_op)
    if prev_op is not None and kw is None:
        warnings.append(
            f"Nieznany operator łączący {prev_op!r} dla grupy warunków — przyjęto 'and'"
        )
    parts.append((kw, f"({sub})"))


def _walk_frame(registry, frame, warnings):
    """Zwraca fragment DjangoQL dla ramki (lub '' gdy nic przekladalnego).

    frame[0] to operator ramki (lub None); frame[1:] to liscie/podramki.
    """
    parts = []
    for idx, element in enumerate(frame):
        if idx == 0:
            continue
        if isinstance(element, dict):
            _append_leaf(registry, element, parts, warnings)
        elif isinstance(element, list):
            _append_subframe(registry, element, parts, warnings)
    return _join_parts(parts)


def multiseek_form_to_djangoql(form_json, registry):
    """Glowne API: dict z 'form_data' -> ConversionResult(query, warnings)."""
    warnings = []
    form_data = form_json.get("form_data") or [None]
    query = _walk_frame(registry, form_data, warnings)
    return ConversionResult(query=query, warnings=warnings)
