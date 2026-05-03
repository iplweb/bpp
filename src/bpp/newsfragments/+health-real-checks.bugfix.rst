Endpoint ``/health/`` faktycznie sprawdza teraz dostępność
PostgreSQL (``SELECT 1``) i Redisa (``PING`` z 2-sekundowym
timeoutem) i zwraca ``503`` z listą niedostępnych komponentów
zamiast bezwarunkowego ``200 OK``. Docker healthcheck
serwisów ``appserver`` / ``authserver`` wykrywa teraz awarię
bazy lub brokera — wcześniej kontener pozostawał oznaczony
jako „healthy” mimo że strona nie była w stanie obsłużyć
żadnego requestu.
