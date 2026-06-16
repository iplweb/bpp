-- Reverse migracji 0441 — przywraca funkcję plpython3u trigger_tytul_sort
-- oraz 5 triggerów BEFORE INSERT/UPDATE (stan z baseline.sql).
-- Wymaga rozszerzenia plpython3u (obecne aż do finalnego DROP EXTENSION).

CREATE OR REPLACE FUNCTION public.trigger_tytul_sort() RETURNS trigger
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

    ret = tytul_oryginalny.lower().strip()

    for elem in replaces:
      while True:
        if ret.startswith(elem):
          ret = ret[len(elem):]
          continue
        break

    ret = ret.replace("'", "").replace('"', '')

    TD["new"]["tytul_oryginalny_sort"] = ret

    return "modify"
$$;

CREATE TRIGGER bpp_patent_tytul_oryginalny_sort_trigger BEFORE INSERT OR UPDATE ON public.bpp_patent FOR EACH ROW EXECUTE FUNCTION public.trigger_tytul_sort();
CREATE TRIGGER bpp_praca_doktorska_tytul_oryginalny_sort_trigger BEFORE INSERT OR UPDATE ON public.bpp_praca_doktorska FOR EACH ROW EXECUTE FUNCTION public.trigger_tytul_sort();
CREATE TRIGGER bpp_praca_habilitacyjna_tytul_oryginalny_sort_trigger BEFORE INSERT OR UPDATE ON public.bpp_praca_habilitacyjna FOR EACH ROW EXECUTE FUNCTION public.trigger_tytul_sort();
CREATE TRIGGER bpp_wydawnictwo_ciagle_tytul_oryginalny_sort_trigger BEFORE INSERT OR UPDATE ON public.bpp_wydawnictwo_ciagle FOR EACH ROW EXECUTE FUNCTION public.trigger_tytul_sort();
CREATE TRIGGER bpp_wydawnictwo_zwarte_tytul_oryginalny_sort_trigger BEFORE INSERT OR UPDATE ON public.bpp_wydawnictwo_zwarte FOR EACH ROW EXECUTE FUNCTION public.trigger_tytul_sort();
