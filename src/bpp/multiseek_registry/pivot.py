"""Zgodnościowy re-eksport: silnik pivota żyje w bpp.pivot.

Rejestr wymiarów Rekordu przestał być multiseek-specyficzny w momencie, gdy
tabelę krzyżową dostała też strona „Wyszukiwanie zapytaniem". Ten moduł
zostaje, żeby nie ruszać call-site'ów w szablonach, widokach i testach.

Świadomie NIE re-eksportuje PIVOT_MAX_CELLS/PIVOT_MAX_PAIRS: `zbuduj_pivot`
czyta te progi jako globalne SWOJEGO modułu (bpp.pivot.core), więc kopia
nazwy pod tą ścieżką byłaby martwa — monkeypatch na niej nie wpłynąłby na
bramkę, dając złudzenie działającego testu. Kto patchuje progi, patchuje je
w bpp.pivot.core, gdzie mieszkają.
"""

from bpp.pivot.core import (  # noqa: F401
    BRAK,
    PivotDimension,
    PivotMetric,
    PivotResult,
    PivotTooLargeError,
    zbuduj_pivot,
)
from bpp.pivot.rekord import (  # noqa: F401
    DEFAULT_METRIC,
    DEFAULT_ROW,
    DIMENSIONS,
    METRICS,
    parse_pivot_params,
)
