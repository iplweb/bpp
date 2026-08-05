Optymalizacje wydajności warstwy requestu: ``NotificationsMiddleware`` nie
wykonuje już pełnoskanowego ``UPDATE`` na tabeli wiadomości przy każdym
requeście zalogowanego użytkownika (odsiew tanim zapytaniem po
zaindeksowanym ``user_id``), a cache ``cacheops`` objął rozstrzyganie
domena→``Site``, grupy uprawnień oraz słowniki (tytuł, język, typ KBN,
charakter formalny, funkcja autora, dyscyplina naukowa). Konferencje
celowo pozostają poza ``cacheops`` — integrator PBN zapisuje każdy rekord
bezwarunkowo, więc cache generowałby tysiące inwalidacji na przebieg.
