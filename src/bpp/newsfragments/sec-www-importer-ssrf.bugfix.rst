Importer publikacji (provider „Pozostałe strony WWW") waliduje teraz adres
docelowy przez rozwiązanie DNS przed każdym żądaniem i po każdym
przekierowaniu — blokuje pobieranie z adresów loopback, prywatnych,
link-local oraz endpointów metadanych chmury (ochrona przed SSRF).
