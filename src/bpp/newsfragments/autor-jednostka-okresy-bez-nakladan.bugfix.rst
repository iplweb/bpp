Datowane okresy zatrudnienia autora w tej samej jednostce nie mogą się już
nakładać: dwa równoległe zapisy (import, masowa edycja) tworzyły metodą
„sprawdź i utwórz" częściowo pokrywające się przedziały pracy, których żaden
warunek unikalności nie wykrywał. Dodano ograniczenie wykluczające
(EXCLUDE / btree_gist) na przedziale ``[rozpoczęcie, zakończenie]`` z granicami
domkniętymi obustronnie — okresy przylegające (koniec + 1 dzień = następny
początek) i rozłączne pozostają legalne, a otwarty koniec (bez daty
zakończenia) traktowany jest jako trwający do teraz. Migracja poprzedzająca
odmawia założenia ograniczenia z czytelną listą kolizji, gdy w bazie istniałyby
już nakładające się okresy (zamiast je po cichu scalać). Dodawanie jednostki
przy równoległym utworzeniu pokrywającego okresu nie kończy się już błędem.
