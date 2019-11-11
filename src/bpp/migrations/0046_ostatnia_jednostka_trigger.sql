BEGIN;



CREATE OR REPLACE FUNCTION bpp_autor_jednostka_aktualna_jednostka()
  RETURNS TRIGGER
  LANGUAGE plpython3u
  AS $$
    # Ta funkcja odświeża pole 'ostatnia jednostka' modelu bpp.Autor

    aktualna_jednostka = None
    aktualna_funkcja = None

    try:
        autor_id = TD['new']['autor_id']
    except TypeError: # TypeError: 'NoneType' object has no attribute '__getitem__' dla DELETE-triggerów
        autor_id = TD['old']['autor_id']

    if autor_id is None:
        return

    # Strategia 1 - określone, kiedy rozpoczął pracę i nie określono kiedy zakończył;
    # weź tą, gdzie rozpoczął pracę najpóźniej, jeżeli zaczął w kilku jednocześnie to ostatnią dopisaną do bazy
    # (najwyższe ID)
    if aktualna_jednostka is None:
      query = """
        SELECT
          jednostka_id, funkcja_id
        FROM
          bpp_autor_jednostka
        WHERE
          rozpoczal_prace IS NOT NULL AND
          zakonczyl_prace IS NULL AND
          autor_id = %s
        ORDER BY
          bpp_autor_jednostka.rozpoczal_prace DESC,
          bpp_autor_jednostka.id DESC
      """ % (autor_id)
      res = plpy.execute(query)
      try:
          aktualna_jednostka = res[0]['jednostka_id']
          aktualna_funkcja = res[0]['funkcja_id']
      except IndexError:
          pass

    # Strategia 2 - weź ostatnią dopisaną do bazy (najwyższe ID), w której NIE zakończył pracy
    if aktualna_jednostka is None:
      query = """
        SELECT
          jednostka_id, funkcja_id
        FROM
          bpp_autor_jednostka
        WHERE
          zakonczyl_prace IS NULL AND
          autor_id = %s
        ORDER BY
          bpp_autor_jednostka.rozpoczal_prace DESC,
          bpp_autor_jednostka.id DESC
      """ % (autor_id)
      res = plpy.execute(query)
      try:
          aktualna_jednostka = res[0]['jednostka_id']
          aktualna_funkcja = res[0]['funkcja_id']
      except IndexError:
          pass

    # Strategia 3 - weź ostatnią dopisaną do bazy (najwyższe ID)
    if aktualna_jednostka is None:
      query = """
        SELECT
          jednostka_id, funkcja_id
        FROM
          bpp_autor_jednostka
        WHERE
          autor_id = %s
        ORDER BY
          bpp_autor_jednostka.rozpoczal_prace DESC,
          bpp_autor_jednostka.id DESC
      """ % (autor_id)
      res = plpy.execute(query)
      try:
          aktualna_jednostka = res[0]['jednostka_id']
          aktualna_funkcja = res[0]['funkcja_id']
      except IndexError:
          pass

    if aktualna_jednostka is not None:
        aktualna_jednostka = str(aktualna_jednostka)

    if aktualna_funkcja is not None:
        aktualna_funkcja = str(aktualna_funkcja)

    plpy.execute(
        "UPDATE bpp_autor SET aktualna_jednostka_id = %s, aktualna_funkcja_id = %s WHERE bpp_autor.id = %s" % (
            plpy.quote_nullable(aktualna_jednostka),
            plpy.quote_nullable(aktualna_funkcja),
            autor_id
        ))

$$;


DROP TRIGGER IF EXISTS bpp_autor_jednostka_aktualna_jednostka_trigger ON bpp_autor_jednostka;

CREATE TRIGGER bpp_autor_jednostka_aktualna_jednostka_trigger
  AFTER INSERT OR UPDATE OR DELETE ON bpp_autor_jednostka
  FOR EACH ROW
  EXECUTE PROCEDURE bpp_autor_jednostka_aktualna_jednostka();


UPDATE bpp_autor_jednostka SET id=id;

COMMIT;
