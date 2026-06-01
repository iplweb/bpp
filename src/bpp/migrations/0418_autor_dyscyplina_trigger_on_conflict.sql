BEGIN;

-- denorm 1.11.0 dodaje UNIQUE index `denorm_dirtyinstance_unique` na
-- (content_type_id, COALESCE(object_id, -1), COALESCE(func_name, '')).
-- Wlasne triggery BPP (ponizej) enqueue'uja rekordy do denorm_dirtyinstance
-- surowym INSERT-em z pominieciem maszynerii denorma, ktora swoje wlasne
-- INSERT-y owija w `BEGIN ... EXCEPTION WHEN unique_violation THEN -- nic END`.
-- Bez ON CONFLICT te recznie pisane INSERT-y wpadaja w UniqueViolation, gdy ten
-- sam (content_type_id, rekord_id) jest juz w kolejce (np. powtorka miedzy
-- iteracjami petli po tabelach / polach). Dodajemy `ON CONFLICT DO NOTHING`
-- (bez conflict-target — lapie kazdy unique_violation), co odwzorowuje idiom
-- denorma i jest no-opem na starym denormie bez tego indeksu.
--
-- NIE edytujemy 0302 (zakaz modyfikacji istniejacych migracji) — CREATE OR
-- REPLACE podmienia tylko cialo funkcji; istniejace triggery wiaza sie po
-- nazwie, wiec nie wymagaja odtworzenia.

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


CREATE OR REPLACE FUNCTION bpp_autor_dyscyplina_delete()
  RETURNS TRIGGER
  LANGUAGE plpython3u
AS
$$
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

COMMIT;
