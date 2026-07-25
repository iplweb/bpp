# Zakres lat dla wyszukiwania prac do ewaluacji.
#
# Stałe te mieszkały historycznie w ``ewaluacja2021.const`` (apka raportów
# "3N"), ale to ``ewaluacja_common`` jest współdzielonym modułem żywych apek
# ewaluacyjnych (liczba_n, optymalizacja, metryki) i to on faktycznie używa
# zakresu lat w ``get_lista_prac``. Przeniesione tutaj, by żywy kod nie zależał
# od uśpionej apki ``ewaluacja2021`` (patrz ``ewaluacja2021/README.md``).
ROK_MIN = 2022
ROK_MAX = 2026

# Okno *bieżącej* ewaluacji, jako domknięty przedział (pierwszy rok, ostatni
# rok). Bieżące okno otwiera się w 2026 r. i zamyka w 2029 r.
#
# To jedyne źródło prawdy dla aplikacji ``kompletnosc_polon`` (raport
# kompletności danych POL-on, FD#437) — raport pyta o braki wyłącznie
# w rekordach z tego przedziału lat.
#
# UWAGA: świadomie NIE podpięte pod ``ROK_MIN``/``ROK_MAX`` powyżej ani pod
# domyślne argumenty w ``ewaluacja_metryki`` (``rok_min=2022, rok_max=2025``
# w ośmiu sygnaturach). Te trzy definicje okna są dziś wzajemnie niezgodne;
# ich ujednolicenie zmieniłoby wyniki liczenia metryk i slotów, więc idzie
# osobnym zgłoszeniem. Nowy kod ma używać ``OKNO_EWALUACJI``.
OKNO_EWALUACJI = (2026, 2029)
