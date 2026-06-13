-- Eliminacja trigger_tytul_sort (§2 spec). Klucz sortu tytułu liczy teraz
-- ModelPrzeszukiwalny.save() (bpp/models/abstract/search.py). Wszystkie zapisy
-- tytul_oryginalny idą przez ORM, więc gwarancja triggera DB jest zbędna.
--
-- Usuwamy 5 triggerów BEFORE INSERT/UPDATE + samą funkcję plpython3u
-- (jedyną — obok bpp_refresh_cache ze Spec 1 — używającą stanu GD).

DROP TRIGGER IF EXISTS bpp_patent_tytul_oryginalny_sort_trigger ON public.bpp_patent;
DROP TRIGGER IF EXISTS bpp_praca_doktorska_tytul_oryginalny_sort_trigger ON public.bpp_praca_doktorska;
DROP TRIGGER IF EXISTS bpp_praca_habilitacyjna_tytul_oryginalny_sort_trigger ON public.bpp_praca_habilitacyjna;
DROP TRIGGER IF EXISTS bpp_wydawnictwo_ciagle_tytul_oryginalny_sort_trigger ON public.bpp_wydawnictwo_ciagle;
DROP TRIGGER IF EXISTS bpp_wydawnictwo_zwarte_tytul_oryginalny_sort_trigger ON public.bpp_wydawnictwo_zwarte;

DROP FUNCTION IF EXISTS public.trigger_tytul_sort();
