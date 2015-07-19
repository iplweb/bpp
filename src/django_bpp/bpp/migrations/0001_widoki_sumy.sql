CREATE OR REPLACE VIEW bpp_sumy_patent_view AS

  SELECT
    bpp_autor.id                         AS autor_id,
    bpp_jednostka.id                     AS jednostka_id,
    bpp_wydzial.id                       AS wydzial_id,
    bpp_patent.rok                       AS rok,
    SUM(bpp_patent.punktacja_wewnetrzna) AS punktacja_wewnetrzna,
    SUM(bpp_patent.index_copernicus)     AS index_copernicus,
    SUM(bpp_patent.impact_factor)        AS impact_factor,
    SUM(bpp_patent.punkty_kbn)           AS punkty_kbn,

    SUM(bpp_patent.kc_impact_factor)     AS kc_impact_factor,
    SUM(bpp_patent.kc_punkty_kbn)        AS kc_punkty_kbn,
    SUM(bpp_patent.kc_index_copernicus)  AS kc_index_copernicus,

-- Kompatybilność z klasą ModelPunktowany:
    TRUE                                 AS weryfikacja_punktacji

  FROM
    bpp_autor,
    bpp_patent,
    bpp_jednostka,
    bpp_patent_autor,
    bpp_wydzial

  WHERE
    bpp_autor.id = bpp_patent_autor.autor_id AND
    bpp_patent.id = bpp_patent_autor.rekord_id AND
    bpp_jednostka.id = bpp_patent_autor.jednostka_id AND
    bpp_wydzial.id = bpp_jednostka.wydzial_id AND
    bpp_jednostka.wchodzi_do_raportow = TRUE

  GROUP BY
    bpp_autor.id, bpp_jednostka.id, bpp_wydzial.id, bpp_patent.rok;




CREATE OR REPLACE VIEW bpp_sumy_praca_doktorska_view AS

  SELECT
    bpp_autor.id                                  AS autor_id,
    bpp_jednostka.id                              AS jednostka_id,
    bpp_wydzial.id                                AS wydzial_id,
    bpp_praca_doktorska.rok                       AS rok,
    SUM(bpp_praca_doktorska.punktacja_wewnetrzna) AS punktacja_wewnetrzna,
    SUM(bpp_praca_doktorska.index_copernicus)     AS index_copernicus,
    SUM(bpp_praca_doktorska.impact_factor)        AS impact_factor,
    SUM(bpp_praca_doktorska.punkty_kbn)           AS punkty_kbn,

    SUM(bpp_praca_doktorska.kc_impact_factor)     AS kc_impact_factor,
    SUM(bpp_praca_doktorska.kc_punkty_kbn)        AS kc_punkty_kbn,
    SUM(bpp_praca_doktorska.kc_index_copernicus)  AS kc_index_copernicus,

-- Kompatybilność z klasą ModelPunktowany:
    TRUE                                          AS weryfikacja_punktacji

  FROM
    bpp_autor,
    bpp_praca_doktorska,
    bpp_jednostka,
    bpp_wydzial,
    bpp_typ_kbn

  WHERE
    bpp_autor.id = bpp_praca_doktorska.autor_id AND
    bpp_jednostka.id = bpp_praca_doktorska.jednostka_id AND
    bpp_wydzial.id = bpp_jednostka.wydzial_id AND
    bpp_jednostka.wchodzi_do_raportow = TRUE AND
    bpp_typ_kbn.id = bpp_praca_doktorska.typ_kbn_id AND
    bpp_typ_kbn.skrot != 'PW'

  GROUP BY
    bpp_autor.id, bpp_jednostka.id, bpp_wydzial.id, bpp_praca_doktorska.rok;





