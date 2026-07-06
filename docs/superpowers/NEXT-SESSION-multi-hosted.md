# NEXT SESSION — multi-hosted audyty (do wklejenia po resecie)

> Wklej treść sekcji „PROMPT DO WKLEJENIA" niżej jako pierwszą wiadomość po resecie.
> Reszta dokumentu to kontekst, który agent może doczytać.

---

## PROMPT DO WKLEJENIA

Jesteś świeżą sesją. Repo: `~/Programowanie/bpp-multi-hosted-config`, gałąź
`feature/multi-hosted-config` (BPP, Django). Wątki multi-hosted (R1 slot read-side,
R2 ewaluacja_liczba_n, integrator PBN, drobne, HST per-uczelnia, NOT NULL, verify.py)
są ZROBIONE i wypushowane — pełny stan w `docs/superpowers/HANDOFF-multi-hosted.md`
(przeczytaj go najpierw). Teraz cztery audyty multi-hosted. Dla każdego: ustal fakty,
pokaż znaleziska, zaproponuj fix, NIE implementuj bez mojej zgody (brainstorming →
spec → plan → subagent-driven, jak poprzednio). Zacznij od audytów 1–3 (read-only
rozpoznanie, równolegle), potem 4.

**Audyt 1 — pozostałe `get_default`/`objects.default` bez świadomego „zostaje".**
Źródło prawdy: `src/bpp/tests/test_multihosted_get_default_guard.py` (dict `APPROVED`).
Dla KAŻDEGO wpisu z whitelisty przeczytaj kod w danym pliku i oceń: czy to NAPRAWDĘ
świadomy, nieusuwalny fallback (np. brak requestu w CLI/Celery, czysty display,
docstring/komentarz), czy „odłożone" które da się już zrobić per-uczelnia. Szczególnie
podejrzane: `powiazania_autorow/queries.py` (opis: „deferred multi-host" — to nie
„zostaje", to dług). Zwróć tabelę: plik → uzasadnienie → werdykt (ZOSTAJE / DO ZROBIENIA
+ jak). Sprawdź też `grep -rnE "objects\.default|get_default\(\)" src --include=*.py`
poza whitelistą (guard łapie runtime, ale potwierdź brak nowych w testach/komentarzach
które realnie są kodem).

**Audyt 2 — zadania Celery bez argumentu `uczelnia`.**
Znajdź definicje tasków (`@shared_task`, `@app.task`, `@task`, `bind=True`) w całym
`src/` i wytypuj te, które dotykają logiki zależnej od uczelni (PBN klient, sloty,
liczba_n, metryki, oświadczenia, eksport) a NIE przyjmują `uczelnia`/`uczelnia_id`
ani nie wyprowadzają uczelni jawnie (np. z `get_for_request` — niedostępne w tle!,
albo z FK obiektu). Tła bez requestu to typowe miejsce regresji multi-hosted (reguła
projektu: tło → jawna uczelnia: argument / FK / `Uczelnia.objects.get()` single-or-fail,
NIGDY get_default/get_for_request). Start: `grep -rnE "@shared_task|@app\.task|@task\b|\.delay\(|\.apply_async" src --include=*.py`. Zwróć listę: task → czy
uczelnia-zależny → czy ma uczelnię → ryzyko.

**Audyt 3 — gdzie jeszcze uczelnia się przyda.**
Poszukaj miejsc, które POWINNY być per-uczelnia, a nie są: filtry/agregaty po
`Autor_Dyscyplina`/`Cache_Punktacja_*`/`Rekord` bez uczelni w widokach/raportach/API;
flagi `Uczelnia` (pbn_*, pbn_wysylaj_*, ukryte_statusy, obca_jednostka) czytane „raz
globalnie"; rankingi/„liczba N"/eksporty/PBN-wysyłka. Skup się na ŚCIEŻKACH RUNTIME
widzianych przez użytkownika danej uczelni. Federacja optymalizacji (ewaluacja_optymalizacja,
ewaluacja_optymalizuj_publikacje) jest ŚWIADOMIE OLANA — NIE proponuj jej. Zwróć listę
kandydatów z oceną „realny multi-host gap" vs „OK/świadome".

