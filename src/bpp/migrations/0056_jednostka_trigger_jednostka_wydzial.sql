BEGIN;

-- trigger sprawdzający, czy pole uczelnia_id dodawanego wydziału oraz czy pole uczelnia_id
-- edytowanej jednostki są takie same (czy wydział przydzielany jednostce jest z tej samej uczelni)
-- dla obiektow wydzial_jednostka


CREATE OR REPLACE FUNCTION bpp_jednostka_wydzial_sprawdz_uczelnia_id()
  RETURNS TRIGGER
AS $$
    jednostka_id = TD["new"]["jednostka_id"]
    wydzial_id = TD["new"]["wydzial_id"]

    if wydzial_id is not None:
      q1 = "SELECT uczelnia_id FROM bpp_wydzial WHERE id = %i" % wydzial_id
      q2 = "SELECT uczelnia_id FROM bpp_jednostka WHERE id = %i" % jednostka_id

      r1 = plpy.execute(q1)
      r2 = plpy.execute(q2)

      assert r1[0]["uczelnia_id"] == r2[0]["uczelnia_id"], "Uczelnia jednostki i wydzialu musi byc identyczna"

$$ LANGUAGE plpython3u;


DROP TRIGGER IF EXISTS bpp_jednostka_wydzial_sprawdz_uczelnia_id_trigger ON bpp_jednostka_wydzial;

CREATE TRIGGER bpp_jednostka_wydzial_sprawdz_uczelnia_id_trigger
  BEFORE INSERT OR UPDATE ON bpp_jednostka_wydzial
  FOR EACH ROW
  EXECUTE PROCEDURE bpp_jednostka_wydzial_sprawdz_uczelnia_id();

-- trigger sprawdzający, czy pole uczelnia_id jednostki oraz pole uczelnia_id wydzialu
-- z id okreslonym w polu wydzial_id dla tabeli bpp_jednostka sa identyczne
-- (czy wydział przydzielany jednostce jest z tej samej uczelni)

CREATE OR REPLACE FUNCTION bpp_jednostka_sprawdz_uczelnia_id()
  RETURNS TRIGGER
AS $$
    uczelnia_id = TD["new"]["uczelnia_id"]
    wydzial_id = TD["new"]["wydzial_id"]

    if wydzial_id is not None:
        q = "SELECT uczelnia_id FROM bpp_wydzial WHERE id = %i" % wydzial_id
        r = plpy.execute(q)
        assert r[0]["uczelnia_id"] == uczelnia_id, "Uczelnia jednostki i wydzialu musi byc identyczna"

$$ LANGUAGE plpython3u;


DROP TRIGGER IF EXISTS bpp_jednostka_sprawdz_uczelnia_id_trigger ON bpp_jednostka;

CREATE TRIGGER bpp_jednostka_sprawdz_uczelnia_id_trigger
  BEFORE INSERT OR UPDATE ON bpp_jednostka
  FOR EACH ROW
  EXECUTE PROCEDURE bpp_jednostka_sprawdz_uczelnia_id();


-- trigger wypełniający pole "wydzial" i "aktualna" dla jednostki

CREATE OR REPLACE FUNCTION bpp_jednostka_ustaw_wydzial_aktualna()
  RETURNS TRIGGER
AS $$
    action = "new"
    if TD["event"] == "DELETE":
        action = "old"

    if TD["event"] == "UPDATE":
        if TD["new"]["jednostka_id"] != TD["old"]["jednostka_id"]:
            raise Exception("zmiana ID jednostki nie jest obsługiwana przez trigger")

    jednostka_id = TD[action]["jednostka_id"]
    q1 = """
    SELECT
        wydzial_id,
        (coalesce("do", '9999-12-31'::date) > NOW()::date) AS "aktualna"
    FROM
        bpp_jednostka_wydzial
    WHERE
        jednostka_id = $1
    ORDER BY
        (coalesce("od", '0001-01-01'::date)) DESC
    LIMIT
        1
    """

    p1 = plpy.prepare(q1, ["int"])
    rv = plpy.execute(p1, [jednostka_id])

    q2 = """
    UPDATE
        bpp_jednostka
    SET
        wydzial_id = $1,
        aktualna = $2
    WHERE
        id = $3
    """
    p2 = plpy.prepare(q2, ["int", "bool", "int"])

    if len(rv) == 1:
        plpy.execute(p2, [rv[0]["wydzial_id"], rv[0]["aktualna"], jednostka_id])
    else:
        # Ustaw wydział=NULL i aktualna=False jeżeli nie ma żadnych wpisów
        plpy.execute(p2, [None, False, jednostka_id])

$$ LANGUAGE plpython3u;

DROP TRIGGER IF EXISTS bpp_jednostka_ustaw_wydzial_aktualna_trigger ON bpp_jednostka_wydzial;

CREATE TRIGGER bpp_jednostka_ustaw_wydzial_aktualna_trigger
  AFTER INSERT OR UPDATE OR DELETE ON bpp_jednostka_wydzial
  FOR EACH ROW
  EXECUTE PROCEDURE bpp_jednostka_ustaw_wydzial_aktualna();

-- Constraint sprawdzający czy się zakresy nie pokrywają

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE bpp_jednostka_wydzial
  DROP CONSTRAINT IF EXISTS unikalny_zakres_dat_dla_jednostki;

ALTER TABLE bpp_jednostka_wydzial
  ADD CONSTRAINT unikalny_zakres_dat_dla_jednostki
    EXCLUDE  USING gist
    ( jednostka_id WITH =,
      daterange(coalesce("od", '0001-01-01'::date), coalesce("do", '9999-12-31'), '[]') WITH &&
    );

ALTER TABLE bpp_jednostka_wydzial
  ADD CONSTRAINT bez_dat_do_w_przyszlosci
    CHECK ("do" < NOW()::date);

-- constraints ze OD ma byc wieksze niz DO jest już zapewniony przez unikalny_zakres_dat_dla_jednostki

COMMIT;
