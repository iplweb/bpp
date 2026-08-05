Publiczne strony przeglądania (lata, rok, listy autorów, źródeł i jednostek
oraz strona rekordu) są zapamiętywane w cache'u HTTP dla użytkowników
niezalogowanych — ścina to ruch robotów indeksujących z bazy danych. Cache
jest izolowany per domena (multi-hosted: treść jednej uczelni nigdy nie
trafi pod domenę innej) oraz per stan zgody na ciasteczka (osoba, która
odmówiła zgody, nigdy nie dostanie strony z włączoną analityką), omija
użytkowników zalogowanych w obie strony, a zapis danych w panelu
administracyjnym unieważnia go natychmiast.
