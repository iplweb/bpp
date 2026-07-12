Ustabilizowano flaky testy ``import_pracownikow`` i ``deduplikator_autorow`` pod
zrównoleglonym uruchomieniem (pytest-split + xdist). Testy tworzące jednostki o
dosłownej nazwie „Katedra Testowa" itp. kolidowały na unikalnym constraincie
``bpp_jednostka_nazwa_key``, gdy scommitowany wiersz sąsiada przeciekł na
współdzielony worker — nazwy jednostek są teraz globalnie unikalne (czytelny
prefiks + losowy sufiks). Test wykrywania duplikatów autorów asertuje własną
inwariantę (para w jednym klastrze) zamiast globalnej liczby kandydatów, więc
ambient „Kowalski Jan" z sąsiednich testów już go nie wywraca.
