Listy w panelu administracyjnym korzystają z nowego trybu pobierania relacji
z Django 6.1 (``FETCH_PEERS``): powiązane obiekty potrzebne do wyświetlenia
wiersza dociągane są hurtem dla całej strony, a nie osobno dla każdego
wiersza. Na dużej bazie skraca to czas otwarcia list o kilkanaście do
kilkudziesięciu procent, zależnie od listy.
