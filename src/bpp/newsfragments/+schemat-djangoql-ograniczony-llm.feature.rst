Widok „Szukaj zapytaniem" korzysta teraz z ograniczonego schematu DjangoQL
(allow-lista rdzenia bibliograficznego): podpowiedzi i zapytania obejmują tylko
modele publikacji, autorów, jednostek, źródeł i słowniki, bez szumu z
wewnętrznych tabel PBN / importu / deduplikacji / ewaluacji. Wyszukiwanie
DjangoQL w panelu administracyjnym pozostaje pełne. Dodano też komendę
``manage.py opisz_schemat_djangoql_dla_llm`` generującą zwięzły, ostemplowany
wersją opis tej przestrzeni wyszukiwania dla modeli językowych (LLM).
