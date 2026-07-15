Decyzja o dodaniu ``DISTINCT`` w wyszukiwarce multiseek nie opiera się już na
przeszukiwaniu tekstu wygenerowanego SQL-a (kruche — zależne od aliasów i
formatowania zapytania). Zamiast tego złączenia mnożące rekordy (autorzy, bazy
zewnętrzne) wykrywane są po realnych nazwach tabel w zapytaniu
(``query.alias_map``), co jest odporne na aliasy i szczegóły generowania SQL-a.
