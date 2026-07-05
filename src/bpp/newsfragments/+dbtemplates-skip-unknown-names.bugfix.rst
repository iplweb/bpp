Przyspieszono renderowanie stron w panelu administracyjnym. Każda
lista obiektów wykonywała wcześniej ~300 zbędnych zapytań do bazy o
szablony (``dbtemplates`` sprawdzał w bazie każdą z ~150 nazw
szablonów admina, mimo że nie ma tam żadnego z nich), przez co
strony otwierały się zauważalnie wolno. Po aktualizacji
``django-dbtemplates-iplweb`` do wersji ``4.4.0`` i włączeniu opcji
``DBTEMPLATES_SKIP_UNKNOWN_NAMES`` te zapytania znikają — strony
admina renderują się kilkukrotnie szybciej.
