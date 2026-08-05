-- Niezmiennik "co najwyzej jedno podstawowe miejsce pracy na autora" przenosimy
-- z natychmiastowego (per-statement) partial unique index na DEFERRED constraint
-- trigger. Dzieki temu legalna operacja "przelacz domyslne miejsce pracy"
-- (przejsciowo dwa rekordy podstawowe_miejsce_pracy=TRUE w obrebie JEDNEJ
-- transakcji) juz nie wybucha: sprawdzenie nastepuje dopiero przy COMMIT,
-- na stanie KONCOWYM. Kolejnosc zapisu wierszy w formsecie przestaje miec
-- znaczenie.
--
-- (Partial unique index w PostgreSQL NIE moze byc DEFERRABLE, dlatego nie da
-- sie po prostu "odroczyc" starego indeksu — trzeba go zastapic constraint
-- triggerem.)

-- 1. Usun stary natychmiastowy partial unique index, jesli istnieje w danym
--    srodowisku. UWAGA: w czesci baz (dryf schematu wzgledem migracji 0318)
--    indeksu fizycznie nie ma, mimo ze django_migrations notuje go jako
--    zaaplikowanego -> DROP ... IF EXISTS jest tu konieczny.
DROP INDEX IF EXISTS jedno_podstawowe_miejsce_pracy_na_autora;

-- 2. Funkcja walidujaca. Liczy globalna liczbe podstawowych miejsc pracy
--    autora; jako DEFERRED widzi stan na koniec transakcji.
CREATE OR REPLACE FUNCTION bpp_autor_jednostka_jedno_podstawowe()
    RETURNS trigger
    LANGUAGE plpgsql
AS $$
DECLARE
    v_count integer;
BEGIN
    IF NEW.podstawowe_miejsce_pracy IS TRUE THEN
        SELECT count(*) INTO v_count
        FROM bpp_autor_jednostka
        WHERE autor_id = NEW.autor_id
          AND podstawowe_miejsce_pracy IS TRUE;
        IF v_count > 1 THEN
            -- ERRCODE unique_violation -> Django mapuje to na IntegrityError.
            RAISE EXCEPTION
                'Autor ma wiecej niz jedno podstawowe miejsce pracy (dozwolone jest tylko jedno)'
                USING ERRCODE = 'unique_violation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

-- 3. Constraint trigger DEFERRABLE INITIALLY DEFERRED.
DROP TRIGGER IF EXISTS bpp_autor_jednostka_jedno_podstawowe_trig
    ON bpp_autor_jednostka;

CREATE CONSTRAINT TRIGGER bpp_autor_jednostka_jedno_podstawowe_trig
    AFTER INSERT OR UPDATE ON bpp_autor_jednostka
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    EXECUTE PROCEDURE bpp_autor_jednostka_jedno_podstawowe();
