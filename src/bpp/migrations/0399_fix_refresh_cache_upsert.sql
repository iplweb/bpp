BEGIN;

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
    columns_cache_key = "table_columns_ver_1"
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

    if GD.get(columns_cache_key) is None:
        GD[columns_cache_key] = {}

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

    def get_table_columns(mat_table):
        """Pobiera listę kolumn dla tabeli w sposób dynamiczny z cache."""
        if mat_table not in GD[columns_cache_key]:
            query = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = '%s'
                ORDER BY ordinal_position
            """ % mat_table
            res = plpy.execute(query)
            GD[columns_cache_key][mat_table] = [row['column_name'] for row in res]
        return GD[columns_cache_key][mat_table]

    def get_unique_constraint_column(mat_table):
        """Zwraca kolumnę dla ON CONFLICT w zależności od tabeli."""
        # Obie tabele mają unikalny indeks na kolumnie 'id'
        return "id"

    with plpy.subtransaction():
        for table, id_col in refresh_tables:
          # Użyj advisory lock dla konkretnych rekordów zamiast blokady całej tabeli
          lock_key = hash(f"{table}_{content_type_id}_{object_id}") % (2**31)
          plpy.execute(f"SELECT pg_advisory_xact_lock({lock_key})")

          if TD["event"] == "DELETE":
              # Dla DELETE - po prostu usuwamy rekordy
              query = "DELETE FROM " + table + " " + (where % id_col)
              plpy.execute(query)
          elif TD["event"] in ["UPDATE", "INSERT"]:
              # Dla UPDATE/INSERT używamy upsert z dynamiczną listą kolumn
              source_view = table.replace("_mat", "")
              columns = get_table_columns(table)
              conflict_col = get_unique_constraint_column(table)

              # Buduj listę kolumn do SELECT i UPDATE
              columns_str = ", ".join(columns)

              # Buduj klauzulę SET dla ON CONFLICT DO UPDATE
              # Pomijamy kolumnę konfliktową (id) w SET
              update_columns = [col for col in columns if col != conflict_col]
              set_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])

              # Najpierw usuwamy stare rekordy których już nie ma w źródle
              # (obsługa przypadku gdy rekord zmienia swoje powiązania)
              delete_query = "DELETE FROM " + table + " " + (where % id_col)
              plpy.execute(delete_query)

              # Następnie wstawiamy/aktualizujemy za pomocą upsert
              # ON CONFLICT DO UPDATE obsługuje przypadek gdy rekord już istnieje
              # (np. z powodu race condition między triggerami)
              select_query = f"SELECT {columns_str} FROM {source_view} " + (where % id_col)
              upsert_query = f"""
                  INSERT INTO {table} ({columns_str})
                  {select_query}
                  ON CONFLICT ({conflict_col}) DO UPDATE SET {set_clause}
              """
              plpy.execute(upsert_query)

$$;

COMMIT;
