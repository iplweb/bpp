Testy ``import_pracownikow`` nie zakładają już danych referencyjnych w bazie
(``Tytul`` „dr", ``Funkcja_Autora`` „asystent") — same je zapewniają przez
fixtury/``get_or_create``, więc nie padają zależnie od kolejności wykonania.
