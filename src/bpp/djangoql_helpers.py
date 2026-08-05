"""Zgodność wsteczna dla ai_search: helpery błędów DjangoQL.

Funkcje pomocnicze do lokalizowania i formatowania błędów zapytań DjangoQL
zostały wydzielone w gałęzi ``dev`` do :mod:`bpp.djangoql_errors` (bez
podkreślenia w nazwach). ``ai_search`` (translator + testy) importuje je pod
nazwami z podkreśleniem — re-eksportujemy je stąd jako aliasy, żeby zachować
JEDNO źródło prawdy (``bpp.djangoql_errors``) bez duplikacji implementacji.
"""

from bpp.djangoql_errors import (  # noqa: F401  re-export dla zgodności
    error_location as _error_location,
)
from bpp.djangoql_errors import (  # noqa: F401
    error_payload as _error_payload,
)
from bpp.djangoql_errors import (  # noqa: F401
    format_error_text as _format_error_text,
)
from bpp.djangoql_errors import (  # noqa: F401
    locate_token as _locate_token,
)
