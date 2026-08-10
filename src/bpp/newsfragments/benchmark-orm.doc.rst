Dodano harness do mierzenia wydajności ORM-a na kopii bazy produkcyjnej
(``bench/``) wraz z dokumentacją (``docs/deweloper/benchmark-orm.md``):
liczy zapytania i czas dla prawdziwych requestów, wykrywa N+1 przez
*fetch modes* z Django 6.1 i weryfikuje, że optymalizacja nie zmieniła
wyniku strony.
