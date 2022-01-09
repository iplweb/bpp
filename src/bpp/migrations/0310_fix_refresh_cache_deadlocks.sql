

CREATE OR REPLACE FUNCTION bpp_refresh_cache()
  RETURNS TRIGGER
  LANGUAGE plpython3u
  AS $$
    # Ta funkcja odświeża tabele bpp_rekord_mat oraz bpp_autorzy_mat na podstawie
    # selectu z widoków bpp_rekord oraz bpp_autorzy. Kluczem do rozpoznania
    # rekordu są pola (content_type_id, object_id), gdzie object_id to
    # unikalne ID rekordu w danej oryginalnej tabeli (czyli tej, na podstawie
    # której cache jest generowane), zaś content_type_id jest to ID obiektu
    # z tabeli django_content_type

    # cache tabeli django_content_type
    cache_key = "django_content_type_ver_1"
    table_name = TD["table_name"]
    app_name, model_name = table_name.split("_", 1)

    # domyślnie odśwież tylko tabelę rekordów
    refresh_rekord = True
    refresh_autor = False

    # jaki to trigger? może być insert, update lub delete, gdzie szukać ID obiektu
    trigger_field_name = "new"
    if TD['event'] in ["DELETE", "UPDATE"]:
        trigger_field_name = "old"

    # jezeli tabela z której uruchamiany jest trigger to tabela autorow, to
    # object_id jest w polu 'rekord_id'
    TABELE_AUTORSKIE = ['bpp_wydawnictwo_ciagle_autor', 'bpp_wydawnictwo_zwarte_autor', 'bpp_patent_autor']
    id_field_name = 'id'
    extra_where = ''
    if table_name in TABELE_AUTORSKIE:
        id_field_name = 'rekord_id'
        # ... i wyrzuc "_autor" z nazwy modelu
        model_name = model_name.replace("_autor", "")
        # ... i nie odświeżaj tabeli rekordów
        refresh_autor = True
        refresh_rekord = False
        # ... i jeszcze dorzuć ekstra zapytanie dla konkretnego autora, żeby nie robić
        # dla 50ciu autorów 50ciu tych samych zapytań
        extra_where = ' AND autor_id = %s' % TD[trigger_field_name]['autor_id']

    object_id = TD[trigger_field_name][id_field_name]

    if GD.get(cache_key) is None:
        GD[cache_key] = {}

    try:
        content_type_id = GD[cache_key][table_name]
    except KeyError:
        query = "SELECT id FROM django_content_type WHERE app_label = '%s' AND model = '%s'" % (app_name, model_name)
        res = plpy.execute(query)
        GD[cache_key][table_name] = res[0]['id']
        content_type_id = GD[cache_key][table_name]

    if TD["table_name"] in ["bpp_praca_doktorska", "bpp_praca_habilitacyjna"]:
        # Odśwież również tabelę autorzy za pomocą tej funkcji
        refresh_autor = True

    where = "WHERE %%s = ARRAY[%s, %s]::INTEGER[2]" % (content_type_id, object_id)
    where += extra_where

    refresh_tables = []

    if refresh_rekord:
        refresh_tables.append(("bpp_rekord_mat", "id"))
        # Aktualizacja bpp_rekord_mat skasuje rowniez wpisy w bpp_autorzy_mat
        # jezeli aktualizujemy np tylko opis bibliograficzny, to autorzy znikna.
        refresh_tables.append(("bpp_autorzy_mat", "rekord_id"))

    if refresh_autor:
        if "bpp_autorzy_mat" not in refresh_tables:
            refresh_tables.append(("bpp_autorzy_mat", "rekord_id"))

    with plpy.subtransaction():
        for table, id_col in refresh_tables:

          plpy.execute(f"LOCK {table} IN EXCLUSIVE MODE")

          query = "DELETE FROM " + table + " " + (where % id_col)
          plpy.execute(query)

          if TD["event"] in ["UPDATE", "INSERT"]:
              select_query = " SELECT * FROM " + table.replace("_mat", "") + "  " + (where % id_col)
              query = "INSERT INTO " + table + select_query
              plpy.execute(query)

$$;

COMMIT;
