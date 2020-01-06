BEGIN;



CREATE OR REPLACE FUNCTION bpp_autor_dyscyplina_change()
  RETURNS TRIGGER
  LANGUAGE plpython3u
AS
$$
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
    SELECT %(table)s_autor.id FROM %(table)s, %(table)s_autor
    WHERE dyscyplina_naukowa_id = %(dyscyplina_id)s
      AND %(table)s.rok = %(rok)i
      AND %(table)s.id = %(table)s_autor.rekord_id
      AND %(table)s_autor.autor_id = %(autor_id)i
  """

  for table in ['bpp_wydawnictwo_ciagle',
                'bpp_wydawnictwo_zwarte',
                'bpp_patent']:

    if diff_f1 and (val_f1_old != None):
      plpy.execute(qry % dict(temp_table="dys", table=table, dyscyplina_id=val_f1_old, rok=rok, autor_id=autor_id))

    if diff_f2 and (val_f2_old != None):
      plpy.execute(qry % dict(temp_table="subdys", table=table, dyscyplina_id=val_f2_old, rok=rok, autor_id=autor_id))

    if diff_f1 and (val_f1_old != None):
      plpy.execute("UPDATE %s_autor SET dyscyplina_naukowa_id = %s WHERE id IN (SELECT id FROM dys)" % (table, val_f1_new))
      plpy.execute("DROP TABLE dys")

    if diff_f2 and (val_f2_old != None):
      plpy.execute("UPDATE %s_autor SET dyscyplina_naukowa_id = %s WHERE id IN (SELECT id FROM subdys)" % (table, val_f2_new or "NULL"))
      plpy.execute("DROP TABLE subdys")
$$;


CREATE OR REPLACE FUNCTION bpp_autor_dyscyplina_delete()
  RETURNS TRIGGER
  LANGUAGE plpython3u
AS
$$
  # Uruchamiane w przypadku skasowania wpisu dla roku czyli obiektu Autor_Dyscyplina
  # (tabela bpp_autor_dyscyplina)

  qry = """
    UPDATE %(table)s_autor SET dyscyplina_naukowa_id = NULL WHERE id IN (
      SELECT %(table)s_autor.id
      FROM %(table)s, %(table)s_autor
      WHERE %(table)s.rok = %(rok)i
        AND %(table)s.id = %(table)s_autor.rekord_id
        AND %(table)s_autor.autor_id = %(autor_id)i
    )
  """

  autor_id = TD['old']['autor_id']
  rok = TD['old']['rok']

  for field in ['dyscyplina_naukowa_id', 'subdyscyplina_naukowa_id']:
    if TD['old'][field] is None:
      continue

    for table in ['bpp_wydawnictwo_ciagle',
                  'bpp_wydawnictwo_zwarte',
                  'bpp_patent']:
      plpy.execute(qry % dict(table=table, autor_id=autor_id, rok=rok))
$$;


CREATE OR REPLACE FUNCTION bpp_autor_dyscyplina_rozne()
  RETURNS TRIGGER
  LANGUAGE plpython3u
AS
$$
  # Sprawdz czy dyscyplina_naukowa i subdyscyplina_naukowa sa rozne
  if TD['new']['dyscyplina_naukowa_id'] == TD['new']['subdyscyplina_naukowa_id']:
    plpy.error("Dyscypliny muszą być różne")

$$;

DROP TRIGGER IF EXISTS bpp_autor_dyscyplina_rozne_trigger ON bpp_autor_dyscyplina;

CREATE TRIGGER bpp_autor_dyscyplina_rozne_trigger
  AFTER INSERT OR UPDATE
  ON bpp_autor_dyscyplina
  FOR EACH ROW
EXECUTE PROCEDURE bpp_autor_dyscyplina_rozne();

DROP TRIGGER IF EXISTS bpp_autor_dyscyplina_update_trigger ON bpp_autor_dyscyplina;

CREATE TRIGGER bpp_autor_dyscyplina_update_trigger
  AFTER UPDATE
  ON bpp_autor_dyscyplina
  FOR EACH ROW
EXECUTE PROCEDURE bpp_autor_dyscyplina_change();

DROP TRIGGER IF EXISTS bpp_autor_dyscyplina_delete_trigger ON bpp_autor_dyscyplina;

CREATE TRIGGER bpp_autor_dyscyplina_delete_trigger
  AFTER DELETE
  ON bpp_autor_dyscyplina
  FOR EACH ROW
EXECUTE PROCEDURE bpp_autor_dyscyplina_delete();

COMMIT;
