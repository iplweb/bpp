-- Usuniecie nieuzywanych / redundantnych indeksow na mat-tabelach cache.
-- Potwierdzone pg_stat_user_indexes z produkcji (idx_scan=0 lub redundantny
-- prefiks). Mniej indeksow = mniejsza amplifikacja zapisu triggera
-- bpp_refresh_cache() (DELETE+INSERT na kazde odswiezenie) + mniej miejsca.
-- Zachowane: indeksy uzywane, unikalne, FK, wariant upper() trigramow
-- (kod szuka przez upper()/iexact; surowe gin(col) mialy 0 uzyc).
BEGIN;
-- bpp_rekord_mat: surowe trigramy (martwe; uzywany wariant upper())
DROP INDEX IF EXISTS bpp_rekord_mat_public_www;   -- gin(public_www), 0 uzyc (jest _public_www_gin)
DROP INDEX IF EXISTS bpp_rekord_mat_www;          -- gin(www), 0 uzyc (jest _www_gin)
DROP INDEX IF EXISTS bpp_rekord_mat_doi_gin;      -- gin(doi), 0 uzyc (jest _doi=upper)
DROP INDEX IF EXISTS bpp_rekord_mat_isbn;         -- gin(isbn), 0 uzyc (jest _isbn_gin=upper)
DROP INDEX IF EXISTS bpp_rekord_mat_e_isbn;       -- gin(e_isbn), 0 uzyc
DROP INDEX IF EXISTS bpp_rekord_mat_e_isbn_gin;   -- gin(upper(e_isbn)), 0 uzyc
-- bpp_rekord_mat: btree na polach tekstowych szukanych trigramem (0 uzyc)
DROP INDEX IF EXISTS bpp_rekord_mat_public_www_idx; -- btree(public_www), 0 uzyc
DROP INDEX IF EXISTS bpp_rekord_mat_www_idx;        -- btree(www), 0 uzyc
DROP INDEX IF EXISTS bpp_rekord_mat_isbn_idx;       -- btree(isbn), 0 uzyc
DROP INDEX IF EXISTS bpp_rekord_mat_e;              -- btree(uwagi) free-text, 0 uzyc
DROP INDEX IF EXISTS bpp_rekord_mat_f;              -- btree(adnotacje) free-text, 3 uzycia
-- bpp_rekord_mat: btree na kolumnach nieuzywanych w zapytaniach (0 uzyc)
DROP INDEX IF EXISTS bpp_rekord_mat_9;  -- index_copernicus
DROP INDEX IF EXISTS bpp_rekord_mat_5;  -- wydawnictwo
DROP INDEX IF EXISTS bpp_rekord_mat_n;  -- openaccess_tryb_dostepu_id (nie-FK)
DROP INDEX IF EXISTS bpp_rekord_mat_k;  -- recenzowana (bool)
DROP INDEX IF EXISTS bpp_rekord_mat_q;  -- dostep_dnia
DROP INDEX IF EXISTS bpp_rekord_mat_p;  -- liczba_cytowan
-- bpp_autorzy_mat
DROP INDEX IF EXISTS bpp_autorzy_mat_7;   -- upowaznienie_pbn (bool), 0 uzyc
DROP INDEX IF EXISTS bpp_autorzy_mat_11;  -- przypieta (bool), 0 uzyc
DROP INDEX IF EXISTS bpp_autorzy_mat_12;  -- data_oswiadczenia, 0 uzyc
DROP INDEX IF EXISTS bpp_autorzy_mat_6;   -- dyscyplina_naukowa_id: redundantny prefiks _8 (dyscyplina, rekord_id)
COMMIT;
