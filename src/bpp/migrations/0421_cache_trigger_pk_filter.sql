-- Optymalizacja triggera cache (issue #311) + deterministyczny advisory lock (#309).
-- Dokleja object_id_raw (surowy PK) do 10 widokow per-typ i przepisuje
-- bpp_refresh_cache() tak, by filtrowac po surowym PK (Index seek) zamiast
-- po wyliczanej kolumnie-tablicy na unii (Seq Scan).
-- Widoki bazowe wygenerowane z pg_get_viewdef (stan po migracji 0420).
BEGIN;

-- ============ 1) Widoki per-typ + object_id_raw ============
CREATE OR REPLACE VIEW bpp_wydawnictwo_ciagle_view AS
 SELECT ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'wydawnictwo_ciagle'::text), bpp_wydawnictwo_ciagle.id] AS id,
    bpp_wydawnictwo_ciagle.tytul_oryginalny,
    bpp_wydawnictwo_ciagle.tytul,
    bpp_wydawnictwo_ciagle.search_index,
    bpp_wydawnictwo_ciagle.rok,
    bpp_wydawnictwo_ciagle.jezyk_id,
    bpp_wydawnictwo_ciagle.typ_kbn_id,
    bpp_wydawnictwo_ciagle.charakter_formalny_id,
    bpp_wydawnictwo_ciagle.zrodlo_id,
    NULL::integer AS wydawnictwo_nadrzedne_id,
    NULL::text AS wydawnictwo,
    bpp_wydawnictwo_ciagle.informacje,
    bpp_wydawnictwo_ciagle.szczegoly,
    bpp_wydawnictwo_ciagle.uwagi,
    bpp_wydawnictwo_ciagle.impact_factor,
    bpp_wydawnictwo_ciagle.punkty_kbn,
    bpp_wydawnictwo_ciagle.index_copernicus,
    bpp_wydawnictwo_ciagle.punktacja_wewnetrzna,
    bpp_wydawnictwo_ciagle.punktacja_snip,
    bpp_wydawnictwo_ciagle.kwartyl_w_wos,
    bpp_wydawnictwo_ciagle.kwartyl_w_scopus,
    bpp_wydawnictwo_ciagle.adnotacje,
    bpp_wydawnictwo_ciagle.utworzono,
    bpp_wydawnictwo_ciagle.ostatnio_zmieniony,
    bpp_wydawnictwo_ciagle.tytul_oryginalny_sort,
    bpp_wydawnictwo_ciagle.opis_bibliograficzny_cache,
    bpp_wydawnictwo_ciagle.opis_bibliograficzny_autorzy_cache,
    bpp_wydawnictwo_ciagle.opis_bibliograficzny_zapisani_autorzy_cache,
    bpp_wydawnictwo_ciagle.slug,
    bpp_wydawnictwo_ciagle.recenzowana,
    bpp_wydawnictwo_ciagle.liczba_znakow_wydawniczych,
    bpp_wydawnictwo_ciagle.www,
    bpp_wydawnictwo_ciagle.dostep_dnia,
    bpp_wydawnictwo_ciagle.public_www,
    bpp_wydawnictwo_ciagle.public_dostep_dnia,
    bpp_wydawnictwo_ciagle.openaccess_czas_publikacji_id,
    bpp_wydawnictwo_ciagle.openaccess_licencja_id,
    bpp_wydawnictwo_ciagle.openaccess_tryb_dostepu_id,
    bpp_wydawnictwo_ciagle.openaccess_wersja_tekstu_id,
    bpp_wydawnictwo_ciagle.openaccess_ilosc_miesiecy,
    bpp_wydawnictwo_ciagle.openaccess_data_opublikowania,
    bpp_wydawnictwo_ciagle.konferencja_id,
    count(bpp_wydawnictwo_ciagle_autor.autor_id) AS liczba_autorow,
    bpp_wydawnictwo_ciagle.liczba_cytowan,
    bpp_wydawnictwo_ciagle.status_korekty_id,
    lower(bpp_wydawnictwo_ciagle.doi::text) AS doi,
    bpp_wydawnictwo_ciagle.pbn_uid_id,
    NULL::text AS isbn,
    NULL::text AS e_isbn,
    bpp_wydawnictwo_ciagle.slowa_kluczowe_eng,
    NULL::integer AS wydawca_id
    , bpp_wydawnictwo_ciagle.id AS object_id_raw
   FROM bpp_wydawnictwo_ciagle
     LEFT JOIN bpp_wydawnictwo_ciagle_autor ON bpp_wydawnictwo_ciagle.id = bpp_wydawnictwo_ciagle_autor.rekord_id
  GROUP BY bpp_wydawnictwo_ciagle.id;
