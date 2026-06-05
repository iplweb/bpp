Lista (changelist) w panelu administracyjnym dla modeli z eksportem
XLSX (m.in. wydawnictwa, autorzy, dyscypliny autorów) wykonywała
zapytanie filtrujące i wyszukujące **dwukrotnie** przy każdym
wyświetleniu — raz przy sprawdzaniu uprawnień do eksportu
(``has_export_permission`` budowało własny ``ChangeList`` tylko po to,
by policzyć rekordy), a drugi raz przy renderowaniu listy. Teraz
``ChangeList`` jest budowany raz na żądanie, więc kosztowne zapytanie
nie powtarza się. Przy okazji znika zdublowany komunikat o błędzie
składni w wyszukiwarce DjangoQL.
