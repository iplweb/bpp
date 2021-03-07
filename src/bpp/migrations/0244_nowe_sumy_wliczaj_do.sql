BEGIN;

DROP VIEW IF EXISTS bpp_nowe_sumy_view CASCADE;
DROP VIEW IF EXISTS bpp_nowe_sumy_all_view CASCADE;
DROP VIEW IF EXISTS bpp_nowe_sumy_patent_view CASCADE;
DROP VIEW IF EXISTS bpp_nowe_sumy_praca_doktorska_view CASCADE;
DROP VIEW IF EXISTS bpp_nowe_sumy_praca_habilitacyjna_view CASCADE;
DROP VIEW IF EXISTS bpp_nowe_sumy_wydawnictwo_ciagle_view CASCADE;
DROP VIEW IF EXISTS bpp_nowe_sumy_wydawnictwo_zwarte_view CASCADE;

CREATE OR REPLACE VIEW bpp_nowe_sumy_patent_view AS

SELECT bpp_autor.id         AS autor_id,
       bpp_jednostka.id     AS jednostka_id,

       rok                  AS rok,
       punktacja_wewnetrzna AS punktacja_wewnetrzna,
       index_copernicus     AS index_copernicus,
       impact_factor        AS impact_factor,
       '0' :: INTEGER       AS liczba_cytowan,
       punkty_kbn           AS punkty_kbn,
       kc_impact_factor     AS kc_impact_factor,
       kc_punkty_kbn        AS kc_punkty_kbn,
       kc_index_copernicus  AS kc_index_copernicus,

       -- Kompatybilność z klasą ModelPunktowany:
       TRUE                 AS weryfikacja_punktacji,

       afiliuje             AS afiliuje,

       status_korekty_id

FROM bpp_autor,
     bpp_patent,
     bpp_jednostka,
     bpp_patent_autor

WHERE bpp_autor.id = bpp_patent_autor.autor_id
  AND bpp_patent.id = bpp_patent_autor.rekord_id
  AND bpp_jednostka.id = bpp_patent_autor.jednostka_id
  AND bpp_jednostka.wchodzi_do_raportow = TRUE;


CREATE OR REPLACE VIEW bpp_nowe_sumy_praca_doktorska_view AS

SELECT bpp_autor.id         AS autor_id,
       bpp_jednostka.id     AS jednostka_id,

       rok                  AS rok,
       punktacja_wewnetrzna AS punktacja_wewnetrzna,
       index_copernicus     AS index_copernicus,
       impact_factor        AS impact_factor,
       liczba_cytowan       AS liczba_cytowan,
       punkty_kbn           AS punkty_kbn,
       kc_impact_factor     AS kc_impact_factor,
       kc_punkty_kbn        AS kc_punkty_kbn,
       kc_index_copernicus  AS kc_index_copernicus,

       -- Kompatybilność z klasą ModelPunktowany:
       TRUE                 AS weryfikacja_punktacji,

       TRUE                 AS afiliuje,

       status_korekty_id

FROM bpp_autor,
     bpp_praca_doktorska,
     bpp_jednostka,
     bpp_typ_kbn

WHERE bpp_autor.id = bpp_praca_doktorska.autor_id
  AND bpp_jednostka.id = bpp_praca_doktorska.jednostka_id
  AND bpp_jednostka.wchodzi_do_raportow = TRUE
  AND bpp_typ_kbn.id = bpp_praca_doktorska.typ_kbn_id
  AND bpp_typ_kbn.skrot != 'PW';


CREATE OR REPLACE VIEW bpp_nowe_sumy_praca_habilitacyjna_view AS

SELECT bpp_autor.id         AS autor_id,
       bpp_jednostka.id     AS jednostka_id,

       rok                  AS rok,
       punktacja_wewnetrzna AS punktacja_wewnetrzna,
       index_copernicus     AS index_copernicus,
       impact_factor        AS impact_factor,
       liczba_cytowan       AS liczba_cytowan,
       punkty_kbn           AS punkty_kbn,
       kc_impact_factor     AS kc_impact_factor,
       kc_punkty_kbn        AS kc_punkty_kbn,
       kc_index_copernicus  AS kc_index_copernicus,

       -- Kompatybilność z klasą ModelPunktowany:
       TRUE                 AS weryfikacja_punktacji,

       TRUE                 AS afiliuje,

       status_korekty_id

FROM bpp_autor,
     bpp_praca_habilitacyjna,
     bpp_jednostka,
     bpp_typ_kbn

