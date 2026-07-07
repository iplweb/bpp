-- Reverse: zdejmij DEFERRED constraint trigger + funkcje i odtworz oryginalny
-- natychmiastowy partial unique index (stan sprzed migracji 0444).
DROP TRIGGER IF EXISTS bpp_autor_jednostka_jedno_podstawowe_trig
    ON bpp_autor_jednostka;
DROP FUNCTION IF EXISTS bpp_autor_jednostka_jedno_podstawowe();

CREATE UNIQUE INDEX IF NOT EXISTS jedno_podstawowe_miejsce_pracy_na_autora
    ON bpp_autor_jednostka (autor_id)
    WHERE podstawowe_miejsce_pracy = true;
