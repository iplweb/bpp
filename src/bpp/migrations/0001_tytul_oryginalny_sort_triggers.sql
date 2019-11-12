
BEGIN;

-- Funkcja w PL/PYTHON sprawdzającą JEZYK DOKUMENTU
-- przyjmującą domyślnie POLSKI jeżeli nie jest podany i wycinającą znaki
-- z początku tytułu
-- znaki te NIE są tożsame ze stopwords

CREATE OR REPLACE FUNCTION trigger_tytul_sort()
  RETURNS TRIGGER
  LANGUAGE plpython3u
AS $$
    if TD["new"]["tytul_oryginalny_sort"]:
      # Jeżeli jest coś w tym polu, to sprawdź, może nie warto go zmieniać
      # jeżeli nie, to uzupełnij je.
      if TD["event"] == "UPDATE":
          if TD["new"]["tytul_oryginalny"] == TD["old"]["tytul_oryginalny"]:
              if TD["new"].get("jezyk_id") == TD["old"].get("jezyk_id"):
                return

    version = "get_tytul_sort_ver_6_initialized"
    cache = version + "_cache"

    jezyk_id = TD["new"].get("jezyk_id", None)

    if jezyk_id is not None:
        # ma jezyk_id

        if GD.get(cache) is None:
            # utwórz słownik CACHE
            GD[cache] = {}

        if GD[cache].get(jezyk_id) is None:
            query = "SELECT skrot FROM bpp_jezyk WHERE id = %s" % TD["new"]["jezyk_id"]
            res = plpy.execute(query)
            GD[cache][jezyk_id] = res[0]["skrot"]

        jezyk = GD[cache].get(jezyk_id)

    else:
        jezyk = "pol."


    tytul_oryginalny = TD["new"]["tytul_oryginalny"]

    if not GD.get(version, None):
      GD[version] = {
        'ang.': ["the ", "a "],
        'niem.': ["der ", "die ", "das ", ],
        'fr.': ["la ", "le ", "en "],
        'wł.': ["la ", "en "],
        'hiszp.': ["de ", "la ", "en "]
      }

    replaces = GD.get(version).get(jezyk, [" ", "\t"])

#    if jezyk not in ['ang.', 'pol.']:
#        raise Exception("%r %r %r" % (GD[cache], replaces, jezyk))

    ret = tytul_oryginalny.lower().strip()

    for elem in replaces:
      while True:
        if ret.startswith(elem):
          ret = ret[len(elem):]
          continue
        break

    ret = ret.replace("'", "").replace('"', '')

    #if "test" in ret:
    #     raise Exception("%s.. %s.. %s.. %s.. %s.." % (GD[cache], replaces, jezyk, TD['new']['tytul_oryginalny'], ret))

    TD["new"]["tytul_oryginalny_sort"] = ret

    return "modify"
$$;


DROP TRIGGER IF EXISTS bpp_wydawnictwo_ciagle_tytul_oryginalny_sort_trigger ON bpp_wydawnictwo_ciagle;

CREATE TRIGGER bpp_wydawnictwo_ciagle_tytul_oryginalny_sort_trigger
  BEFORE INSERT OR UPDATE
  ON bpp_wydawnictwo_ciagle
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_tytul_sort();


DROP TRIGGER IF EXISTS bpp_wydawnictwo_zwarte_tytul_oryginalny_sort_trigger ON bpp_wydawnictwo_zwarte;

CREATE TRIGGER bpp_wydawnictwo_zwarte_tytul_oryginalny_sort_trigger
  BEFORE INSERT OR UPDATE
  ON bpp_wydawnictwo_zwarte
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_tytul_sort();

DROP TRIGGER IF EXISTS bpp_patent_tytul_oryginalny_sort_trigger ON bpp_patent;

CREATE TRIGGER bpp_patent_tytul_oryginalny_sort_trigger
  BEFORE INSERT OR UPDATE
  ON bpp_patent
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_tytul_sort();




DROP TRIGGER IF EXISTS bpp_praca_doktorska_tytul_oryginalny_sort_trigger ON bpp_praca_doktorska;

CREATE TRIGGER bpp_praca_doktorska_tytul_oryginalny_sort_trigger
  BEFORE INSERT OR UPDATE
  ON bpp_praca_doktorska
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_tytul_sort();



DROP TRIGGER IF EXISTS bpp_praca_habilitacyjna_tytul_oryginalny_sort_trigger ON bpp_praca_habilitacyjna;

CREATE TRIGGER bpp_praca_habilitacyjna_tytul_oryginalny_sort_trigger
  BEFORE INSERT OR UPDATE
  ON bpp_praca_habilitacyjna
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_tytul_sort();

COMMIT;
