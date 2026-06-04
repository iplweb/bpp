"""Wspólny mixin DjangoQL dla adminów BPP.

Zbiera w jednym miejscu konfigurację, którą dotąd każdy admin powtarzał
(``djangoql_schema = BppQLSchema``) i włącza nowości z djangoql 0.25:

- ``djangoql_highlight = True`` — nakładka kolorująca składnię nad polem
  wyszukiwania (z czerwoną falką w miejscu błędu),
- ``multiline.js`` (Shift+Enter wstawia nową linię) ładuje się sam, gdy
  ``djangoql_completion`` jest włączone,
- rozbicie „dlaczego 0 wyników" (``djangoql_explain_empty``) jest domyślnie
  włączone w ``DjangoQLSearchMixin``.

Admin używa ``BppDjangoQLSearchMixin`` zamiast ``DjangoQLSearchMixin`` i nie
ustawia już ``djangoql_schema`` (chyba że potrzebuje innego schematu).
"""

from djangoql.admin import DjangoQLSearchMixin

from bpp.djangoql_schema import BppQLSchema


class BppDjangoQLSearchMixin(DjangoQLSearchMixin):
    """``DjangoQLSearchMixin`` ze wspólnym schematem BPP i włączoną nakładką
    podświetlania składni."""

    djangoql_schema = BppQLSchema
    djangoql_highlight = True
