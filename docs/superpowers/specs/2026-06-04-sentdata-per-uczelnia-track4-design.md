# Spec — Track 4: `SentData` per-uczelnia (klucz wysyłki PBN)

Audyt: `docs/superpowers/2026-06-04-audyt-uczelnia-coverage.md` (🔴 #6).
Decyzja usera: rekord wysyłany na N profili instytucji → N osobno oznaczonych
`SentData`; klucz lookup `(object_id, content_type, uczelnia)`.

## Dlaczego to outward-facing i krytyczne dla spójności

`SentData` to **stan wysyłki do zewnętrznego PBN** (`uploaded_okay`,
`submitted_successfully`, `data_sent`). Steruje czy w ogóle wyślemy
(`check_if_upload_needed`, `bad_uploads`, `only_new`). W multi-hosted dwie
uczelnie wysyłające ten sam rekord BPP **współdzielą i nadpisują** jeden wiersz
(`get_for_rec` po samym `object_id`+`content_type`) → wysyłka do drugiego profilu
PBN jest błędnie pomijana (zgubiona) albo nadpisana.

**Spójność krytyczna:** gdy zaczną istnieć ≥2 wiersze na `(object_id,
content_type)`, KAŻDE `get_for_rec(rec)` BEZ uczelni rzuci
`MultipleObjectsReturned`. Dlatego WSZYSTKIE call-site'y muszą być zmienione
atomowo — nie wolno zrobić tego połowicznie.

## Stan obecny
FK `uczelnia` na `SentData` JUŻ istnieje (nullable, `sentdata.py:137`), ale:
- `get_for_rec(rec)` filtruje tylko `(object_id, content_type)`;
- żadna metoda managera nie ustawia/filtruje `uczelnia`;
- wszystkie wiersze w runtime mają `uczelnia IS NULL` (integrator nigdy nie taguje).

## Zmiana managera (`pbn_api/models/sentdata.py`, `SentDataManager`)

Dodać parametr `uczelnia` do metod (keyword, dla zgodności default `None` →
zachowanie globalne tylko gdy NULL-owy świat; realne callery ZAWSZE podają):

| metoda | zmiana |
|---|---|
| `get_for_rec(self, rec, uczelnia=None)` | `qs = filter(object_id, content_type)`; `if uczelnia is not None: qs = qs.filter(uczelnia=uczelnia)`; `return qs.get()` |
| `check_if_needed(self, rec, data, uczelnia=None)` | przelot do `get_for_rec(rec, uczelnia)` |
| `check_if_upload_needed(self, rec, data, uczelnia=None)` | przelot do `get_for_rec(rec, uczelnia)` |
| `create_or_update_before_upload(self, rec, data, api_url="", uczelnia=None)` | `get_for_rec(rec, uczelnia)`; w `except DoesNotExist`: `create(..., uczelnia=uczelnia)` |
| `mark_as_successful(self, rec, pbn_uid_id=None, api_response_status="", uczelnia=None)` | `get_for_rec(rec, uczelnia)` |
| `mark_as_failed(self, rec, exception="", api_response_status="", uczelnia=None)` | `get_for_rec(rec, uczelnia)` |
| `updated(self, rec, data, pbn_uid_id=None, uploaded_okay=True, exception="", uczelnia=None)` | `get_for_rec(rec, uczelnia)`; create z `uczelnia=uczelnia` |
| `ids_for_model(self, model, uczelnia=None)` | `qs = filter(content_type)`; `if uczelnia: qs = qs.filter(uczelnia=uczelnia)` |
| `bad_uploads(self, model, uczelnia=None)` | `ids_for_model(model, uczelnia).filter(uploaded_okay=False)...` |

## Call-site'y (WSZYSTKIE — atomowo)

1. **`pbn_api/client/publication_sync.py`** (`PublicationSyncMixin`, ma `self.uczelnia`):
   - `:84` `check_if_upload_needed(rec, js)` → `+ uczelnia=self.uczelnia`
   - `:87` `get_for_rec(rec)` → `+ self.uczelnia`
   - `:204` `create_or_update_before_upload(rec, js, api_url=...)` → `+ uczelnia=self.uczelnia`
   - `:208` `mark_as_successful(rec, ...)` → `+ uczelnia=self.uczelnia`
   - `:210,215` `mark_as_failed(rec, ...)` → `+ uczelnia=self.uczelnia`
   - `:667` `get_for_rec(pub)` → `+ self.uczelnia`
2. **`pbn_integrator/utils/synchronization.py`** (`tworz_woluminy_do_synchronizacji`
   ma `client` → `client.uczelnia`):
   - `:204,244` `bad_uploads(Wydawnictwo_*)` → `+ uczelnia=client.uczelnia`
   - `:210,250` `ids_for_model(Wydawnictwo_*)` → `+ uczelnia=client.uczelnia`
   - (zweryfikować, że funkcja ma `client` w zasięgu w tych liniach)
3. **`bpp/admin/helpers/pbn_api/common.py:177,241`** `get_for_rec(obj)` (link admin do
   wysłanych danych): przekazać uczelnię z kontekstu akcji adminowej (ta sama, którą
   akcja użyła do uploadu — `get_for_request(request)`). Jeśli funkcja nie ma
   uczelni w zasięgu → dodać parametr i przekazać od wołającego (akcja PBN w
   adminie zna `get_for_request`).
4. **`bpp/system.py:142`** — sprawdzić użycie `SentData` (lista importów/cleanup);
   jeśli to globalny `.delete()`/iteracja → zawęzić lub udokumentować.
5. **`pbn_api/models/oswiadczenie_instytucji.py:201`** (override `delete()`):
   `SentData.objects.filter(pbn_uid_id=self.publicationId_id).delete()` — po
   tagowaniu dodać `uczelnia=self.uczelnia` do filtra (kasuj tylko SentData tej
   uczelni). Wymaga, by `OswiadczenieInstytucji.uczelnia` było ustawione (patrz
   Track 7 — obecnie nullable; jeśli NULL → zachowanie jak dawniej, global delete,
   ale to akceptowalne do czasu pełnego tagowania lustra).
6. **`pbn_export_queue/views/{utils,detail_views}.py`** — zweryfikować użycia
   `SentData` (grep wskazał plik); jeśli `get_for_rec`/display → przekazać uczelnię
   wpisu kolejki (`entry.uczelnia`).
7. **`pbn_integrator/utils/cleanup.py`** — zweryfikować (prawdop. global cleanup).

## Migracja + backfill

Schemat: FK już istnieje (nullable) → **brak zmiany schematu**, tylko data-migration:
- `RunPython`: jeśli `Uczelnia.objects.count() == 1` → `SentData.objects.filter(
  uczelnia__isnull=True).update(uczelnia=<ta jedna>)`.
- Multi-install z NULL-ami → **NIE failować, NIE kasować**: zostaw NULL. Nowy
  lookup filtruje po uczelni → NULL-owe wiersze stają się niewidoczne dla
  keyed-lookup, więc kolejna wysyłka utworzy poprawnie otagowany wiersz (co
  najwyżej jeden redundantny re-send per `(rec, uczelnia)` — samonaprawcze,
  bezpieczne; PBN przyjmie idempotentnie). Odnotować w komentarzu migracji.
- `uczelnia` **zostaje nullable** (faza przejściowa; NULL = legacy/nieotagowane).

## Test plan (TDD)

`pbn_api/tests/test_sentdata_per_uczelnia.py`:
1. `test_get_for_rec_per_uczelnia`: 2 uczelnie, `create_or_update_before_upload(
   rec, d1, uczelnia=U1)` + `(rec, d2, uczelnia=U2)` → `count()==2`;
   `get_for_rec(rec, U1).data_sent == d1`; `get_for_rec(rec, U2).data_sent == d2`.
2. `test_mark_successful_izolacja`: `mark_as_successful(rec, uczelnia=U1)` →
   `get_for_rec(rec, U1).uploaded_okay is True` AND `get_for_rec(rec, U2).
   uploaded_okay is False` (brak współdzielenia stanu).
3. `test_check_if_upload_needed_per_uczelnia`: po sukcesie U1, `check_if_upload_needed(
   rec, same_data, U1) is False` ale `(rec, same_data, U2) is True`.
4. `test_bad_uploads_per_uczelnia`: `bad_uploads(model, U1)` nie zawiera rekordu
   którego zła wysyłka była na U2.
5. Regresja: cała sucha `pbn_api/tests/` (test_client_upload, test_client_sync,
   test_bpp_admin_helpers — te WOŁAJĄ zmienione metody, zaktualizować je o
   `uczelnia=`).
6. `makemigrations --check` zielony; migracja backfill testowana single+multi.

## Inwariant
Single-install: po backfillu wszystkie wiersze mają tę jedną uczelnię; lookup z
`uczelnia=<ta>` = no-op. Zero zmian zachowania wysyłki przy 1 uczelni.

## Kolejność wykonania (atomowa)
manager → publication_sync → synchronization → admin/common → system/cleanup/
queue → oswiadczenie_instytucji.delete → migracja → testy istniejące (dopisać
`uczelnia=`) → nowe testy → pełna regresja `pbn_api` + `pbn_integrator`.
