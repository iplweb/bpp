BEGIN;

CREATE OR REPLACE FUNCTION zaznacz_Cache_Liczba_N_Last_Updated_wymaga_przeliczenia_trigger() RETURNS TRIGGER AS
$$
BEGIN

    INSERT INTO bpp_cache_liczba_n_last_updated(id, wymaga_przeliczenia)
    VALUES (1, true)
    ON CONFLICT (id)
        DO UPDATE SET wymaga_przeliczenia = true;

    RETURN NULL; -- result is ignored since this is an AFTER trigger
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE TRIGGER bpp_autor_dyscyplina_zaznacz_Cache_Liczba_N_trigger
    AFTER INSERT OR UPDATE OR DELETE
    ON bpp_autor_dyscyplina
EXECUTE PROCEDURE zaznacz_Cache_Liczba_N_Last_Updated_wymaga_przeliczenia_trigger();

COMMIT;
