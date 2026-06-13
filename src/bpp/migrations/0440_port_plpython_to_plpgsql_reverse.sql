-- Reverse migracji 0440 — przywraca oryginalne wersje plpython3u 7 funkcji.
-- Skopiowane 1:1 z baseline.sql (stan sprzed portu). Wymaga rozszerzenia
-- plpython3u w bazie (jeszcze obecne aż do osobnego DROP EXTENSION w Spec/PR3).

CREATE OR REPLACE FUNCTION public.bpp_autor_dyscyplina_change() RETURNS trigger
    LANGUAGE plpython3u
    AS $$
  # Uruchamiane w przypadku zmiany dyscypliny obiektu Autor_Dyscyplina
  # (tabela bpp_autor_dyscyplina)

  # Ta funkcja wygląda jak wygląda, bo w przypadku zmiany dwóch pól tzn dyscyplina_naukowa
  # oraz subdyscyplina_naukowa, w najgorszym możliwym przypadku -- zamiany jednego z drugim
  # będzie potrzebne właśnie takie przemapowanie rzeczy:

  if TD['new']['rok'] != TD['old']['rok']:
    plpy.error("Zmiana roku NIE jest obsługiwana")
    return

  if TD['new']['autor_id'] != TD['old']['autor_id']:
    plpy.error("Zmiana ID autora nie jest obsługiwana")
    return

  rok = TD['new']['rok']
  autor_id = TD['new']['autor_id']

  f1 = 'dyscyplina_naukowa_id'
  f2 = 'subdyscyplina_naukowa_id'

  val_f1_old = TD['old'][f1]
  val_f1_new = TD['new'][f1]

  val_f2_old = TD['old'][f2]
  val_f2_new = TD['new'][f2]

  diff_f1 = val_f1_old != val_f1_new
  diff_f2 = val_f2_old != val_f2_new

  # Brak zmian dyscyplin, wróć
  if not diff_f1 and not diff_f2:
    return

  qry = """
    CREATE TEMP TABLE %(temp_table)s AS
    SELECT %(table)s_autor.id, %(table)s_autor.rekord_id FROM %(table)s, %(table)s_autor
    WHERE dyscyplina_naukowa_id = %(dyscyplina_id)s
      AND %(table)s.rok = %(rok)i
      AND %(table)s.id = %(table)s_autor.rekord_id
      AND %(table)s_autor.autor_id = %(autor_id)i
  """

  cqueue = """
  INSERT INTO denorm_dirtyinstance(content_type_id, object_id) SELECT %(content_type_id)s, rekord_id FROM %(table)s ON CONFLICT DO NOTHING
  """

  for table in ['bpp_wydawnictwo_ciagle',
                'bpp_wydawnictwo_zwarte',
                'bpp_patent']:

    rv = plpy.execute("SELECT id FROM django_content_type WHERE app_label = 'bpp' AND model = '%s'" % table[4:], 1)
    content_type_id = rv[0]['id']

    if diff_f1 and (val_f1_old != None):
      plpy.execute(qry % dict(temp_table="dys", table=table, dyscyplina_id=val_f1_old, rok=rok, autor_id=autor_id))

    if diff_f2 and (val_f2_old != None):
      plpy.execute(qry % dict(temp_table="subdys", table=table, dyscyplina_id=val_f2_old, rok=rok, autor_id=autor_id))

    if diff_f1 and (val_f1_old != None):
      plpy.execute("UPDATE %s_autor SET dyscyplina_naukowa_id = %s WHERE id IN (SELECT id FROM dys)" % (table, val_f1_new))
      plpy.execute(cqueue % dict(table="dys", content_type_id=content_type_id))
      plpy.execute("DROP TABLE dys")

    if diff_f2 and (val_f2_old != None):
      plpy.execute("UPDATE %s_autor SET dyscyplina_naukowa_id = %s WHERE id IN (SELECT id FROM subdys)" % (table, val_f2_new or "NULL"))
      plpy.execute(cqueue % dict(table="subdys", content_type_id=content_type_id))
      plpy.execute("DROP TABLE subdys")
$$;


