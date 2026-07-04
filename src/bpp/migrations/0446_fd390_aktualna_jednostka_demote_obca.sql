-- FD#390: trigger aktualna_jednostka — realna jednostka bije obcą.
--
-- Multi-homed, wspólna baza: jeden Autor bywa przypięty do jednostek w RÓŻNYCH
-- uczelniach (np. „Jednostka Domyślna" uczelni A jako pracownik + „Obca
-- jednostka" uczelni B po imporcie publikacji B). Poprzednia wersja settera
-- (0440) sortowała kandydatów bez uwzględnienia CHARAKTERU jednostki, więc przy
-- braku dat i „podstawowego miejsca pracy" decydowało `id DESC` — obca jednostka
-- utworzona później porywała `aktualna_jednostka`, przez co na stronie uczelni A
-- autor „pokazywał się jako z obcej uczelni" (zepsute linki, edycja 404, PBN UID).
--
-- Fix: dołożenie JOIN do bpp_jednostka i PIERWSZEGO klucza sortowania
-- `skupia_pracownikow DESC` — realna jednostka pracownicza (skupia_pracownikow
-- = TRUE) zawsze wygrywa z obcą (FALSE). Reszta porządku bez zmian. Autor
-- przypięty WYŁĄCZNIE do obcych jednostek nadal dostaje obcą jako aktualną
-- (demotowanie działa tylko przy konflikcie z realną). Zakończone zatrudnienia
-- dalej są odfiltrowane WHERE-m przed sortowaniem, więc realna-ale-zakończona
-- nie „ożywa".

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

    SELECT aj.jednostka_id, aj.funkcja_id
    INTO v_jednostka_id, v_funkcja_id
    FROM bpp_autor_jednostka aj
    JOIN bpp_jednostka j ON j.id = aj.jednostka_id
    WHERE aj.autor_id = v_autor_id
      AND coalesce(aj.zakonczyl_prace, '9999-12-31'::date) > NOW()::date
    ORDER BY
        coalesce(j.skupia_pracownikow, true) DESC,
        coalesce(aj.podstawowe_miejsce_pracy, false) DESC,
        coalesce(aj.rozpoczal_prace, '0001-01-01'::date) DESC,
        coalesce(aj.zakonczyl_prace, '9999-12-31'::date) DESC,
        aj.id DESC
    LIMIT 1;

    IF FOUND THEN
        UPDATE bpp_autor
           SET aktualna_jednostka_id = v_jednostka_id,
               aktualna_funkcja_id = v_funkcja_id
         WHERE id = v_autor_id;
    ELSE
        -- Brak wpisów -> wyzeruj aktualną jednostkę/funkcję.
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