WHERE bpp_autor.id = bpp_praca_habilitacyjna.autor_id
  AND bpp_jednostka.id = bpp_praca_habilitacyjna.jednostka_id
  AND bpp_jednostka.wchodzi_do_raportow = TRUE
  AND bpp_typ_kbn.id = bpp_praca_habilitacyjna.typ_kbn_id
  AND bpp_typ_kbn.skrot != 'PW';


CREATE OR REPLACE VIEW bpp_nowe_sumy_wydawnictwo_ciagle_view AS

SELECT bpp_autor.id         AS autor_id,
       bpp_jednostka.id     AS jednostka_id,

       rok                  AS rok,
       punktacja_wewnetrzna AS punktacja_wewnetrzna,
       index_copernicus     AS index_copernicus,
       impact_factor        AS impact_factor,
       liczba_cytowan       AS liczba_cytowan,
       punkty_kbn           AS punkty_kbn,
       kc_impact_factor     AS kc_impact_factor,
       kc_punkty_kbn        AS kc_punkty_kbn,
       kc_index_copernicus  AS kc_index_copernicus,

       -- Kompatybilność z klasą ModelPunktowany:
       TRUE                 AS weryfikacja_punktacji,

       afiliuje             AS afiliuje,

       status_korekty_id

FROM bpp_autor,
     bpp_wydawnictwo_ciagle,
     bpp_wydawnictwo_ciagle_autor,
     bpp_jednostka,
     bpp_typ_kbn,
     bpp_charakter_formalny

WHERE bpp_autor.id = bpp_wydawnictwo_ciagle_autor.autor_id
  AND bpp_wydawnictwo_ciagle.id = bpp_wydawnictwo_ciagle_autor.rekord_id
  AND bpp_jednostka.id = bpp_wydawnictwo_ciagle_autor.jednostka_id
  AND bpp_jednostka.wchodzi_do_raportow = TRUE
  AND bpp_typ_kbn.id = bpp_wydawnictwo_ciagle.typ_kbn_id
  AND bpp_charakter_formalny.id = bpp_wydawnictwo_ciagle.charakter_formalny_id
  AND bpp_typ_kbn.wliczaj_do_rankingu = TRUE
  AND bpp_charakter_formalny.wliczaj_do_rankingu = TRUE;


CREATE OR REPLACE VIEW bpp_nowe_sumy_wydawnictwo_zwarte_view AS

SELECT bpp_autor.id         AS autor_id,
       bpp_jednostka.id     AS jednostka_id,

       rok                  AS rok,
       punktacja_wewnetrzna AS punktacja_wewnetrzna,
       index_copernicus     AS index_copernicus,
       impact_factor        AS impact_factor,
       liczba_cytowan       AS liczba_cytowan,
       punkty_kbn           AS punkty_kbn,
       kc_impact_factor     AS kc_impact_factor,
       kc_punkty_kbn        AS kc_punkty_kbn,
       kc_index_copernicus  AS kc_index_copernicus,

       -- Kompatybilność z klasą ModelPunktowany:
       TRUE                 AS weryfikacja_punktacji,

       afiliuje             AS afiliuje,

       status_korekty_id

FROM bpp_autor,
     bpp_wydawnictwo_zwarte,
     bpp_wydawnictwo_zwarte_autor,
     bpp_jednostka,
     bpp_typ_kbn,
     bpp_charakter_formalny

WHERE bpp_autor.id = bpp_wydawnictwo_zwarte_autor.autor_id
  AND bpp_wydawnictwo_zwarte.id = bpp_wydawnictwo_zwarte_autor.rekord_id
  AND bpp_jednostka.id = bpp_wydawnictwo_zwarte_autor.jednostka_id
  AND bpp_jednostka.wchodzi_do_raportow = TRUE
  AND bpp_typ_kbn.id = bpp_wydawnictwo_zwarte.typ_kbn_id
  AND bpp_charakter_formalny.id = bpp_wydawnictwo_zwarte.charakter_formalny_id
  AND bpp_typ_kbn.wliczaj_do_rankingu = TRUE
  AND bpp_charakter_formalny.wliczaj_do_rankingu = TRUE;


CREATE OR REPLACE VIEW bpp_nowe_sumy_view AS
SELECT *
FROM bpp_nowe_sumy_patent_view
UNION ALL
SELECT *
FROM bpp_nowe_sumy_praca_habilitacyjna_view
UNION ALL
SELECT *
FROM bpp_nowe_sumy_praca_doktorska_view
UNION ALL
SELECT *
FROM bpp_nowe_sumy_wydawnictwo_ciagle_view
UNION ALL
SELECT *
FROM bpp_nowe_sumy_wydawnictwo_zwarte_view;

COMMIT;