CREATE OR REPLACE FUNCTION public.bpp_autor_dyscyplina_delete() RETURNS trigger
    LANGUAGE plpython3u
    AS $$
  # Uruchamiane w przypadku skasowania wpisu dla roku czyli obiektu Autor_Dyscyplina
  # (tabela bpp_autor_dyscyplina)

  cqueue = """
  INSERT INTO denorm_dirtyinstance(content_type_id, object_id) SELECT %(content_type_id)s, rekord_id FROM %(table)s ON CONFLICT DO NOTHING
  """

  autor_id = TD['old']['autor_id']
  rok = TD['old']['rok']

  for field in ['dyscyplina_naukowa_id', 'subdyscyplina_naukowa_id']:
    if TD['old'][field] is None:
      continue

    for table in ['bpp_wydawnictwo_ciagle',
                  'bpp_wydawnictwo_zwarte',
                  'bpp_patent']:
      rv = plpy.execute("SELECT id FROM django_content_type WHERE app_label = 'bpp' AND model = '%s'" % table[4:], 1)
      content_type_id = rv[0]['id']

      plpy.execute("""
      CREATE TEMP TABLE dys AS
      SELECT %(table)s_autor.id, %(table)s_autor.rekord_id
      FROM %(table)s, %(table)s_autor
      WHERE %(table)s.rok = %(rok)i
        AND %(table)s.id = %(table)s_autor.rekord_id
        AND %(table)s_autor.autor_id = %(autor_id)i
      """ % dict(table=table, autor_id=autor_id, rok=rok))
      plpy.execute("UPDATE %(table)s_autor SET dyscyplina_naukowa_id = NULL WHERE id IN (SELECT id FROM dys)" % dict(table=table))
      plpy.execute(cqueue % dict(content_type_id=content_type_id, table="dys"))
      plpy.execute("DROP TABLE dys")

$$;


CREATE OR REPLACE FUNCTION public.bpp_autor_dyscyplina_rozne() RETURNS trigger
    LANGUAGE plpython3u
    AS $$
  # Sprawdz czy dyscyplina_naukowa i subdyscyplina_naukowa sa rozne
  if TD['new']['dyscyplina_naukowa_id'] == TD['new']['subdyscyplina_naukowa_id']:
    plpy.error("Dyscypliny muszą być różne")

$$;


CREATE OR REPLACE FUNCTION public.bpp_autor_ustaw_jednostka_aktualna() RETURNS trigger
    LANGUAGE plpython3u
    AS $_$

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

$_$;


CREATE OR REPLACE FUNCTION public.bpp_jednostka_sprawdz_uczelnia_id() RETURNS trigger
    LANGUAGE plpython3u
    AS $$
    uczelnia_id = TD["new"]["uczelnia_id"]
    wydzial_id = TD["new"]["wydzial_id"]

    if wydzial_id is not None:
        q = "SELECT uczelnia_id FROM bpp_wydzial WHERE id = %i" % wydzial_id
        r = plpy.execute(q)
        assert r[0]["uczelnia_id"] == uczelnia_id, "Uczelnia jednostki i wydzialu musi byc identyczna"

$$;


CREATE OR REPLACE FUNCTION public.bpp_jednostka_ustaw_wydzial_aktualna() RETURNS trigger
    LANGUAGE plpython3u
    AS $_$
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

$_$;


CREATE OR REPLACE FUNCTION public.bpp_jednostka_wydzial_sprawdz_uczelnia_id() RETURNS trigger
    LANGUAGE plpython3u
    AS $$
    jednostka_id = TD["new"]["jednostka_id"]
    wydzial_id = TD["new"]["wydzial_id"]

    if wydzial_id is not None:
      q1 = "SELECT uczelnia_id FROM bpp_wydzial WHERE id = %i" % wydzial_id
      q2 = "SELECT uczelnia_id FROM bpp_jednostka WHERE id = %i" % jednostka_id

      r1 = plpy.execute(q1)
      r2 = plpy.execute(q2)

      assert r1[0]["uczelnia_id"] == r2[0]["uczelnia_id"], "Uczelnia jednostki i wydzialu musi byc identyczna"

$$;
