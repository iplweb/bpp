Test inwalidacji cache'a strony głównej po zapisie Uczelni biegnie teraz
na realnym backendzie (``LocMemCache``) i sprawdza SKUTEK zamiast mocka
``cache.delete``. Dowodzi pełnej ścieżki: pierwsze żądanie zapisuje kontekst,
zapis Uczelni faktycznie unieważnia klucz, kolejne żądanie dostaje nową
nazwę zamiast zapamiętanej starej. Dołożono warunek kontrolny (zmiana z
pominięciem sygnału zostawia starą wartość w cache), który pada, gdyby cache
przestał działać. Inwalidacja działa poprawnie — bug nie ujawniony.
