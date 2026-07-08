Integracja źródeł z PBN (``integruj_zrodla``, Faza 2 pobierania źródeł)
iteruje teraz strumieniowo po źródłach bez dopasowania PBN (server-side
cursor) zamiast ładować wszystkie naraz do pamięci — mniejszy i stały ślad
pamięciowy przy pełnym imporcie.
