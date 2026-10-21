"""Zgodnościowy re-eksport: silnik pivota żyje w bpp.pivot.

Rejestr wymiarów Rekordu przestał być multiseek-specyficzny w momencie, gdy
tabelę krzyżową dostała też strona „Wyszukiwanie zapytaniem". Ten moduł
zostaje, żeby nie ruszać call-site'ów w szablonach, widokach i testach.

Świadomie NIE re-eksportuje STAŁYCH (PIVOT_MAX_CELLS/PIVOT_MAX_PAIRS,
DOZWOLONE_NA_STRONIE): kod silnika czyta je jako globalne SWOJEGO modułu
(bpp.pivot.core), więc kopia nazwy pod tą ścieżką byłaby martwa — podmiana
na niej nie wpłynęłaby na bramkę ani na walidację, dając złudzenie
działającego testu, a przy DOZWOLONE_NA_STRONIE rozjechałaby listę opcji
w UI z whitelistą sprawdzaną w parse_widok(). Stałe bierz z bpp.pivot.core,
gdzie mieszkają. Funkcje (zbuduj_pivot, parse_widok) re-eksportujemy, bo to
te SAME obiekty, nie kopie wartości.
"""

from bpp.pivot.core import (  # noqa: F401
    BRAK,
    PivotDimension,
    PivotMetric,
    PivotResult,
    PivotTooLargeError,
    PivotWidok,
    parse_widok,
    zbuduj_pivot,
)
from bpp.pivot.rekord import (  # noqa: F401
    DEFAULT_METRIC,
    DEFAULT_ROW,
    DIMENSIONS,
    METRICS,
    parse_pivot_params,
)
