BEGIN;

-- Ten plik ma stworzyc 2 triggery:
-- 1) gdy zmieniono nazwe w tabeli 'wydawca' to wszystkie rekordy powiazane
--    maja miec przebudowe opisu (z cache)
-- 2) gdy dodano, usunieto lub zmieniono 'poziom_wydawcy' to wszystkie rekordy
--    na dany rok maja miec przebudowe opisu (celem przebudowy punktacji) w cache
--    + dodatkowo gdy w tabeli poziom_wydawcy zmienia sie ID wydawcy lub rok to blad

-- trigger 1
-- Zmiana nazwy w tabeli wydawca LUB usunięcie rekordu wydawcy

CREATE OR REPLACE FUNCTION bpp_wydawca_change()
  RETURNS TRIGGER
  LANGUAGE plpython3u
AS
$$
  # Uruchamiane w przypadku zmiany nazwy obiektu Wydawca
  # (tabela bpp_wydawca)

  if TD['event'] == 'UPDATE':

    if TD['new']['id'] != TD['old']['id']:
      plpy.error("Zmiana ID nie jest obslugiwana")
      return

    if TD['new']['nazwa'] == TD['old']['nazwa']:
      return

  qry = """
    CREATE TEMP TABLE %(temp_table)s AS
    SELECT id AS rekord_id
    FROM %(table)s
    WHERE wydawca_id = %(wydawca_id)s
  """

  cqueue = """
  INSERT INTO bpp_cachequeue
  (created_on, last_updated_on, error, object_id, content_type_id)
  SELECT NOW(), NOW(), 'false', rekord_id, %(content_type_id)s FROM %(temp_table)s
  """

  notification = False

  for table in ['bpp_wydawnictwo_zwarte',
                'bpp_praca_doktorska',
                'bpp_praca_habilitacyjna',]:

    rv = plpy.execute("SELECT id FROM django_content_type WHERE app_label = 'bpp' AND model = '%s'" % table[4:], 1)
    content_type_id = rv[0]['id']

    plpy.execute(qry % dict(temp_table="wyd", table=table, wydawca_id=TD['old']['id']))

    rv = plpy.execute("SELECT COUNT(rekord_id) AS cnt FROM wyd")
    res = rv[0]['cnt']

    if res:
      plpy.execute(cqueue % dict(temp_table="wyd", content_type_id=content_type_id))
      notification = True

    plpy.execute("DROP TABLE wyd")

  if notification:
    plpy.execute("NOTIFY cachequeue")
$$;


DROP TRIGGER IF EXISTS bpp_wydawca_change_trigger ON bpp_wydawca;

CREATE TRIGGER bpp_wydawca_change_trigger
  AFTER DELETE OR UPDATE
  ON bpp_wydawca
  FOR EACH ROW
EXECUTE PROCEDURE bpp_wydawca_change();


-- trigger 2
-- dodanie, zmiana lub usuniecie poziomu wydawcy

CREATE OR REPLACE FUNCTION bpp_poziom_wydawcy_change_trigger()
  RETURNS TRIGGER
  LANGUAGE plpython3u
AS
$$
  # Uruchamiane w przypadku zmiany nazwy obiektu Poziom_Wydawcy
  # (tabela bpp_poziom_wydawcy)

  if TD['event'] == 'INSERT' or TD['event'] == "UPDATE":
    rok = TD['new']['rok']
    wydawca_id = TD['new']['wydawca_id']

  if TD['event'] == 'DELETE':
    rok = TD['old']['rok']
    wydawca_id = TD['old']['wydawca_id']

  if TD['event'] == 'UPDATE':
    if TD['new']['rok'] != TD['old']['rok']:
      plpy.error("Zmiana roku nie jest obslugiwana")
      return

    if TD['new']['wydawca_id'] != TD['old']['wydawca_id']:
      plpy.error("Zmiana id wydawcy nie jest obslugiwana")
      return

    if TD['new']['poziom'] == TD['old']['poziom']:
      return

  qry = """
    CREATE TEMP TABLE %(temp_table)s AS
    SELECT id AS rekord_id
    FROM %(table)s
    WHERE wydawca_id = %(wydawca_id)s AND rok = %(rok)i
  """

  count_qry = """
    SELECT COUNT(id) AS cnt
    FROM %(table)s
    WHERE wydawca_id = %(wydawca_id)s AND rok = %(rok)i
  """

  notification = False

  for table in ['bpp_wydawnictwo_zwarte',
                'bpp_praca_doktorska',
                'bpp_praca_habilitacyjna',]:

    rv = plpy.execute(count_qry % dict(table=table, wydawca_id=wydawca_id, rok=rok))
    cnt = rv[0]['cnt']
    if cnt:
      plpy.execute(qry % dict(temp_table="wyd", table=table, wydawca_id=wydawca_id, rok=rok))

      rv = plpy.execute("SELECT id FROM django_content_type WHERE app_label = 'bpp' AND model = '%s'" % table[4:], 1)
      content_type_id = rv[0]['id']

      cqueue = """
      INSERT INTO bpp_cachequeue
      (created_on, last_updated_on, error, object_id, content_type_id)
      SELECT NOW(), NOW(), 'false', rekord_id, %(content_type_id)s FROM %(temp_table)s
      """

      plpy.execute(cqueue % dict(temp_table="wyd", content_type_id=content_type_id))
      notification = True

      plpy.execute("DROP TABLE wyd")

  if notification:
    plpy.execute("NOTIFY cachequeue")
$$;


DROP TRIGGER IF EXISTS bpp_poziom_wydawcy_change_trigger ON bpp_poziom_wydawcy;

CREATE TRIGGER bpp_poziom_wydawcy_change_trigger
  AFTER INSERT OR DELETE OR UPDATE
  ON bpp_poziom_wydawcy
  FOR EACH ROW
EXECUTE PROCEDURE bpp_poziom_wydawcy_change_trigger();

COMMIT;