;

CREATE OR REPLACE VIEW bpp_wydawnictwo_zwarte_view AS
 SELECT ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'wydawnictwo_zwarte'::text), bpp_wydawnictwo_zwarte.id] AS id,
    bpp_wydawnictwo_zwarte.tytul_oryginalny,
    bpp_wydawnictwo_zwarte.tytul,
    bpp_wydawnictwo_zwarte.search_index,
    bpp_wydawnictwo_zwarte.rok,
    bpp_wydawnictwo_zwarte.jezyk_id,
    bpp_wydawnictwo_zwarte.typ_kbn_id,
    bpp_wydawnictwo_zwarte.charakter_formalny_id,
    NULL::integer AS zrodlo_id,
    bpp_wydawnictwo_zwarte.wydawnictwo_nadrzedne_id,
    bpp_wydawnictwo_zwarte.wydawca_opis AS wydawnictwo,
    bpp_wydawnictwo_zwarte.informacje,
    bpp_wydawnictwo_zwarte.szczegoly,
    bpp_wydawnictwo_zwarte.uwagi,
    bpp_wydawnictwo_zwarte.impact_factor,
    bpp_wydawnictwo_zwarte.punkty_kbn,
    bpp_wydawnictwo_zwarte.index_copernicus,
    bpp_wydawnictwo_zwarte.punktacja_wewnetrzna,
    bpp_wydawnictwo_zwarte.punktacja_snip,
    NULL::integer AS kwartyl_w_wos,
    NULL::integer AS kwartyl_w_scopus,
    bpp_wydawnictwo_zwarte.adnotacje,
    bpp_wydawnictwo_zwarte.utworzono,
    bpp_wydawnictwo_zwarte.ostatnio_zmieniony,
    bpp_wydawnictwo_zwarte.tytul_oryginalny_sort,
    bpp_wydawnictwo_zwarte.opis_bibliograficzny_cache,
    bpp_wydawnictwo_zwarte.opis_bibliograficzny_autorzy_cache,
    bpp_wydawnictwo_zwarte.opis_bibliograficzny_zapisani_autorzy_cache,
    bpp_wydawnictwo_zwarte.slug,
    bpp_wydawnictwo_zwarte.recenzowana,
    bpp_wydawnictwo_zwarte.liczba_znakow_wydawniczych,
    bpp_wydawnictwo_zwarte.www,
    bpp_wydawnictwo_zwarte.dostep_dnia,
    bpp_wydawnictwo_zwarte.public_www,
    bpp_wydawnictwo_zwarte.public_dostep_dnia,
    bpp_wydawnictwo_zwarte.openaccess_czas_publikacji_id,
    bpp_wydawnictwo_zwarte.openaccess_licencja_id,
    bpp_wydawnictwo_zwarte.openaccess_tryb_dostepu_id,
    bpp_wydawnictwo_zwarte.openaccess_wersja_tekstu_id,
    bpp_wydawnictwo_zwarte.openaccess_ilosc_miesiecy,
    bpp_wydawnictwo_zwarte.openaccess_data_opublikowania,
    bpp_wydawnictwo_zwarte.konferencja_id,
    count(bpp_wydawnictwo_zwarte_autor.autor_id) AS liczba_autorow,
    bpp_wydawnictwo_zwarte.liczba_cytowan,
    bpp_wydawnictwo_zwarte.status_korekty_id,
    lower(bpp_wydawnictwo_zwarte.doi::text) AS doi,
    bpp_wydawnictwo_zwarte.pbn_uid_id,
    TRIM(BOTH FROM replace(replace(replace(bpp_wydawnictwo_zwarte.isbn::text, '-'::text, ''::text), ' '::text, ''::text), '.'::text, ''::text)) AS isbn,
    TRIM(BOTH FROM replace(replace(replace(bpp_wydawnictwo_zwarte.e_isbn::text, '-'::text, ''::text), ' '::text, ''::text), '.'::text, ''::text)) AS e_isbn,
    bpp_wydawnictwo_zwarte.slowa_kluczowe_eng,
    bpp_wydawnictwo_zwarte.wydawca_id
    , bpp_wydawnictwo_zwarte.id AS object_id_raw
   FROM bpp_wydawnictwo_zwarte
     LEFT JOIN bpp_wydawnictwo_zwarte_autor ON bpp_wydawnictwo_zwarte.id = bpp_wydawnictwo_zwarte_autor.rekord_id
  GROUP BY bpp_wydawnictwo_zwarte.id;
