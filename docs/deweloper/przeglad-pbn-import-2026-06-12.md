# Przegląd kodu importu PBN — 2026-06-12

> Read-only review przeprowadzony na branchu `feature/multi-hosted-config`.
> Implementacja poprawek: branch `feature/pbn-import-cleanup` → PR do
> `feature/multi-hosted-config`. Plan wdrożenia:
> [`docs/superpowers/plans/2026-06-12-pbn-import-cleanup.md`](../superpowers/plans/2026-06-12-pbn-import-cleanup.md).

## Zakres

Przegląd `src/pbn_import/` oraz powiązanego kodu importu PBN
(`pbn_integrator`, `pbn_api`, `import_common`). ~22k linii kodu produkcyjnego
(bez testów/migracji) w czterech głównych aplikacjach.

## Architektura — obraz ogólny

System jest poprawnie zbudowany **warstwowo**, nie jako konkurujące
reimplementacje:

```
pbn_import      (UI WebSocket/HTMX + ImportManager + pipeline kroków)  ← nowsza prezentacja
   └─deleguje→ pbn_integrator   (właściwy silnik importu encji)        ← kanoniczny
        └─używa→ pbn_api         (klient + adaptery + modele)
```

Zależność jest jednokierunkowa: `pbn_integrator` ma **zero** realnych
zależności kodowych od `pbn_import` (dwa „odwrotne" trafienia to nazwa
loggera `"pbn_import"` w `pbn_integrator/importer/publishers.py:14` oraz
`call_command` do komendy z `pbn_api`). 8 z 10 klas-kroków w
`pbn_import/utils/*_import.py` to cienkie wrappery (30–90 linii)
delegujące do `pbn_integrator`. **Nie ma duplikacji importerów encji do
usunięcia** — konsolidacja przeniosłaby kod, nie usunęła.

## Ustalenia i rekomendacje (rankingowane)

### 1. Martwa warstwa WebSocket — usunąć w całości ✅ DO ZROBIENIA

`pbn_import` dostarcza dwa mechanizmy postępu: Django Channels (WebSocket)
**oraz** polling HTMX. Działa tylko HTMX. Ścieżka WS jest martwa na trzy
niezależnie zabójcze sposoby (zweryfikowane bezpośrednio):

- **Niezgodność koperty.** Każde `send_websocket_update` pakuje payload jako
  `{"type": "import_update", ...}` (`tasks.py:27`, `views.py:307`), więc
  dispatchowany jest tylko handler `import_update` konsumenta. Bogatsze
  handlery `progress_update`/`log_entry`/`status_change`/`completion_notification`
  (`consumers.py:74–134`) są **nieosiągalne**.
- **Klient porzuca wszystko.** `dashboard.html:459` robi `switch(data.type)`
  na zewnętrznej kopercie (zawsze `"import_update"`), a `case` to
  `'progress_update'`/`'log_entry'`/`'completion'` — żaden nie pasuje, każda
  wiadomość jest odrzucana.
- **Nawet pasujący handler nic nie robi.** `updateProgressDisplay` ustawia
  tylko `document.title`; `addLogEntry` (`dashboard.html:464`) jest
  **wywoływany, ale nigdy nie zdefiniowany** (ReferenceError).

Polling HTMX (`every 5s` na postępie/logach) jest w pełni podłączony i to
on realizuje cały realtime.

**Akcja:** usunąć `consumers.py`, `routing.py`, helpery i wywołania
`send_websocket_update` (`tasks.py`, `views.py`), blok `<script>` WS
(`dashboard.html`), wpięcie w `django_bpp/asgi.py`, testy `test_consumers.py`
/ `test_routing.py`. Infrastruktura Channels zostaje (używa jej
`channels_broadcast`). ~250 linii mniej, zero utraty funkcjonalności.

### 2. Skrypty `fix_*` — POMINIĘTE (decyzja użytkownika)

`fix_missing_imported_pubs.py`, `fix_import_dat_oswiadczen_pbn.py`,
`fix_pbn_import_oswiadczen_ksiazki.py` — analiza wskazała część z nich jako
jednorazowe skrypty naprawcze (kandydaci do usunięcia), ale **na życzenie
użytkownika pozostawione bez zmian** w tym przebiegu.

### 3. Konsolidacja orkiestratorów — ⚠️ ZABLOKOWANE, NIE USUWAĆ

**Pierwotna rekomendacja zakładała, że legacy komenda `pbn_integrator` to
duplikat orkiestratora. Weryfikacja to OBALIŁA.** Komenda
`pbn_integrator/management/commands/pbn_integrator.py` zawiera istotną
**unikalną** funkcjonalność bez odpowiednika w nowym pipeline kroków:

- Etap 9 `weryfikuj_orcidy` (weryfikacja ORCID)
- Etap 15 `pobierz_skasowane_prace` (prace skasowane w PBN)
- Etapy 19/20 `pobierz_prace_po_doi` / `pobierz_prace_po_isbn`
- Etap 21 — raporty walidacyjne (`wyswietl_niezmatchowane...`,
  `sprawdz_ilosc_autorow...`)
- `_handle_clears` — `clear_all` / `clear_match_publications` /
  `clear_publications`
