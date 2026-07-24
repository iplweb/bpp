Adminowa wyszukiwarka DjangoQL nie udostępnia już modelu użytkownika
(``BppUser``) przez relację ``Autor.user`` — pola ``pbn_token``, ``email`` i
``is_superuser`` przestały być filtrowalne, co eliminowało możliwość
odczytania cudzego tokenu PBN metodą blind-oracle.
