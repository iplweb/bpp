Mocki danych testowych PBN dla endpointów paginowanych są teraz
owinięte w ``fixtures.pbn_api.pbn_pageable_json`` — zgodnie z
rzeczywistym kształtem odpowiedzi PBN (``{content, pageable,
number, totalElements, totalPages, ...}``). Wcześniej mocki zwracały
płaską listę / pustą listę, co w
``PBNClient._pages`` triggerowało
``RuntimeWarning: PBNClient.{get,post}_page request for ... did not
return a paged resource, maybe use PBNClient.{get,post} (without
'page') instead``. Produkcyjne wywołania
(``search_publications``, ``get_institution_publication_v2``,
``get_institution_statements_of_single_publication``) pozostają bez
zmian — to są paginowane endpointy PBN, więc ``get_pages`` /
``post_pages`` są poprawne; problem był tylko w mockach.

Poprawione pliki testowe:

- ``src/pbn_api/tests/test_client_sync.py``
- ``src/pbn_api/tests/test_client_helpers.py``
- ``src/pbn_api/tests/test_bpp_admin_helpers.py``
- ``src/bpp/tests/test_views/test_api.py``