CREATE OR REPLACE VIEW bpp_sumy_praca_habilitacyjna_view AS

  SELECT
    bpp_autor.id                                      AS autor_id,
    bpp_jednostka.id                                  AS jednostka_id,
    bpp_wydzial.id                                    AS wydzial_id,
    bpp_praca_habilitacyjna.rok                       AS rok,
    SUM(bpp_praca_habilitacyjna.punktacja_wewnetrzna) AS punktacja_wewnetrzna,
    SUM(bpp_praca_habilitacyjna.index_copernicus)     AS index_copernicus,
    SUM(bpp_praca_habilitacyjna.impact_factor)        AS impact_factor,
    SUM(bpp_praca_habilitacyjna.punkty_kbn)           AS punkty_kbn,

    SUM(bpp_praca_habilitacyjna.kc_impact_factor)     AS kc_impact_factor,
    SUM(bpp_praca_habilitacyjna.kc_punkty_kbn)        AS kc_punkty_kbn,
    SUM(bpp_praca_habilitacyjna.kc_index_copernicus)  AS kc_index_copernicus,

-- Kompatybilność z klasą ModelPunktowany:
    TRUE                                              AS weryfikacja_punktacji

  FROM
    bpp_autor,
    bpp_praca_habilitacyjna,
    bpp_jednostka,
    bpp_wydzial,
    bpp_typ_kbn

  WHERE
    bpp_autor.id = bpp_praca_habilitacyjna.autor_id AND
    bpp_jednostka.id = bpp_praca_habilitacyjna.jednostka_id AND
    bpp_wydzial.id = bpp_jednostka.wydzial_id AND
    bpp_jednostka.wchodzi_do_raportow = TRUE AND
    bpp_typ_kbn.id = bpp_praca_habilitacyjna.typ_kbn_id AND
    bpp_typ_kbn.skrot != 'PW'

  GROUP BY
    bpp_autor.id, bpp_jednostka.id, bpp_wydzial.id, bpp_praca_habilitacyjna.rok;





CREATE OR REPLACE VIEW bpp_sumy_wydawnictwo_ciagle_view AS

  SELECT
    bpp_autor.id                                     AS autor_id,
    bpp_jednostka.id                                 AS jednostka_id,
    bpp_wydzial.id                                   AS wydzial_id,
    bpp_wydawnictwo_ciagle.rok                       AS rok,
    SUM(bpp_wydawnictwo_ciagle.punktacja_wewnetrzna) AS punktacja_wewnetrzna,
    SUM(bpp_wydawnictwo_ciagle.index_copernicus)     AS index_copernicus,
    SUM(bpp_wydawnictwo_ciagle.impact_factor)        AS impact_factor,
    SUM(bpp_wydawnictwo_ciagle.punkty_kbn)           AS punkty_kbn,

    SUM(bpp_wydawnictwo_ciagle.kc_impact_factor)     AS kc_impact_factor,
    SUM(bpp_wydawnictwo_ciagle.kc_punkty_kbn)        AS kc_punkty_kbn,
    SUM(bpp_wydawnictwo_ciagle.kc_index_copernicus)  AS kc_index_copernicus,

-- Kompatybilność z klasą ModelPunktowany:
    TRUE                                             AS weryfikacja_punktacji

  FROM
    bpp_autor,
    bpp_wydawnictwo_ciagle,
    bpp_wydawnictwo_ciagle_autor,
    bpp_jednostka,
    bpp_wydzial,
    bpp_typ_kbn

  WHERE
    bpp_autor.id = bpp_wydawnictwo_ciagle_autor.autor_id AND
    bpp_wydawnictwo_ciagle.id = bpp_wydawnictwo_ciagle_autor.rekord_id AND
    bpp_jednostka.id = bpp_wydawnictwo_ciagle_autor.jednostka_id AND
    bpp_wydzial.id = bpp_jednostka.wydzial_id AND
    bpp_jednostka.wchodzi_do_raportow = TRUE AND
    bpp_typ_kbn.id = bpp_wydawnictwo_ciagle.typ_kbn_id AND
    bpp_typ_kbn.skrot != 'PW'


  GROUP BY
    bpp_autor.id, bpp_jednostka.id, bpp_wydzial.id, bpp_wydawnictwo_ciagle.rok;




