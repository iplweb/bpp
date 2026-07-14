Na ekranie „Rezultaty” importu pracowników dodano selektor liczby
wierszy na stronę (10 / 25 / 50 / 100 / wszystkie, domyślnie 25) wraz
z pagerem. Paginacja działa po stronie klienta i współgra z istniejącym
paskiem filtrów. Ogranicza rozmiar renderowanego drzewa DOM, dzięki
czemu edycja dopasowanego autora przez Select2 nie spowalnia się przy
importach z dużą liczbą wierszy.
