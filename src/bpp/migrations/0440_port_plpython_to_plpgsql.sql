-- Port 7 funkcji PL/Python -> PL/pgSQL (pożegnanie z plpython3u, §1 spec).
--
-- Wszystkie 7 jest GD-free (stanu sesyjnego GD używały tylko bpp_refresh_cache
-- i trigger_tytul_sort). Tu: 2 dirty-markery dyscyplin, 2 settery "aktualna",
-- 3 walidatory. CREATE OR REPLACE — triggery (CREATE TRIGGER) pozostają bez
-- zmian, zmienia się tylko ciało + LANGUAGE.
--
-- Uwaga semantyczna: wszędzie gdzie oryginał używał Pythonowego `==`
-- (które dla None==None zwraca True), stosujemy `IS NOT DISTINCT FROM`,
-- żeby NULL=NULL traktować jak równość — wierna kalka zachowania plpython.


-- =====================================================================
-- 1a. Dirty-markery denorm (filtr rok + dyscyplina + ten autor)
-- =====================================================================

-- bpp_autor_dyscyplina_change: AFTER UPDATE na bpp_autor_dyscyplina.
-- Gdy autorowi zmienia się przypisana dyscyplina/subdyscyplina na dany rok,
-- przemapowuje wiersze *_autor (tego autora, tego roku) ze starej wartości
-- dyscypliny na nową i oznacza dotknięte rekordy jako dirty dla denorm.
--
-- KRYTYCZNE: dwufazowość (snapshot ID-ków OBU zbiorów PRZED jakimkolwiek
-- UPDATE). W najgorszym przypadku — zamianie dyscypliny z subdyscypliną —
-- sekwencyjny UPDATE f1 wpadłby w selekcję f2 (read-after-write) i cofnął
-- zmianę. Dlatego najpierw array_agg ID-ków obu zbiorów, potem dopiero
-- UPDATE-y. Wierna kalka oryginalnego two-temp-table podejścia.
CREATE OR REPLACE FUNCTION public.bpp_autor_dyscyplina_change() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_rok           integer;
    v_autor_id      integer;
    v_f1_old        integer;
    v_f1_new        integer;
    v_f2_old        integer;
    v_f2_new        integer;
    v_diff_f1       boolean;
    v_diff_f2       boolean;
    v_table         text;
    v_ct_id         integer;
    v_dys_ids       integer[];
    v_dys_rekordy   integer[];
    v_subdys_ids    integer[];
    v_subdys_rekordy integer[];
