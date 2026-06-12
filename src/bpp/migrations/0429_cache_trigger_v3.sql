-- Trigger cache v3 (spec docs/deweloper/spec-optymalizacje-wydajnosci-2026-06.md,
-- pkt 1.1 / 1.2 / 1.4). Widoki per-typ bez zmian (stan po 0421) — podmieniamy
-- wylacznie funkcje bpp_refresh_cache().
--
-- Zmiany wzgledem v2 (0421):
--
-- 1. INSERT/UPDATE bez wstepnego DELETE — wiersz tabeli bazowej nigdy nie
--    znika z wlasnego widoku per-typ (widoki *_view to czyste SELECT-y
--    z GROUP BY po PK), wiec ON CONFLICT (id) DO UPDATE wystarcza.
--    Poprzednio DELETE na bpp_rekord_mat kaskadowal (FK) na bpp_autorzy_mat,
--    wymuszajac wipe + re-insert WSZYSTKICH autorow przy kazdej edycji
--    publikacji; czysty upsert to zwykly UPDATE (HOT-friendly, bez churnu
--    indeksow przy niezmienionych kolumnach indeksowanych).
--
-- 2. Edycje publikacji ciagle/zwarte/patent NIE odswiezaja bpp_autorzy_mat —
--    wiersze autorow pochodza wylacznie z tabel *_autor (widoki *_autorzy
--    to SELECT bez WHERE z tabeli through). Praca_doktorska/habilitacyjna:
--    autor lezy na wierszu publikacji, a widok *_autorzy ma INNER JOIN do
--    bpp_autor — wiersz moze "wypasc" ze zrodla, wiec tam zostaje
--    DELETE + INSERT (dokladnie 1 wiersz, tanio).
--
-- 3. UPDATE czyta TD["new"] (nie TD["old"]) — zmiana autor_id / rekord_id
--    in-place na wierszu *_autor aktualizuje wiersz mat przez ON CONFLICT
--    po stabilnym id = ARRAY[ct, pk-wiersza-through], zamiast go gubic
--    (v2 filtrowala widok po STARYM autor_id -> pusty SELECT).
--
-- 4. DELETE wiersza *_autor kasuje precyzyjnie po id wiersza mat
--    (ARRAY[ct, pk-wiersza-through]) — v2 kasowala po (rekord_id, autor_id),
--    co przy autorze w dwoch rolach (aut. + red.) usuwalo OBA wiersze.
--
-- 5. Bez plpy.subtransaction() — kazde odpalenie zuzywalo subxact (XID);
--    >64 subxactow w jednej transakcji (masowy import, rebuildall) to spill
--    do SLRU pg_subtrans i ostry spadek wydajnosci sprawdzania widocznosci.
--    Subtransakcja niczego tu nie lapala (brak try/except) — blad i tak
--    propaguje i wycofuje transakcje.
BEGIN;

