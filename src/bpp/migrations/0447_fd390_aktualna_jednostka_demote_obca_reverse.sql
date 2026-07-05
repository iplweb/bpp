-- Reverse FD#390: przywróć wersję settera aktualna_jednostka z 0440
-- (bez demotowania obcej jednostki — sort bez skupia_pracownikow).

BEGIN;

CREATE OR REPLACE FUNCTION public.bpp_autor_ustaw_jednostka_aktualna()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_autor_id    integer;
    v_jednostka_id integer;
    v_funkcja_id  integer;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.autor_id IS DISTINCT FROM OLD.autor_id THEN
            RAISE EXCEPTION
                'zmiana ID autora nie jest obsługiwana przez trigger';
        END IF;
    END IF;

    IF TG_OP = 'DELETE' THEN
        v_autor_id := OLD.autor_id;
    ELSE
        v_autor_id := NEW.autor_id;
    END IF;

    SELECT jednostka_id, funkcja_id
    INTO v_jednostka_id, v_funkcja_id
    FROM bpp_autor_jednostka
    WHERE autor_id = v_autor_id
      AND coalesce(zakonczyl_prace, '9999-12-31'::date) > NOW()::date
    ORDER BY
        coalesce(podstawowe_miejsce_pracy, false) DESC,
        coalesce(rozpoczal_prace, '0001-01-01'::date) DESC,
        coalesce(zakonczyl_prace, '9999-12-31'::date) DESC,
        id DESC
    LIMIT 1;

    IF FOUND THEN
        UPDATE bpp_autor
           SET aktualna_jednostka_id = v_jednostka_id,
               aktualna_funkcja_id = v_funkcja_id
         WHERE id = v_autor_id;
    ELSE
        UPDATE bpp_autor
           SET aktualna_jednostka_id = NULL,
               aktualna_funkcja_id = NULL
         WHERE id = v_autor_id;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