BEGIN
    -- Guard: zmiana roku / ID autora nie jest obsługiwana (jak w oryginale).
    IF NEW.rok IS DISTINCT FROM OLD.rok THEN
        RAISE EXCEPTION 'Zmiana roku NIE jest obsługiwana';
    END IF;
    IF NEW.autor_id IS DISTINCT FROM OLD.autor_id THEN
        RAISE EXCEPTION 'Zmiana ID autora nie jest obsługiwana';
    END IF;

    v_rok      := NEW.rok;
    v_autor_id := NEW.autor_id;

    v_f1_old := OLD.dyscyplina_naukowa_id;
    v_f1_new := NEW.dyscyplina_naukowa_id;
    v_f2_old := OLD.subdyscyplina_naukowa_id;
    v_f2_new := NEW.subdyscyplina_naukowa_id;

    v_diff_f1 := v_f1_old IS DISTINCT FROM v_f1_new;
    v_diff_f2 := v_f2_old IS DISTINCT FROM v_f2_new;

    -- Brak zmian dyscyplin — wróć.
    IF NOT v_diff_f1 AND NOT v_diff_f2 THEN
        RETURN NEW;
    END IF;

    FOREACH v_table IN ARRAY
        ARRAY['bpp_wydawnictwo_ciagle', 'bpp_wydawnictwo_zwarte', 'bpp_patent']
    LOOP
        SELECT id INTO v_ct_id
        FROM django_content_type
        WHERE app_label = 'bpp' AND model = substr(v_table, 5);

        v_dys_ids := NULL;
        v_dys_rekordy := NULL;
        v_subdys_ids := NULL;
        v_subdys_rekordy := NULL;

        -- FAZA 1: snapshot ID-ków zanim cokolwiek zaktualizujemy.
        IF v_diff_f1 AND v_f1_old IS NOT NULL THEN
            EXECUTE format(
                'SELECT array_agg(a.id), array_agg(a.rekord_id)
                   FROM %I a, %I p
                  WHERE a.dyscyplina_naukowa_id = $1
                    AND p.rok = $2
                    AND p.id = a.rekord_id
                    AND a.autor_id = $3',
                v_table || '_autor', v_table)
            INTO v_dys_ids, v_dys_rekordy
            USING v_f1_old, v_rok, v_autor_id;
        END IF;

        IF v_diff_f2 AND v_f2_old IS NOT NULL THEN
            EXECUTE format(
                'SELECT array_agg(a.id), array_agg(a.rekord_id)
                   FROM %I a, %I p
                  WHERE a.dyscyplina_naukowa_id = $1
                    AND p.rok = $2
                    AND p.id = a.rekord_id
                    AND a.autor_id = $3',
                v_table || '_autor', v_table)
            INTO v_subdys_ids, v_subdys_rekordy
            USING v_f2_old, v_rok, v_autor_id;
        END IF;

        -- FAZA 2: dopiero teraz UPDATE-y + oznaczanie dirty.
        IF v_dys_ids IS NOT NULL THEN
            EXECUTE format(
                'UPDATE %I SET dyscyplina_naukowa_id = $1 WHERE id = ANY($2)',
                v_table || '_autor')
            USING v_f1_new, v_dys_ids;

            INSERT INTO denorm_dirtyinstance(content_type_id, object_id)
            SELECT v_ct_id, r FROM unnest(v_dys_rekordy) AS r
            ON CONFLICT DO NOTHING;
        END IF;

        IF v_subdys_ids IS NOT NULL THEN
            -- subdyscyplina_naukowa autora -> kolumna dyscyplina_naukowa_id
            -- wiersza *_autor (te tabele mają tylko jedno pole dyscypliny);
            -- nowa wartość może być NULL (gdy subdyscyplinę skasowano).
            EXECUTE format(
                'UPDATE %I SET dyscyplina_naukowa_id = $1 WHERE id = ANY($2)',
                v_table || '_autor')
            USING v_f2_new, v_subdys_ids;

            INSERT INTO denorm_dirtyinstance(content_type_id, object_id)
            SELECT v_ct_id, r FROM unnest(v_subdys_rekordy) AS r
            ON CONFLICT DO NOTHING;
        END IF;
    END LOOP;

    RETURN NEW;
END;
$$;


-- bpp_autor_dyscyplina_delete: AFTER DELETE na bpp_autor_dyscyplina.
-- Gdy kasowane jest przypisanie dyscypliny dla roku — wszystkim wierszom
-- *_autor tego autora w tym roku zeruje dyscyplinę i oznacza rekordy dirty.
-- Filtr: rok + autor (jak w oryginale). Oryginał iterował po polach
-- [dyscyplina, subdyscyplina] robiąc to samo dwa razy gdy oba były != NULL;
-- wynik (zbiór NULL-owanych wierszy i dirtyinstance) jest identyczny przy
-- jednym przebiegu, więc upraszczamy do jednego — z gardą "któraś != NULL".
CREATE OR REPLACE FUNCTION public.bpp_autor_dyscyplina_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_autor_id integer := OLD.autor_id;
    v_rok      integer := OLD.rok;
    v_table    text;
    v_ct_id    integer;
BEGIN
    IF OLD.dyscyplina_naukowa_id IS NULL
       AND OLD.subdyscyplina_naukowa_id IS NULL THEN
        RETURN OLD;
    END IF;

    FOREACH v_table IN ARRAY
        ARRAY['bpp_wydawnictwo_ciagle', 'bpp_wydawnictwo_zwarte', 'bpp_patent']
    LOOP
        SELECT id INTO v_ct_id
        FROM django_content_type
        WHERE app_label = 'bpp' AND model = substr(v_table, 5);

        EXECUTE format(
            'WITH dys AS (
                 UPDATE %I a SET dyscyplina_naukowa_id = NULL
                   FROM %I p
                  WHERE p.id = a.rekord_id
                    AND p.rok = $1
                    AND a.autor_id = $2
              RETURNING a.rekord_id
             )
             INSERT INTO denorm_dirtyinstance(content_type_id, object_id)
             SELECT $3, rekord_id FROM dys
             ON CONFLICT DO NOTHING',
            v_table || '_autor', v_table)
        USING v_rok, v_autor_id, v_ct_id;
    END LOOP;

    RETURN OLD;
END;
$$;