;

CREATE OR REPLACE VIEW bpp_patent_view AS
 SELECT ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'patent'::text), bpp_patent.id] AS id,
    bpp_patent.tytul_oryginalny,
    NULL::text AS tytul,
    bpp_patent.search_index,
    bpp_patent.rok,
    ( SELECT bpp_jezyk.id
           FROM bpp_jezyk
          WHERE bpp_jezyk.skrot::text = 'pol.'::text) AS jezyk_id,
    ( SELECT bpp_typ_kbn.id
           FROM bpp_typ_kbn
          WHERE bpp_typ_kbn.skrot::text = 'PO'::text) AS typ_kbn_id,
    ( SELECT bpp_charakter_formalny.id
           FROM bpp_charakter_formalny
          WHERE bpp_charakter_formalny.skrot::text = 'PAT'::text) AS charakter_formalny_id,
    NULL::integer AS zrodlo_id,
    NULL::integer AS wydawnictwo_nadrzedne_id,
    NULL::text AS wydawnictwo,
    bpp_patent.informacje,
    bpp_patent.szczegoly,
    bpp_patent.uwagi,
    bpp_patent.impact_factor,
    bpp_patent.punkty_kbn,
    bpp_patent.index_copernicus,
    bpp_patent.punktacja_wewnetrzna,
    bpp_patent.punktacja_snip,
    NULL::integer AS kwartyl_w_wos,
    NULL::integer AS kwartyl_w_scopus,
    bpp_patent.adnotacje,
    bpp_patent.utworzono,
    bpp_patent.ostatnio_zmieniony,
    bpp_patent.tytul_oryginalny_sort,
    bpp_patent.opis_bibliograficzny_cache,
    bpp_patent.opis_bibliograficzny_autorzy_cache,
    bpp_patent.opis_bibliograficzny_zapisani_autorzy_cache,
    bpp_patent.slug,
    bpp_patent.recenzowana,
    0 AS liczba_znakow_wydawniczych,
    bpp_patent.www,
    bpp_patent.dostep_dnia,
    bpp_patent.public_www,
    bpp_patent.public_dostep_dnia,
    NULL::integer AS openaccess_czas_publikacji_id,
    NULL::integer AS openaccess_licencja_id,
    NULL::integer AS openaccess_tryb_dostepu_id,
    NULL::integer AS openaccess_wersja_tekstu_id,
    NULL::integer AS openaccess_ilosc_miesiecy,
    NULL::date AS openaccess_data_opublikowania,
    NULL::integer AS konferencja_id,
    count(bpp_patent_autor.autor_id) AS liczba_autorow,
    NULL::integer AS liczba_cytowan,
    bpp_patent.status_korekty_id,
    NULL::text AS doi,
    NULL::text AS pbn_uid_id,
    NULL::text AS isbn,
    NULL::text AS e_isbn,
    bpp_patent.slowa_kluczowe_eng,
    NULL::integer AS wydawca_id
    , bpp_patent.id AS object_id_raw
   FROM bpp_patent
     LEFT JOIN bpp_patent_autor ON bpp_patent.id = bpp_patent_autor.rekord_id
  GROUP BY bpp_patent.id;
;