CREATE OR REPLACE VIEW bpp_sumy_wydawnictwo_zwarte_view AS

  SELECT
    bpp_autor.id                                     AS autor_id,
    bpp_jednostka.id                                 AS jednostka_id,
    bpp_wydzial.id                                   AS wydzial_id,
    bpp_wydawnictwo_zwarte.rok                       AS rok,
    SUM(bpp_wydawnictwo_zwarte.punktacja_wewnetrzna) AS punktacja_wewnetrzna,
    SUM(bpp_wydawnictwo_zwarte.index_copernicus)     AS index_copernicus,
    SUM(bpp_wydawnictwo_zwarte.impact_factor)        AS impact_factor,
    SUM(bpp_wydawnictwo_zwarte.punkty_kbn)           AS punkty_kbn,

    SUM(bpp_wydawnictwo_zwarte.kc_impact_factor)     AS kc_impact_factor,
    SUM(bpp_wydawnictwo_zwarte.kc_punkty_kbn)        AS kc_punkty_kbn,
    SUM(bpp_wydawnictwo_zwarte.kc_index_copernicus)  AS kc_index_copernicus,

-- Kompatybilność z klasą ModelPunktowany:
    TRUE                                             AS weryfikacja_punktacji

  FROM
    bpp_autor,
    bpp_wydawnictwo_zwarte,
    bpp_wydawnictwo_zwarte_autor,
    bpp_jednostka,
    bpp_wydzial,
    bpp_typ_kbn

  WHERE
    bpp_autor.id = bpp_wydawnictwo_zwarte_autor.autor_id AND
    bpp_wydawnictwo_zwarte.id = bpp_wydawnictwo_zwarte_autor.rekord_id AND
    bpp_jednostka.id = bpp_wydawnictwo_zwarte_autor.jednostka_id AND
    bpp_wydzial.id = bpp_jednostka.wydzial_id AND
    bpp_jednostka.wchodzi_do_raportow = TRUE AND
    bpp_typ_kbn.id = bpp_wydawnictwo_zwarte.typ_kbn_id AND
    bpp_typ_kbn.skrot != 'PW'


  GROUP BY
    bpp_autor.id, bpp_jednostka.id, bpp_wydzial.id, bpp_wydawnictwo_zwarte.rok;


CREATE OR REPLACE VIEW bpp_sumy_all_view AS
  SELECT
    *
  FROM bpp_sumy_patent_view
  UNION
  SELECT
    *
  FROM bpp_sumy_praca_habilitacyjna_view
  UNION
  SELECT
    *
  FROM bpp_sumy_praca_doktorska_view
  UNION
  SELECT
    *
  FROM bpp_sumy_wydawnictwo_ciagle_view
  UNION
  SELECT
    *
  FROM bpp_sumy_wydawnictwo_zwarte_view;


CREATE OR REPLACE VIEW bpp_sumy_view AS
  SELECT
    autor_id,
    jednostka_id,
    wydzial_id,
    rok,
    SUM(punktacja_wewnetrzna) AS punktacja_wewnetrzna,
    SUM(impact_factor)        AS impact_factor,
    SUM(punkty_kbn)           AS punkty_kbn,
    SUM(index_copernicus)     AS index_copernicus,

    SUM(kc_impact_factor)     AS kc_impact_factor,
    SUM(kc_punkty_kbn)        AS kc_punkty_kbn,
    SUM(kc_index_copernicus)  AS kc_index_copernicus,

-- Kompatybilnosć z ModelPunktowany
    TRUE                      AS weryfikacja_punktacji

  FROM
    bpp_sumy_all_view


  GROUP BY
    autor_id, jednostka_id, wydzial_id, rok

  HAVING
    SUM(punktacja_wewnetrzna) > 0 OR
    SUM(impact_factor) > 0 OR
    SUM(punkty_kbn) > 0 OR
    SUM(index_copernicus) > 0;