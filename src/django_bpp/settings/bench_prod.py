"""Wariant benchmarku z PRODUKCYJNYMI regułami cacheops.

Używany przez skrypty w ``bench/``. Konfiguracja DEV-ONLY.

Po co osobny wariant: ``local.py`` (a więc i ``bench.py``) NIE definiuje
``CACHEOPS`` wcale, więc cacheops jest w ``INSTALLED_APPS``, ale nie
cache'uje niczego. Produkcja definiuje reguły m.in. dla ``bpp.uczelnia``,
``bpp.jednostka``, ``bpp.tytul`` i pozostałych słowników — a to DOKŁADNIE
te modele, w które uderzają znalezione N+1 (``Jednostka.__str__`` →
``self.uczelnia``, ``Autor.__str__`` → ``self.tytul``).

Pomiar bez tych reguł ZAWYŻA zysk z ``FETCH_PEERS``: liczy jako zapytania
do PostgreSQL coś, co na produkcji jest trafieniem w Redisa. Dlatego
mierzymy oba warianty i raportujemy oba.

Reguły są WYCIĄGANE Z ``production.py`` przez AST, a nie przepisane —
kopia rozjechałaby się z produkcją przy pierwszej zmianie reguł, a wtedy
benchmark mierzyłby konfigurację, której nikt nie ma. Nie importujemy
``production.py`` wprost, bo jego zaimportowanie wykonuje cały moduł
(strażnik ``SECRET_KEY``, ``ALLOWED_HOSTS`` z env itd.).
"""

import ast
import pathlib

from .bench import *  # noqa
from .bench import CACHES  # noqa

_PRODUCTION_PY = pathlib.Path(__file__).with_name("production.py")


class _ZlozStale(ast.NodeTransformer):
    """Zamień arytmetykę na stałych w jedną stałą (``60 * 60`` → ``3600``).

    Potrzebne, bo ``CACHEOPS_DEFAULTS = {"timeout": 60 * 60}`` w
    ``production.py`` to ``BinOp``, a ``ast.literal_eval`` przyjmuje wyłącznie
    literały i odrzuca go (``malformed node or string``). Składamy więc stałe
    sami — dzięki temu NIE musimy sięgać po ``eval``/``compile``: po tym
    przejściu drzewo jest już czystym literałem.

    Świadomie obsługujemy tylko cztery operatory arytmetyczne i wyłącznie na
    liczbach. Cokolwiek innego przechodzi nietknięte i wywali się później na
    ``literal_eval`` — czyli głośno, a nie po cichu z błędną wartością.
    """

    _OPERACJE = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.FloorDiv: lambda a, b: a // b,
    }

    def visit_BinOp(self, wezel):  # noqa: N802 - nazwa wymagana przez ast
        self.generic_visit(wezel)
        operacja = self._OPERACJE.get(type(wezel.op))
        lewo, prawo = wezel.left, wezel.right
        if (
            operacja is not None
            and isinstance(lewo, ast.Constant)
            and isinstance(prawo, ast.Constant)
            and isinstance(lewo.value, (int, float))
            and isinstance(prawo.value, (int, float))
        ):
            return ast.copy_location(
                ast.Constant(value=operacja(lewo.value, prawo.value)), wezel
            )
        return wezel


def _wczytaj_z_production(nazwa):
    """Zwróć wartość przypisania ``nazwa = ...`` z ``production.py``.

    Parsujemy plik do AST i czytamy prawą stronę przypisania — reszta
    ``production.py`` się NIE wykonuje (inaczej odpaliłby się strażnik
    ``SECRET_KEY`` i odczyty ``ALLOWED_HOSTS`` z env).
    """
    drzewo = ast.parse(_PRODUCTION_PY.read_text(encoding="utf-8"))
    for wezel in drzewo.body:
        if isinstance(wezel, ast.Assign) and any(
            isinstance(cel, ast.Name) and cel.id == nazwa for cel in wezel.targets
        ):
            return ast.literal_eval(_ZlozStale().visit(wezel.value))
    raise RuntimeError(f"Nie znalazłem {nazwa} w {_PRODUCTION_PY}")


CACHEOPS = _wczytaj_z_production("CACHEOPS")
CACHEOPS_DEFAULTS = _wczytaj_z_production("CACHEOPS_DEFAULTS")
