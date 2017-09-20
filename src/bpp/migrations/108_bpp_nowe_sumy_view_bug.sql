
CREATE OR REPLACE VIEW bpp_nowe_sumy_view AS
  SELECT
    *
  FROM bpp_nowe_sumy_patent_view
  UNION ALL
  SELECT
    *
  FROM bpp_nowe_sumy_praca_habilitacyjna_view
  UNION ALL
  SELECT
    *
  FROM bpp_nowe_sumy_praca_doktorska_view
  UNION ALL
  SELECT
    *
  FROM bpp_nowe_sumy_wydawnictwo_ciagle_view
  UNION ALL
  SELECT
    *
  FROM bpp_nowe_sumy_wydawnictwo_zwarte_view;
