# Zakres lat dla wyszukiwania prac do ewaluacji.
#
# Stałe te mieszkały historycznie w ``ewaluacja2021.const`` (apka raportów
# "3N"), ale to ``ewaluacja_common`` jest współdzielonym modułem żywych apek
# ewaluacyjnych (liczba_n, optymalizacja, metryki) i to on faktycznie używa
# zakresu lat w ``get_lista_prac``. Przeniesione tutaj, by żywy kod nie zależał
# od uśpionej apki ``ewaluacja2021`` (patrz ``ewaluacja2021/README.md``).
ROK_MIN = 2022
ROK_MAX = 2026
