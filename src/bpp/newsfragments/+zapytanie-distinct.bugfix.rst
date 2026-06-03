Wyszukiwarka zapytań DjangoQL (``/bpp/zapytanie/``) nie zwraca już
zduplikowanych wyników. Filtrowanie po relacji „do wielu" (np.
``autorzy.autor.nazwisko ~ "Kowalski"``) tworzyło złączenie, które
powielało ten sam rekord raz na każdy pasujący wiersz powiązany —
przez co lista i licznik wyników były zawyżone. Wyniki są teraz
zwracane jako lista unikalnych obiektów.