CREATE OR REPLACE VIEW bpp_praca_doktorska_view AS
 SELECT ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'praca_doktorska'::text), id] AS id,
    tytul_oryginalny,
    tytul,
    search_index,
    rok,
    jezyk_id,
    typ_kbn_id,
    ( SELECT bpp_charakter_formalny.id
           FROM bpp_charakter_formalny
          WHERE bpp_charakter_formalny.skrot::text = 'D'::text) AS charakter_formalny_id,
    NULL::integer AS zrodlo_id,
    NULL::integer AS wydawnictwo_nadrzedne_id,
    wydawca_opis AS wydawnictwo,
    informacje,
    szczegoly,
    uwagi,
    impact_factor,
    punkty_kbn,
    index_copernicus,
    punktacja_wewnetrzna,
    punktacja_snip,
    NULL::integer AS kwartyl_w_wos,
    NULL::integer AS kwartyl_w_scopus,
    adnotacje,
    utworzono,
    ostatnio_zmieniony,
    tytul_oryginalny_sort,
    opis_bibliograficzny_cache,
    opis_bibliograficzny_autorzy_cache,
    opis_bibliograficzny_zapisani_autorzy_cache,
    slug,
    recenzowana,
    0 AS liczba_znakow_wydawniczych,
    www,
    dostep_dnia,
    public_www,
    public_dostep_dnia,
    NULL::integer AS openaccess_czas_publikacji_id,
    NULL::integer AS openaccess_licencja_id,
    NULL::integer AS openaccess_tryb_dostepu_id,
    NULL::integer AS openaccess_wersja_tekstu_id,
    NULL::integer AS openaccess_ilosc_miesiecy,
    NULL::date AS openaccess_data_opublikowania,
    NULL::integer AS konferencja_id,
    1 AS liczba_autorow,
    liczba_cytowan,
    status_korekty_id,
    lower(doi::text) AS doi,
    pbn_uid_id,
    replace(replace(replace(isbn::text, '-'::text, ''::text), ' '::text, ''::text), '.'::text, ''::text) AS isbn,
    replace(replace(replace(e_isbn::text, '-'::text, ''::text), ' '::text, ''::text), '.'::text, ''::text) AS e_isbn,
    slowa_kluczowe_eng,
    NULL::integer AS wydawca_id
    , bpp_praca_doktorska.id AS object_id_raw
   FROM bpp_praca_doktorska;
;

CREATE OR REPLACE VIEW bpp_praca_habilitacyjna_view AS
 SELECT ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'praca_habilitacyjna'::text), id] AS id,
    tytul_oryginalny,
    tytul,
    search_index,
    rok,
    jezyk_id,
    typ_kbn_id,
    ( SELECT bpp_charakter_formalny.id
           FROM bpp_charakter_formalny
          WHERE bpp_charakter_formalny.skrot::text = 'H'::text) AS charakter_formalny_id,
    NULL::integer AS zrodlo_id,
    NULL::integer AS wydawnictwo_nadrzedne_id,
    wydawca_opis AS wydawnictwo,
    informacje,
    szczegoly,
    uwagi,
    impact_factor,
    punkty_kbn,
    index_copernicus,
    punktacja_wewnetrzna,
    punktacja_snip,
    NULL::integer AS kwartyl_w_wos,
    NULL::integer AS kwartyl_w_scopus,
    adnotacje,
    utworzono,
    ostatnio_zmieniony,
    tytul_oryginalny_sort,
    opis_bibliograficzny_cache,
    opis_bibliograficzny_autorzy_cache,
    opis_bibliograficzny_zapisani_autorzy_cache,
    slug,
    recenzowana,
    0 AS liczba_znakow_wydawniczych,
    www,
    dostep_dnia,
    public_www,
    public_dostep_dnia,
    NULL::integer AS openaccess_czas_publikacji_id,
    NULL::integer AS openaccess_licencja_id,
    NULL::integer AS openaccess_tryb_dostepu_id,
    NULL::integer AS openaccess_wersja_tekstu_id,
    NULL::integer AS openaccess_ilosc_miesiecy,
    NULL::date AS openaccess_data_opublikowania,
    NULL::integer AS konferencja_id,
    1 AS liczba_autorow,
    liczba_cytowan,
    status_korekty_id,
    lower(doi::text) AS doi,
    pbn_uid_id,
    replace(replace(replace(isbn::text, '-'::text, ''::text), ' '::text, ''::text), '.'::text, ''::text) AS isbn,
    replace(replace(replace(e_isbn::text, '-'::text, ''::text), ' '::text, ''::text), '.'::text, ''::text) AS e_isbn,
    slowa_kluczowe_eng,
    NULL::integer AS wydawca_id
    , bpp_praca_habilitacyjna.id AS object_id_raw
   FROM bpp_praca_habilitacyjna;
