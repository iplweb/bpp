-- Zdejmujemy dawny zakaz dat zakończenia zatrudnienia w przyszłości
-- (`bez_dat_do_w_przyszlosci`, wprowadzony w 0064) — zatrudnienie bywa
-- planowane naprzód („pan X pracuje do zaplanowanej daty"). Jest to spójne
-- z triggerem `bpp_autor_ustaw_jednostka_aktualna`, który dla przyszłej daty
-- „do" i tak liczy `aktualny = True`. Dodatkowo `now()` w CHECK to postgresowy
-- antywzorzec: warunek jest sprawdzany tylko przy zapisie wiersza, nie „w
-- czasie", więc dawał złudne poczucie niezmienniczości.
--
-- W zamian dodajemy odporny na czas CHECK pilnujący, że początek zatrudnienia
-- jest wcześniejszy niż koniec. NULL-e (otwarty początek albo otwarty koniec)
-- dają w porównaniu UNKNOWN → warunek CHECK spełniony → dozwolone.
--
-- NOT VALID: nie walidujemy wstecznie istniejących wierszy. Import historycznie
-- tworzy powiązania z pominięciem `Model.clean()` (patrz Autor_Jednostka.clean),
-- więc w bazie mogą już istnieć rekordy z odwróconym/zerowym zakresem — nie
-- chcemy, żeby deployment wywalił się na `ADD CONSTRAINT`. Reguła egzekwowana
-- jest dla wszystkich NOWYCH i ZMIENIANYCH wierszy.

ALTER TABLE bpp_autor_jednostka
    DROP CONSTRAINT IF EXISTS bez_dat_do_w_przyszlosci;

ALTER TABLE bpp_autor_jednostka
    ADD CONSTRAINT poczatek_przed_koncem
    CHECK (rozpoczal_prace < zakonczyl_prace) NOT VALID;