-- =====================================================================
-- 1c. Walidatory (assert -> RAISE EXCEPTION)
-- =====================================================================

-- bpp_autor_dyscyplina_rozne: dyscyplina != subdyscyplina.
-- IS NOT DISTINCT FROM kalkuje Pythonowe `==` (None==None -> True).
CREATE OR REPLACE FUNCTION public.bpp_autor_dyscyplina_rozne() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.dyscyplina_naukowa_id
       IS NOT DISTINCT FROM NEW.subdyscyplina_naukowa_id THEN
        RAISE EXCEPTION 'Dyscypliny muszą być różne';
    END IF;
    RETURN NEW;
END;
$$;


-- bpp_jednostka_sprawdz_uczelnia_id: uczelnia jednostki == uczelnia jej wydziału.
CREATE OR REPLACE FUNCTION public.bpp_jednostka_sprawdz_uczelnia_id() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_wydzial_uczelnia integer;
BEGIN
    IF NEW.wydzial_id IS NOT NULL THEN
        SELECT uczelnia_id INTO v_wydzial_uczelnia
        FROM bpp_wydzial WHERE id = NEW.wydzial_id;

        IF v_wydzial_uczelnia IS DISTINCT FROM NEW.uczelnia_id THEN
            RAISE EXCEPTION 'Uczelnia jednostki i wydzialu musi byc identyczna';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;


-- bpp_jednostka_wydzial_sprawdz_uczelnia_id: uczelnia wydziału == uczelnia
-- jednostki (po stronie tabeli M2M bpp_jednostka_wydzial).
CREATE OR REPLACE FUNCTION public.bpp_jednostka_wydzial_sprawdz_uczelnia_id()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_uczelnia_wydzialu  integer;
    v_uczelnia_jednostki integer;
BEGIN
    IF NEW.wydzial_id IS NOT NULL THEN
        SELECT uczelnia_id INTO v_uczelnia_wydzialu
        FROM bpp_wydzial WHERE id = NEW.wydzial_id;

        SELECT uczelnia_id INTO v_uczelnia_jednostki
        FROM bpp_jednostka WHERE id = NEW.jednostka_id;

        IF v_uczelnia_wydzialu IS DISTINCT FROM v_uczelnia_jednostki THEN
            RAISE EXCEPTION 'Uczelnia jednostki i wydzialu musi byc identyczna';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;


-- =====================================================================
-- 1b. Settery "aktualna jednostka" / "aktualny wydział"
-- =====================================================================

-- bpp_autor_ustaw_jednostka_aktualna: AFTER INS/DEL/UPD na bpp_autor_jednostka.
-- Wylicza aktualną jednostkę/funkcję autora (najświeższe, niezakończone
-- zatrudnienie, preferując podstawowe miejsce pracy) i zapisuje na bpp_autor.
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


-- bpp_jednostka_ustaw_wydzial_aktualna: AFTER INS/DEL/UPD na
-- bpp_jednostka_wydzial. Wylicza aktualny wydział jednostki (najświeższe
-- przypisanie wg daty "od") i zapisuje na bpp_jednostka.
CREATE OR REPLACE FUNCTION public.bpp_jednostka_ustaw_wydzial_aktualna()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_jednostka_id integer;
    v_wydzial_id   integer;
    v_aktualna     boolean;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.jednostka_id IS DISTINCT FROM OLD.jednostka_id THEN
            RAISE EXCEPTION
                'zmiana ID jednostki nie jest obsługiwana przez trigger';
        END IF;
    END IF;

    IF TG_OP = 'DELETE' THEN
        v_jednostka_id := OLD.jednostka_id;
    ELSE
        v_jednostka_id := NEW.jednostka_id;
    END IF;

    SELECT wydzial_id,
           (coalesce("do", '9999-12-31'::date) > NOW()::date)
    INTO v_wydzial_id, v_aktualna
    FROM bpp_jednostka_wydzial
    WHERE jednostka_id = v_jednostka_id
    ORDER BY coalesce("od", '0001-01-01'::date) DESC
    LIMIT 1;

    IF FOUND THEN
        UPDATE bpp_jednostka
           SET wydzial_id = v_wydzial_id,
               aktualna = v_aktualna
         WHERE id = v_jednostka_id;
    ELSE
        -- Brak wpisów -> wydział NULL, aktualna = false.
        UPDATE bpp_jednostka
           SET wydzial_id = NULL,
               aktualna = false
         WHERE id = v_jednostka_id;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;
