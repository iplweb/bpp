-- Usuniecie redundantnych indeksow NIEOSIAGALNYCH przez modele Django:
--  * bpp_autorzy_mat: tabela managed=False, indeksy zakladane raw SQL-em;
--  * _52be3978 na praca_doktorska/habilitacyjna: indeksy OSIEROCONE (stara
--    nazwa-hash sprzed zmiany schematu nazewnictwa Django) — nie ma ich w
--    stanie modeli, wiec AlterField ich nie ruszy.
-- DROP ... IF EXISTS = no-op, gdy na danym wdrozeniu nazwa nie istnieje
-- (np. swiezy install ma aktualne nazwy, nie stare). Wzorzec jak 0422.
BEGIN;
-- bpp_autorzy_mat_2 (autor_id): redundantny prefiks _4 (autor_id, jednostka_id)
-- oraz _5 (autor_id, typ_odpowiedzialnosci_id). (_6 usuniety juz w 0422.)
DROP INDEX IF EXISTS bpp_autorzy_mat_2;
-- Osierocone duplikaty na autor_id (stara nazwa _52be3978). Aktualny indeks
-- FK (praca_doktorska: _5b69bdd7) / UNIQUE OneToOne (praca_habilitacyjna)
-- zostaje nietkniety.
DROP INDEX IF EXISTS bpp_praca_doktorska_52be3978;
DROP INDEX IF EXISTS bpp_praca_habilitacyjna_52be3978;
COMMIT;
