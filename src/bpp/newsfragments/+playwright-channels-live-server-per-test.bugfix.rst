Naprawiono losowe failowanie kilku testów Playwrighta uruchamianych
równolegle z ``-n auto``. Testy używające session-scoped fixture
``channels_live_server`` (jeden Daphne na worker, reuse między
testami) były wrażliwe na pollution stanu w shared ASGI procesie:
wycieki konekcji DB i race między test'em a serwerem na widoczność
commitowanych danych.

Dodano function-scoped warianty ``admin_page_per_test`` i
``preauth_asgi_page_per_test`` (oparte o istniejący
``channels_live_server_per_test``) — każdy test dostaje świeży
proces Daphne. Przepięto na nie testy:

- ``test_bpp_notifications``
- ``test_global_search_logged_in``
- ``test_procent_odpowiedzialnosci_baseModel_AutorFormset_jeden_autor``
- ``test_procent_odpowiedzialnosci_baseModel_AutorFormset_dwoch_autorow``
- ``test_procent_odpowiedzialnosci_baseModel_AutorFormset_dobrze_potem_zle_dwoch_autorow``

Pozostałe testy (~67) nadal używają szybkiego session-scoped
``channels_live_server`` — bez regresji wydajności.
