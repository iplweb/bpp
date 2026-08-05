Ścieżkę ASGI liveops (``WebProgress`` → channel layer → odbiór komunikatu)
pokrywa teraz test integracyjny na realnym Redisie. Testy jednostkowe
raportują postęp przez ``MockProgress``, więc bez tego testu transport
nie byłby w ogóle sprawdzany.
