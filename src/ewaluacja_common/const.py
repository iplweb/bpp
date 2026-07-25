# Zakres lat dla wyszukiwania prac do ewaluacji.
#
# Stałe te mieszkały historycznie w ``ewaluacja2021.const`` (apka raportów
# "3N"), ale to ``ewaluacja_common`` jest współdzielonym modułem żywych apek
# ewaluacyjnych (liczba_n, optymalizacja, metryki) i to on faktycznie używa
# zakresu lat w ``get_lista_prac``. Przeniesione tutaj, by żywy kod nie zależał
# od uśpionej apki ``ewaluacja2021`` (patrz ``ewaluacja2021/README.md``).
ROK_MIN = 2022
ROK_MAX = 2026

# Okno lat raportu kompletności danych POL-on, jako para
# (pierwszy rok, ostatni rok). Okno otwiera się w 2026 r., a jego górna
# granica jest **z rozmysłem nieustalona** — stąd ``None``.
#
# ``None`` NIE jest przeoczeniem ani „brakiem czasu, żeby wpisać rok”.
# W chwili pisania tego kodu MEiN nie ogłosił, czy nowy okres ewaluacyjny
# trwa cztery czy pięć lat. Wpisanie tu zgadniętego roku (np. 2029) znaczyło
# by, że w pierwszym roku poza zgadniętym zakresem raport po cichu przestanie
# pokazywać nowe rekordy — najgorszy możliwy tryb awarii dla raportu
# o brakach, bo wygląda dokładnie jak „wszystko w porządku”. ``None`` czyta
# się jako „od 2026 wzwyż, granicy jeszcze nie znamy”: selektory nie nakładają
# wtedy górnego odcięcia, a interfejs pokazuje „od 2026”, nie zmyśloną datę.
#
# Gdy zasady zostaną ogłoszone, domknięcie okna to zmiana jednej liczby:
# ``OKNO_EWALUACJI = (2026, <ostatni rok>)``. Kod obsługuje oba warianty
# (patrz ``kompletnosc_polon.selektory._zawez`` i
# ``kompletnosc_polon.views.mixins.opis_okna``) i ma na oba testy.
#
# To okno jest **prywatnym ustawieniem raportu POL-on** (``kompletnosc_polon``,
# FD#437) — raport pyta o braki wyłącznie w rekordach z tego zakresu lat.
# Celowo NIE jest tym samym, co ``ROK_MIN``/``ROK_MAX`` powyżej ani co
# domyślne argumenty ``rok_min``/``rok_max`` w ``ewaluacja_metryki``
# (czyli domyślny okres metryk i liczby N). To dwa różne zegary: tu chodzi
# o obowiązek sprawozdawczy z rozporządzenia o danych w POL-on (jakie dane
# muszą być kompletne), tam — o okres, za który liczy się punktację, sloty
# i liczbę N. Ujednolicenie ich zmieniłoby wyniki liczenia metryk, więc idzie
# osobnym zgłoszeniem. Nowy kod raportu POL-on ma używać ``OKNO_EWALUACJI``.
OKNO_EWALUACJI = (2026, None)
