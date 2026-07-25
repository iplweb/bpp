# Okres ewaluacyjny — JEDNO miejsce, z którego bierze się zakres lat.
#
# Okresy mają NAZWY, nie tylko wartości: gdy MEiN ogłosi zasady kolejnego
# okresu (2026+, cztero- albo pięcioletniego), dopisujemy tutaj NOWĄ stałą,
# a stara ZOSTAJE. Dane i raporty policzone pod poprzednie zasady muszą dać
# się odtworzyć, więc ``OKRES_2022_2025`` nigdy nie zmieni wartości — to
# okres zamknięty, liczony wg zasad sprzed nowelizacji.
OKRES_2022_2025 = (2022, 2025)

# Okres, którego domyślnie używa kod produkcyjny. TO JEST TA JEDNA LINIA,
# którą przestawia się przy zmianie okresu ewaluacyjnego — wystarczy
# wskazać tu inną stałą ``OKRES_*``. Nie wpisuj tutaj krotki wprost;
# nazwany okres wyżej mówi, WEDŁUG JAKICH ZASAD liczymy.
OKRES_DOMYSLNY = OKRES_2022_2025

# Zakres lat dla wyszukiwania prac do ewaluacji.
#
# Stałe te mieszkały historycznie w ``ewaluacja2021.const`` (apka raportów
# "3N"), ale to ``ewaluacja_common`` jest współdzielonym modułem żywych apek
# ewaluacyjnych (liczba_n, optymalizacja, metryki) i to on faktycznie używa
# zakresu lat w ``get_lista_prac``. Przeniesione tutaj, by żywy kod nie zależał
# od uśpionej apki ``ewaluacja2021`` (patrz ``ewaluacja2021/README.md``).
#
# Wyprowadzone z ``OKRES_DOMYSLNY``, żeby nie mogły ponownie zdryfować
# względem reszty repo (przed refaktorem ``ROK_MAX`` wynosił tu 2026, choć
# cała reszta kodu ewaluacyjnego liczyła do 2025).
ROK_MIN, ROK_MAX = OKRES_DOMYSLNY


def lata_okresu(okres=None):
    """Zwraca listę kolejnych lat okresu — dla filtrów ``rok__in`` i list w UI.

    Okres jest przedziałem DOMKNIĘTYM (``(2022, 2025)`` to cztery lata,
    z rokiem 2025 włącznie), a ``range`` ma prawy koniec wyłączny — stąd
    ``+ 1``. Ta jedynka mieszka wyłącznie tutaj, żeby nie trzeba jej było
    powtarzać (i mylić się w niej) w każdym miejscu budującym listę lat.

    Args:
        okres: krotka ``(rok_min, rok_max)``; domyślnie ``OKRES_DOMYSLNY``
            odczytywany w momencie WYWOŁANIA (a nie definicji funkcji), żeby
            testy mogły podmienić okres przez ``mock.patch``.
    """
    if okres is None:
        okres = OKRES_DOMYSLNY
    rok_min, rok_max = okres
    return list(range(rok_min, rok_max + 1))
