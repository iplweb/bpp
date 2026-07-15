Tabele DataTables znów mają polskie etykiety (np. „Szukaj" zamiast „Search").
Domyślny język ustawiany był w ``$(document).ready`` na końcu strony, co
przegrywało wyścig z inicjalizacją tabel w blokach treści — teraz konfiguracja
jest ustawiana synchronicznie, zaraz po załadowaniu bundla, więc każda tabela ją
widzi.