- `_handle_sync` — **cały kierunek wysyłki BPP→PBN**
  (`synchronizuj_publikacje`, `usun_wszystkie_oswiadczenia`,
  `usun_zerowe_oswiadczenia`, flagi `--force-upload`/`--only-bad`/`--only-new`)
- kontrola zakresu etapów (`--start-from-stage`/`--end-before-stage`)

Nowy pipeline `pbn_import` jest **wyłącznie pobierający/importujący**.
Usunięcie legacy komendy zniszczyłoby realną, krytyczną dla multi-hosted
funkcjonalność (wysyłka, czyszczenie, ORCID, DOI/ISBN, prace skasowane).
Komenda jest też referencjonowana w wielu aktywnych dokumentach
spec/audyt multi-hosted.

**Decyzja:** NIE usuwam legacy komendy bez nadzoru. Prawdziwa konsolidacja
wymaga najpierw przeniesienia (rehoming) ścieżek sync/clear/ORCID/DOI/ISBN
— to osobne, starannie zaplanowane zadanie. **Do decyzji rano.**

### 4. Wydajność warstwy widoków ✅ DO ZROBIENIA — WAŻNE

- **Nieograniczone ładowanie logów co 5 s.** Endpointy HTMX
  `ImportAllLogsView` (`views.py:583`) i `ImportErrorLogsView` (`views.py:600`)
  oraz `get_context_data` szczegółu sesji (`views.py:515,520`) robią
  `ImportLog.objects.filter(session=...).order_by("-timestamp")` **bez
  slice'a**. Długi import generuje tysiące wierszy `ImportLog` (jeden na
  każde wywołanie `ImportStepBase.log()`), a `all_logs.html` jest
  re-fetchowany `every 5s`. To O(wszystkie logi) na każdy poll, na każdą
  otwartą stronę. Kontrast: `ImportLogStreamView` (`views.py:405`) poprawnie
  tnie do `[:50]`.
- **Akcja:** wprowadzić stałą `MAX_LOGS_DISPLAY = 200` i zastosować slice w
  `views.py:515,520,583,600`. Pełny log jest i tak pobieralny przez
  `ImportLogDownloadView`.

### 5. Błędy poprawności ✅ DO ZROBIENIA

- **Anulowanie importu przez HTMX zwraca 500.** `components/progress.html:90`
  odwołuje się do `{% url 'pbn_import:stats' session.id %}`, a w `urls.py`
  **nie ma** trasy `stats`. Szablon renderowany jest przez ścieżkę HTMX
  `CancelImportView` (`views.py:373`) → `NoReverseMatch`. Naprawa: renderować
  `components/progress_compact.html`; `progress.html` staje się martwy →
  usunąć.
- **`SavePresetView` (`views.py:484`) to no-op.** `@csrf_exempt`,
  `json.loads(request.body)` bez zabezpieczenia (500 na złym body), komentarz
  „just return success", nic nie zapisuje, brak referencji w szablonach.
  Usunąć widok + trasę `save_preset` (`urls.py:52`).
- **Wyścig nadpisania `progress_data` (JSONField RMW).**
  `ImportStepBase.update_progress` (`base.py:142`) i `start` (`base.py:152`)
  robią pełny `self.session.save()` po mutacji jednego klucza JSON, mogąc
  nadpisać równoległy zapis throttlowanego `TqdmSessionProgress`
  (`base.py:55`, który zapisuje ze stale'owej kopii w pamięci). **Naprawa
  minimalna (bez migracji):** `refresh_from_db(fields=["progress_data"])`
  przed mutacją + zawężenie `save()` do `update_fields`. (Częstotliwość
  zapisów jest OK — `TqdmSessionProgress` throttluje do 1 zapisu/0.5 s.)

### 6. Drobne ✅ DO ZROBIENIA (okrojone)

- **Efekt uboczny w konstruktorze.** `ImportManager.__init__` wywołuje
  `self.client.get_languages()` po sieci (`import_manager.py:47→60`) tylko
  by sprawdzić autoryzację — samo skonstruowanie obiektu robi call API.
  Naprawa: przenieść `_check_pbn_authorization()` z `__init__` na początek
  `run()` (API publiczne bez zmian).
- **Nieaktualny `CODEBASE_MAP.md`** (datowany 2026-01-16; liczby tokenów nie
  zgadzają się z liniami, opisuje usunięty krok `data_integration`).
  Oznaczyć jako historyczny / odświeżyć nagłówek.
- **UWAGA — odrzucone fałszywe trafienia:** wcześniejsza analiza sugerowała
  „martwe helpery" `mark_completed`, `clear_subtask_progress`,
  `update_subtask_progress`. Weryfikacja: **wszystkie są używane**
  (`import_manager.py:320`, każdy krok, `fee_import.py:45`). NIE usuwać.

## Pliki

- Ten przegląd: `/Users/mpasternak/Programowanie/bpp-multi-hosted-config/docs/deweloper/przeglad-pbn-import-2026-06-12.md`
  file:///Volumes/mpasternak/Programowanie/bpp-multi-hosted-config/docs/deweloper/przeglad-pbn-import-2026-06-12.md
- Plan: `/Users/mpasternak/Programowanie/bpp-multi-hosted-config/docs/superpowers/plans/2026-06-12-pbn-import-cleanup.md`
  file:///Volumes/mpasternak/Programowanie/bpp-multi-hosted-config/docs/superpowers/plans/2026-06-12-pbn-import-cleanup.md
