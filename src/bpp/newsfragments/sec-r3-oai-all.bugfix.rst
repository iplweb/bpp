Naprawiono komendę ``oai_all`` (harvester OAI-PMH), która była niesprawna:
używała usuniętego w Pythonie 3.9 ``Element.getchildren()`` (crash), miała
zaszyty adres HTTP i zakres dat kończący się w 2020, nie ustawiała timeoutu
ani nie sprawdzała statusu odpowiedzi, a błędny ``resumptionToken`` mógł
zapętlić ją w nieskończoność. Teraz URL i zakres dat są parametrami, żądania
mają timeout i ``raise_for_status``, XML jest parsowany świadomie przestrzeni
nazw, a bezpieczniki (limit żądań + wykrywanie powtórzonego tokenu) chronią
przed pętlą.