;

CREATE OR REPLACE VIEW bpp_wydawnictwo_ciagle_autorzy AS
 SELECT ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'wydawnictwo_ciagle'::text), rekord_id] AS rekord_id,
    ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'wydawnictwo_ciagle'::text), id] AS id,
    autor_id,
    jednostka_id,
    kolejnosc,
    typ_odpowiedzialnosci_id,
    zapisany_jako,
    zatrudniony,
    afiliuje,
    dyscyplina_naukowa_id,
    upowaznienie_pbn,
    profil_orcid,
    kierunek_studiow_id,
    oswiadczenie_ken,
    przypieta,
    data_oswiadczenia
    , bpp_wydawnictwo_ciagle_autor.rekord_id AS object_id_raw
   FROM bpp_wydawnictwo_ciagle_autor;
;

CREATE OR REPLACE VIEW bpp_wydawnictwo_zwarte_autorzy AS
 SELECT ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'wydawnictwo_zwarte'::text), rekord_id] AS rekord_id,
    ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'wydawnictwo_zwarte'::text), id] AS id,
    autor_id,
    jednostka_id,
    kolejnosc,
    typ_odpowiedzialnosci_id,
    zapisany_jako,
    zatrudniony,
    afiliuje,
    dyscyplina_naukowa_id,
    upowaznienie_pbn,
    profil_orcid,
    kierunek_studiow_id,
    oswiadczenie_ken,
    przypieta,
    data_oswiadczenia
    , bpp_wydawnictwo_zwarte_autor.rekord_id AS object_id_raw
   FROM bpp_wydawnictwo_zwarte_autor;
;

CREATE OR REPLACE VIEW bpp_patent_autorzy AS
 SELECT ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'patent'::text), rekord_id] AS rekord_id,
    ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'patent'::text), id] AS id,
    autor_id,
    jednostka_id,
    kolejnosc,
    typ_odpowiedzialnosci_id,
    zapisany_jako,
    zatrudniony,
    afiliuje,
    dyscyplina_naukowa_id,
    upowaznienie_pbn,
    profil_orcid,
    NULL::integer AS kierunek_studiow_id,
    NULL::boolean AS oswiadczenie_ken,
    przypieta,
    data_oswiadczenia
    , bpp_patent_autor.rekord_id AS object_id_raw
   FROM bpp_patent_autor;
;

CREATE OR REPLACE VIEW bpp_praca_doktorska_autorzy AS
 SELECT ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'praca_doktorska'::text), bpp_praca_doktorska.id] AS rekord_id,
    ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'praca_doktorska'::text), bpp_praca_doktorska.id] AS "array",
    bpp_praca_doktorska.autor_id,
    bpp_praca_doktorska.jednostka_id,
    1 AS kolejnosc,
    ( SELECT bpp_typ_odpowiedzialnosci.id
           FROM bpp_typ_odpowiedzialnosci
          WHERE bpp_typ_odpowiedzialnosci.skrot::text = 'aut.'::text) AS typ_odpowiedzialnosci_id,
    (bpp_autor.nazwisko::text || ' '::text) || bpp_autor.imiona::text AS zapisany_jako,
    true AS zatrudniony,
    true AS afiliuje,
    NULL::integer AS dyscyplina_naukowa_id,
    false AS upowaznienie_pbn,
    false AS profil_orcid,
    NULL::integer AS kierunek_studiow_id,
    NULL::boolean AS oswiadczenie_ken,
    true AS przypieta,
    NULL::date AS data_oswiadczenia
    , bpp_praca_doktorska.id AS object_id_raw
   FROM bpp_praca_doktorska,
    bpp_autor
  WHERE bpp_autor.id = bpp_praca_doktorska.autor_id;
;