CREATE OR REPLACE FUNCTION bpp_refresh_cache()
  RETURNS TRIGGER
  LANGUAGE plpython3u
  AS $$
    # Odswieza bpp_rekord_mat / bpp_autorzy_mat dla POJEDYNCZEGO rekordu.
    # v3 — patrz naglowek pliku 0429_cache_trigger_v3.sql.

    table_name = TD["table_name"]
    event = TD["event"]
    # DELETE: tozsamosc ze starego wiersza. INSERT/UPDATE: z nowego —
    # dzieki temu zmiana autor_id/rekord_id in-place trafia w aktualne dane.
    field = "old" if event == "DELETE" else "new"

    # Routing: tabela triggera -> (bazowa tabela publikacji, czy to through-table autorow)
    ROUTING = {
        "bpp_wydawnictwo_ciagle":       ("bpp_wydawnictwo_ciagle", False),
        "bpp_wydawnictwo_ciagle_autor": ("bpp_wydawnictwo_ciagle", True),
        "bpp_wydawnictwo_zwarte":       ("bpp_wydawnictwo_zwarte", False),
        "bpp_wydawnictwo_zwarte_autor": ("bpp_wydawnictwo_zwarte", True),
        "bpp_patent":                   ("bpp_patent", False),
        "bpp_patent_autor":             ("bpp_patent", True),
        "bpp_praca_doktorska":          ("bpp_praca_doktorska", False),
        "bpp_praca_habilitacyjna":      ("bpp_praca_habilitacyjna", False),
    }
    pub_base, is_through = ROUTING[table_name]
    app_name, model_name = pub_base.split("_", 1)

    # Publikacje, ktorych dane autora leza na wierszu publikacji (widok
    # *_autorzy z INNER JOIN do bpp_autor — wiersz moze wypasc ze zrodla).
    AUTOR_NA_WIERSZU_PUBLIKACJI = ("bpp_praca_doktorska", "bpp_praca_habilitacyjna")

    # object_id = PK publikacji (dla through-table jest w rekord_id, inaczej w id)
    object_id = TD[field]["rekord_id"] if is_through else TD[field]["id"]

    # cache content_type_id oraz listy kolumn w GD (per-backend, na czas polaczenia)
    cache_key = "django_content_type_ver_2"
    columns_cache_key = "table_columns_ver_2"
    if GD.get(cache_key) is None:
        GD[cache_key] = {}
    if GD.get(columns_cache_key) is None:
        GD[columns_cache_key] = {}

    if pub_base not in GD[cache_key]:
        res = plpy.execute(
            "SELECT id FROM django_content_type "
            "WHERE app_label = '%s' AND model = '%s'" % (app_name, model_name))
        GD[cache_key][pub_base] = res[0]["id"]
    content_type_id = GD[cache_key][pub_base]

    rekord_view = pub_base + "_view"
    autorzy_view = pub_base + "_autorzy"

    mat_arr = "ARRAY[%s, %s]::INTEGER[2]" % (content_type_id, object_id)

    def get_table_columns(mat_table):
        if mat_table not in GD[columns_cache_key]:
            res = plpy.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = '%s' "
                "ORDER BY ordinal_position" % mat_table)
            GD[columns_cache_key][mat_table] = [r["column_name"] for r in res]
        return GD[columns_cache_key][mat_table]

    def upsert(mat_table, source_view, source_where):
        # INSERT ... SELECT ... ON CONFLICT (id) DO UPDATE — bez wstepnego
        # DELETE (patrz naglowek pliku, pkt 1).
        # INSERT po nazwach kolumn tabeli mat, SELECT po nazwach kolumn widoku.
        # Odpowiadaja sobie POZYCYJNIE: widok to zrodlo tabeli mat + dorzucone
        # na koncu object_id_raw. Mapowanie pozycyjne (a nie po nazwie) jest
        # odporne na to, ze pojedynczy widok moze nazwac kolumne-tablice inaczej
        # niz tabela mat — np. bpp_praca_doktorska_autorzy ma 'array' zamiast
        # 'id' (nieaaliasowane ARRAY[...]); unia normalizowala nazwe z pierwszej
        # galezi, ale pojedynczy widok juz nie.
        # Cytujemy identyfikatory ("...") — niektore kolumny widokow nazywaja
        # sie jak slowa zarezerwowane (np. 'array').
        def q(c):
            return '"' + c + '"'

        mat_cols = get_table_columns(mat_table)
        src_cols = [c for c in get_table_columns(source_view) if c != "object_id_raw"]
        set_clause = ", ".join(
            "%s = EXCLUDED.%s" % (q(c), q(c)) for c in mat_cols if c != "id")
        plpy.execute(
            "INSERT INTO " + mat_table +
            " (" + ", ".join(q(c) for c in mat_cols) + ") "
            "SELECT " + ", ".join(q(c) for c in src_cols) + " FROM " + source_view +
            " WHERE " + source_where +
            " ON CONFLICT (id) DO UPDATE SET " + set_clause)

    # Deterministyczny advisory lock (#309): para int4 (ct, obj).
    plpy.execute("SELECT pg_advisory_xact_lock(%s, %s)" % (content_type_id, object_id))

    if event == "DELETE":
        if is_through:
            # Precyzyjnie po id wiersza mat = ARRAY[ct, pk-wiersza-through].
            # NIE po (rekord_id, autor_id) — autor w dwoch rolach ma dwa
            # wiersze i skasowalibysmy oba (patrz naglowek, pkt 4).
            plpy.execute(
                "DELETE FROM bpp_autorzy_mat "
                "WHERE id = ARRAY[%s, %s]::INTEGER[2]"
                % (content_type_id, TD["old"]["id"]))
        else:
            # DELETE bpp_rekord_mat kaskaduje (FK) na bpp_autorzy_mat.
            plpy.execute("DELETE FROM bpp_rekord_mat WHERE id = " + mat_arr)
        return

    # INSERT / UPDATE
    if is_through:
        # Tylko ten jeden autor; filtr po NOWYCH wartosciach (pkt 3).
        upsert(
            "bpp_autorzy_mat",
            autorzy_view,
            "object_id_raw = %s AND autor_id = %s"
            % (object_id, TD["new"]["autor_id"]))
        return

    upsert("bpp_rekord_mat", rekord_view, "object_id_raw = %s" % object_id)

    if pub_base in AUTOR_NA_WIERSZU_PUBLIKACJI:
        # Widok *_autorzy ma INNER JOIN do bpp_autor — czysty upsert nie
        # usunalby wiersza, gdy zrodlo nie zwraca nic. DELETE + INSERT,
        # dokladnie 1 wiersz autora.
        plpy.execute("DELETE FROM bpp_autorzy_mat WHERE rekord_id = " + mat_arr)
        upsert("bpp_autorzy_mat", autorzy_view, "object_id_raw = %s" % object_id)
    # Dla ciagle/zwarte/patent NIE ruszamy bpp_autorzy_mat: wiersze autorow
    # pochodza wylacznie z tabel *_autor (pkt 2).
$$;

COMMIT;
