Hardening bezpieczeństwa integracji OAuth/MCP i klienta PBN po przeglądzie:
walidacja hosta w przekierowaniu logowania Microsoft (blokada open-redirect),
maskowanie sekretów OAuth w Rollbarze (``refresh_token``, ``code``,
``code_verifier``, ``token``), egzekwowanie zakresu ``read`` na tokenach
bearer, liczenie rejestracji DCR po realnym IP klienta (proxy-aware), oraz
zaprzestanie wypisywania tokenów PBN do stdout i wysyłania surowego body
odpowiedzi PBN wraz z sekretnymi nagłówkami do Rollbara.