CREATE OR REPLACE VIEW bpp_praca_habilitacyjna_autorzy AS
 SELECT ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'praca_habilitacyjna'::text), bpp_praca_habilitacyjna.id] AS rekord_id,
    ARRAY[( SELECT django_content_type.id
           FROM django_content_type
          WHERE django_content_type.app_label::text = 'bpp'::text AND django_content_type.model::text = 'praca_habilitacyjna'::text), bpp_praca_habilitacyjna.id] AS id,
    bpp_praca_habilitacyjna.autor_id,
    bpp_praca_habilitacyjna.jednostka_id,
    1 AS kolejnosc,
    ( SELECT bpp_typ_odpowiedzialnosci.id
           FROM bpp_typ_odpowiedzialnosci
          WHERE bpp_typ_odpowiedzialnosci.skrot::text = 'aut.'::text) AS typ_odpowiedzialnosci_id,
    (bpp_autor.nazwisko::text || ' '::text) || bpp_autor.imiona::text AS zapisany_jako,
    true AS zatrudniony,
    true AS afiliuje,
    NULL::integer AS dyscyplina_naukowa_id,
    false AS upowaznienie_pbn,
    false AS profil_orcid,
    NULL::integer AS kierunek_studiow_id,
    NULL::boolean AS oswiadczenie_ken,
    true AS przypieta,
    NULL::date AS data_oswiadczenia
    , bpp_praca_habilitacyjna.id AS object_id_raw
   FROM bpp_praca_habilitacyjna,
    bpp_autor
  WHERE bpp_autor.id = bpp_praca_habilitacyjna.autor_id;
;

