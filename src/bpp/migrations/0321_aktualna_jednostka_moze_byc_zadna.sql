
-- W tej migracji zmieniamy zachowanie triggerów zajmujących się polem bpp_autor.aktualna_jednostka
-- i bpp_autor.aktualna_funkcja, w taki sposób, ze w sytuacji, gdzie nie da sie okreslic aktualnej
-- jednostki, bo autor zadnej nie ma przypisanej -- to dostanie tam NULL

BEGIN;

CREATE OR REPLACE FUNCTION bpp_autor_ustaw_jednostka_aktualna()
    RETURNS trigger
    LANGUAGE 'plpython3u'
AS $BODY$

    action = "new"
    if TD["event"] == "DELETE":
        action = "old"

    if TD["event"] == "UPDATE":
        if TD["new"]["autor_id"] != TD["old"]["autor_id"]:
            raise Exception("zmiana ID autora nie jest obsługiwana przez trigger")

    autor_id = TD[action]["autor_id"]
    q1 = """
    SELECT
        jednostka_id,
        funkcja_id,
        (coalesce("podstawowe_miejsce_pracy", false)) AS podstawowe_miejsce_pracy,
        (coalesce("rozpoczal_prace", '0001-01-01'::date)) AS data_rozpoczecia,
        (coalesce("zakonczyl_prace", '9999-12-31'::date)) AS data_zakonczenia
    FROM
        bpp_autor_jednostka
    WHERE
        autor_id = $1 AND
        coalesce("zakonczyl_prace", '9999-12-31'::date) > NOW()::date
    ORDER BY
        podstawowe_miejsce_pracy DESC,
        data_rozpoczecia DESC,
        data_zakonczenia DESC,
        bpp_autor_jednostka.id DESC
    LIMIT
        1
    """

    p1 = plpy.prepare(q1, ["int"])
    rv = plpy.execute(p1, [autor_id])

    q2 = """
    UPDATE
        bpp_autor
    SET
        aktualna_jednostka_id = $1,
        aktualna_funkcja_id = $2
    WHERE
        id = $3
    """
    p2 = plpy.prepare(q2, ["int", "int", "int"])

    if len(rv) == 1:
        plpy.execute(p2, [rv[0]["jednostka_id"], rv[0]["funkcja_id"], autor_id])
    else:
        # Ustaw aktualna_jednostka=NULL, aktualna_funkcja=NULL i aktualny=False jeżeli nie ma żadnych wpisów
        plpy.execute(p2, [None, None, autor_id])

$BODY$;


COMMIT;