**Audyt 4 — self-review kodu vs SPEC i PLAN.**
Dla każdej pary spec+plan w `docs/superpowers/specs/` i `docs/superpowers/plans/`
z 2026-06-02/03 (per-uczelnia-sloty write+read, liczba_n R2, integrator) sprawdź:
czy zrealizowany kod pokrywa KAŻDY punkt spec; czy plan był adekwatny; czy są
rozjazdy (zrobione inaczej niż spec — czy świadomie), luki (spec mówił, kod nie robi),
nadmiar (kod robi, spec nie przewidywał). Użyj `git log --oneline origin/dev..HEAD`
i diffów. Dla rzetelności rozważ subagentów-recenzentów per obszar. Zwróć raport:
spec → pokrycie (✓/luka/rozjazd) + rekomendacje.

Reguły: `uv run` zawsze; testy `-p no:cacheprovider` (testcontainers, Docker musi
działać); guard test `uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q`;
lint `uv run ruff check` (NIE `--fix`); commituj/pushuj tylko gdy poproszę.

---

## KONTEKST (stan na 2026-06-03, agent może doczytać)

**Zrobione i wypushowane** (gałąź `feature/multi-hosted-config`):
- **R1 — slot read-side**: widok `bpp_cache_punktacja_autora_view` eksponuje
  `uczelnia_id`; helper `uczelnia_dla_odczytu` (hybryda site+superuser); raport_slotow
  (RaportSlotowUczelnia FK + generacja + RaportSlotow autor), oswiadczenia, API
  filtrują po uczelni; API owner-scoped.
- **R2 — ewaluacja_liczba_n**: FK `uczelnia` na `IloscUdzialow*` (+NOT NULL mig 0428),
  cały pipeline `utils.py` per-uczelnia (autor→`aktualna_jednostka.uczelnia`, NULL/obca
  wykluczeni; naprawiony globalny `objects.all().delete()`), widoki list/export/verify
  filtrują, admin pokazuje uczelnię.
- **Integrator PBN**: authors.py / pbn_integrator command / scientists.py matcher —
  `client.uczelnia` / `autor.aktualna_jednostka.uczelnia`; `pbn_integrator/` czyste.
- **HST #1**: `wiele_hst` liczone per-uczelnia (`_dopasuj_kalkulator(original, uczelnia)`
  + `wszystkie_dyscypliny_rekordu(uczelnia)`).
- **verify.py**: reads + 4 POST-fixy per-uczelnia.

**Guard whitelist (`APPROVED`) — stan obecny (11 wpisów, materiał do Audytu 1):**
`bpp/middleware.py:1`, `bpp/util/bpp_specific.py:2`, `bpp/models/abstract/pbn.py:2`,
`bpp/models/jednostka.py:1`, `bpp/multiseek_registry/fields/numeric_fields.py:1`,
`ewaluacja2021/util.py:1`, `pbn_api/management/commands/util.py:1`,
`pbn_import/templatetags/pbn_import_tags.py:1`, `pbn_import/utils/command_helpers.py:1`,
`powiazania_autorow/queries.py:1` (← „deferred", podejrzane).
(`pbn_integrator/*` i `bpp/models/sloty/*` USUNIĘTE z whitelisty — zrobione.)

**Reguła binarna multi-hosted (do oceniania znalezisk):** runtime z dostępną uczelnią
→ JAWNA uczelnia (`get_for_request` w widoku / argument / FK / `self.uczelnia`); tło/CLI
bez requestu → `Uczelnia.objects.get()` single-or-fail (NIGDY `get_default`/`get_for_request`).
Atrybucja autora do uczelni: `autor.aktualna_jednostka.uczelnia`, tylko gdy
`skupia_pracownikow=True` (NULL/obca → wykluczony).

**Świadomie OLANE (nie proponować):** federacja optymalizacji
(`ewaluacja_optymalizacja`, `ewaluacja_optymalizuj_publikacje`).

**Dokumenty:** `docs/superpowers/HANDOFF-multi-hosted.md` (master),
`docs/superpowers/specs/2026-06-0{2,3}-*`, `docs/superpowers/plans/2026-06-0{2,3}-*`,
`docs/superpowers/reviews/2026-06-03-self-review-per-uczelnia-sloty-write-side.md`.
