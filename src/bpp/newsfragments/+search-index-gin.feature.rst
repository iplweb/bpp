Wyszukiwanie pełnotekstowe działa szybciej: indeks pełnotekstowy
tabeli cache rekordów zmienił typ z GiST na GIN. Na danych
produkcyjnych typowe kształty zapytań przyspieszają od 1,7× do
prawie 20× (zapytania z dwoma słowami), bez zauważalnego kosztu
przy zapisie.
