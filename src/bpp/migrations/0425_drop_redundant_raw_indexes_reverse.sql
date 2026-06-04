-- Reverse migracji 0425: odtworzenie skasowanych indeksow (dokladne definicje
-- z produkcji). IF NOT EXISTS — zeby nie kolidowac z ewentualnym aktualnie
-- nazwanym indeksem na tej samej kolumnie.
BEGIN;
CREATE INDEX IF NOT EXISTS bpp_autorzy_mat_2 ON public.bpp_autorzy_mat USING btree (autor_id);
CREATE INDEX IF NOT EXISTS bpp_praca_doktorska_52be3978 ON public.bpp_praca_doktorska USING btree (autor_id);
CREATE INDEX IF NOT EXISTS bpp_praca_habilitacyjna_52be3978 ON public.bpp_praca_habilitacyjna USING btree (autor_id);
COMMIT;
