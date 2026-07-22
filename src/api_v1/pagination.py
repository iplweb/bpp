"""Globalna paginacja publicznego API.

Bez ``max_limit`` ``LimitOffsetPagination`` przyjmuje dowolne ``?limit=`` —
anonimowy klient mógł jednym żądaniem kazać serializować całą tabelę
(i przemnożyć koszt każdego pozostałego zapytania na wiersz). Cap jest
odpowiednikiem tego, co ``api_v1.viewsets.zapytanie`` robi lokalnie dla
DjangoQL, tyle że dla wszystkich endpointów listowych naraz.
"""

from rest_framework.pagination import LimitOffsetPagination

#: Twardy cap ``?limit=`` dla całego ``/api/v1/``. 500 = największa wartość
#: obecna w dokumentacji API (harvest słowników jednym żądaniem,
#: docs/superpowers/specs/2026-07-10-api-szukaj-skill-mcp-design.md), więc
#: żaden opisany scenariusz klienta nie zostaje zepsuty. Powyżej cap-a limit
#: jest po cichu przycinany — żądanie nadal zwraca 200, a ``next`` prowadzi
#: do kolejnej strony.
MAKS_LIMIT = 500


class BppLimitOffsetPagination(LimitOffsetPagination):
    max_limit = MAKS_LIMIT
