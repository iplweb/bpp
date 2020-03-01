BEGIN;


-- trigger 3
-- zmiana aliasu wydawcy

CREATE OR REPLACE FUNCTION bpp_alias_wydawcy_change_trigger()
  RETURNS TRIGGER
  LANGUAGE plpython3u
AS
$$
  new_alias_dla_id = TD['new']['alias_dla_id']
  old_alias_dla_id = TD['old']['alias_dla_id']

  if new_alias_dla_id == old_alias_dla_id:
    return

  wydawca_id = TD['new']['id']

  qry = """
    CREATE TEMP TABLE %(temp_table)s AS
    SELECT id AS rekord_id
    FROM %(table)s
    WHERE wydawca_id = %(wydawca_id)s
  """

  count_qry = """
    SELECT COUNT(id) AS cnt
    FROM %(table)s
    WHERE wydawca_id = %(wydawca_id)s
  """

  notification = False

  for table in ['bpp_wydawnictwo_zwarte',
                'bpp_praca_doktorska',
                'bpp_praca_habilitacyjna',]:

    rv = plpy.execute(count_qry % dict(table=table, wydawca_id=wydawca_id))
    cnt = rv[0]['cnt']
    if cnt:
      plpy.execute(qry % dict(temp_table="wyd", table=table, wydawca_id=wydawca_id))

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


DROP TRIGGER IF EXISTS bpp_alias_wydawcy_change_trigger ON bpp_wydawca;

CREATE TRIGGER bpp_alias_wydawcy_change_trigger
  AFTER UPDATE
  ON bpp_wydawca
  FOR EACH ROW
EXECUTE PROCEDURE bpp_alias_wydawcy_change_trigger();

COMMIT;
