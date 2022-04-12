
-- W tej migracji zmieniamy zachowanie triggerów zajmujących się polem bpp_autor.aktualna_jednostka
-- i bpp_autor.aktualna_funkcja, w taki sposób, aby działały podobnie do triggerów zajmujących się
-- polem bpp_jednostka.wydzial . Chodzi o użycie funckji COALESCE() i użycie dat 1-1-1 oraz 9999-12-31
-- w sytuacji, gdy jeden z zakresów dat ma wartość NULL.

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
        (coalesce("zakonczyl_prace", '9999-12-31'::date) > NOW()::date) AS "aktualny"
    FROM
        bpp_autor_jednostka
    WHERE
        autor_id = $1
    ORDER BY
        (coalesce("rozpoczal_prace", '0001-01-01'::date)) DESC,
        (coalesce("zakonczyl_prace", '9999-12-31'::date)) DESC,
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
        aktualna_funkcja_id = $2,
        aktualny = $3
    WHERE
        id = $4
    """
    p2 = plpy.prepare(q2, ["int", "int", "bool", "int"])

    if len(rv) == 1:
        plpy.execute(p2, [rv[0]["jednostka_id"], rv[0]["funkcja_id"], rv[0]["aktualny"], autor_id])
    else:
        # Ustaw aktualna_jednostka=NULL, aktualna_funkcja=NULL i aktualny=False jeżeli nie ma żadnych wpisów
        plpy.execute(p2, [None, None, False, autor_id])

$BODY$;


COMMIT;
