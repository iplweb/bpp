Publiczne API (``/api/v1/``): usunięto problem N+1 na endpointach listowych.
Listy wydawnictw ciągłych i zwartych, patentów, autorów, źródeł, nagród oraz
przypisań autorów wykonywały dotąd od jednego do trzech dodatkowych zapytań
NA KAŻDY wiersz strony (pola tekstowe relacji: status korekty, tryb dostępu /
wersja tekstu / licencja OpenAccess, typ odpowiedzialności, zasięg źródła,
obiekt nagrody, jednostki autora). Liczba zapytań nie zależy już od liczby
zwróconych rekordów — np. lista wydawnictw ciągłych z czterema rekordami
zeszła z 23 do 11 zapytań.

Dodatkowo parametr ``?limit=`` ma teraz twardy górny limit 500 rekordów na
żądanie (wcześniej dowolna wartość, także anonimowo), a autoryzowane
``/api/v1/zapytanie/rekord/`` przestało pobierać indeks wyszukiwania
pełnotekstowego i kilkadziesiąt zbędnych kolumn dla każdego wiersza.
