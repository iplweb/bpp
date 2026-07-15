Kolejne testy nie zakładają już danych słownikowych w bazie (Jezyk „polski",
Typ_Odpowiedzialnosci, Rzeczownik, Crossref_Mapper) — same je zapewniają przez
fixtury (`jezyki`, `typy_odpowiedzialnosci`, nowe `rzeczowniki`/`crossref_mappery`)
lub `get_or_create`, więc nie padają zależnie od kolejności wykonania.