-- ============ 2) Funkcja triggera ============
CREATE OR REPLACE FUNCTION bpp_refresh_cache()
  RETURNS TRIGGER
  LANGUAGE plpython3u
  AS $$
    # Odswieza bpp_rekord_mat / bpp_autorzy_mat dla POJEDYNCZEGO rekordu.
    #
    # Optymalizacja (issue #311): zamiast SELECT-owac ze zlozonej unii
    # bpp_rekord / bpp_autorzy filtrujac po WYLICZANEJ kolumnie-tablicy
    # (id = ARRAY[ct, obj]) — co dawalo Seq Scan wszystkich 5 tabel bazowych —
    # rutujemy SELECT do konkretnego widoku per-typ (wg TD["table_name"]) i
    # filtrujemy po surowej, indeksowanej kolumnie object_id_raw (= PK tabeli
    # bazowej). To daje Index Cond seek zamiast skanu.
    #
    # Operacje po stronie mat-tabel (DELETE / ON CONFLICT (id)) dzialaja dalej
    # na indeksowanej kolumnie-tablicy `id` — bez zmian.

    table_name = TD["table_name"]
    event = TD["event"]
    field = "old" if event in ("DELETE", "UPDATE") else "new"

    # Routing: tabela triggera -> (bazowa tabela publikacji, czy to through-table autorow)
    ROUTING = {
        "bpp_wydawnictwo_ciagle":       ("bpp_wydawnictwo_ciagle", False),
        "bpp_wydawnictwo_ciagle_autor": ("bpp_wydawnictwo_ciagle", True),
        "bpp_wydawnictwo_zwarte":       ("bpp_wydawnictwo_zwarte", False),
        "bpp_wydawnictwo_zwarte_autor": ("bpp_wydawnictwo_zwarte", True),
        "bpp_patent":                   ("bpp_patent", False),
        "bpp_patent_autor":             ("bpp_patent", True),
        "bpp_praca_doktorska":          ("bpp_praca_doktorska", False),
        "bpp_praca_habilitacyjna":      ("bpp_praca_habilitacyjna", False),
    }
    pub_base, is_through = ROUTING[table_name]
    app_name, model_name = pub_base.split("_", 1)

    # object_id = PK publikacji (dla through-table jest w rekord_id, inaczej w id)
    object_id = TD[field]["rekord_id"] if is_through else TD[field]["id"]

    # cache content_type_id oraz listy kolumn w GD (per-backend, na czas polaczenia)
    cache_key = "django_content_type_ver_2"
    columns_cache_key = "table_columns_ver_2"
    if GD.get(cache_key) is None:
        GD[cache_key] = {}
    if GD.get(columns_cache_key) is None:
        GD[columns_cache_key] = {}

    if pub_base not in GD[cache_key]:
        res = plpy.execute(
            "SELECT id FROM django_content_type "
            "WHERE app_label = '%s' AND model = '%s'" % (app_name, model_name))
        GD[cache_key][pub_base] = res[0]["id"]
    content_type_id = GD[cache_key][pub_base]

    # Co odswiezamy: publikacja -> rekord + wszyscy autorzy; through -> tylko ten autor.
    refresh_rekord = not is_through
    refresh_autor = True

    rekord_view = pub_base + "_view"
    autorzy_view = pub_base + "_autorzy"

    # Przy edycji wiersza *_autor odswiez tylko tego jednego autora.
    autor_extra = ""
    if is_through:
        autor_extra = " AND autor_id = %s" % TD[field]["autor_id"]

    mat_arr = "ARRAY[%s, %s]::INTEGER[2]" % (content_type_id, object_id)

    def get_table_columns(mat_table):
        if mat_table not in GD[columns_cache_key]:
            res = plpy.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = '%s' "
                "ORDER BY ordinal_position" % mat_table)
            GD[columns_cache_key][mat_table] = [r["column_name"] for r in res]
        return GD[columns_cache_key][mat_table]

    def upsert(mat_table, mat_where, source_view, source_where):
        # DELETE starych (obsluga przypadku, gdy rekord wypadl ze zrodla),
        # potem INSERT ... SELECT ... ON CONFLICT (id) DO UPDATE (obsluga wyscigu).
        plpy.execute("DELETE FROM " + mat_table + " WHERE " + mat_where)
        if event == "DELETE":
            return
        # INSERT po nazwach kolumn tabeli mat, SELECT po nazwach kolumn widoku.
        # Odpowiadaja sobie POZYCYJNIE: widok to zrodlo tabeli mat + dorzucone
        # na koncu object_id_raw. Mapowanie pozycyjne (a nie po nazwie) jest
        # odporne na to, ze pojedynczy widok moze nazwac kolumne-tablice inaczej
        # niz tabela mat — np. bpp_praca_doktorska_autorzy ma 'array' zamiast
        # 'id' (nieaaliasowane ARRAY[...]); unia normalizowala nazwe z pierwszej
        # galezi, ale pojedynczy widok juz nie.
        # Cytujemy identyfikatory ("...") — niektore kolumny widokow nazywaja
        # sie jak slowa zarezerwowane (np. 'array' w bpp_praca_doktorska_autorzy,
        # nieaaliasowane ARRAY[...]) i bez cudzyslowow daja blad skladni.
        def q(c):
            return '"' + c + '"'

        mat_cols = get_table_columns(mat_table)
        src_cols = [c for c in get_table_columns(source_view) if c != "object_id_raw"]
        set_clause = ", ".join(
            "%s = EXCLUDED.%s" % (q(c), q(c)) for c in mat_cols if c != "id")
        plpy.execute(
            "INSERT INTO " + mat_table +
            " (" + ", ".join(q(c) for c in mat_cols) + ") "
            "SELECT " + ", ".join(q(c) for c in src_cols) + " FROM " + source_view +
            " WHERE " + source_where +
            " ON CONFLICT (id) DO UPDATE SET " + set_clause)

    # Deterministyczny advisory lock (domyka #309): para int4 (ct, obj),
    # zamiast hash(f"...") ktory byl losowy per-backend (PYTHONHASHSEED).
    plpy.execute("SELECT pg_advisory_xact_lock(%s, %s)" % (content_type_id, object_id))

    with plpy.subtransaction():
        if refresh_rekord:
            # DELETE bpp_rekord_mat kaskaduje (FK) na bpp_autorzy_mat — dlatego
            # ponizej i tak odswiezamy autorow.
            upsert(
                "bpp_rekord_mat",
                "id = " + mat_arr,
                rekord_view,
                "object_id_raw = %s" % object_id)
        if refresh_autor:
            upsert(
                "bpp_autorzy_mat",
                "rekord_id = " + mat_arr + autor_extra,
                autorzy_view,
                ("object_id_raw = %s" % object_id) + autor_extra)
$$;

COMMIT;
