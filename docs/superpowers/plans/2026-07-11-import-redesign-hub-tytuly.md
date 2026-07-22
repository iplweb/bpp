# Import pracowników — hub / dopasowanie autora / tytuły — plan implementacyjny

> **Dla wykonawców (subagentów):** wykonuj zadanie po zadaniu, TDD (test →
> patrz-że-czerwony → kod → zielony). Kroki mają checkboksy `- [ ]`. Spec:
> `docs/superpowers/specs/2026-07-11-import-redesign-hub-tytuly.md`.

**Cel:** przeprojektować ekran importu pracowników — dopasowanie autora zamiast
edycji XLS, hub z kafelkami, reconciler tytułów analogiczny do jednostek.

**Architektura:** trzy części na jednej gałęzi
`feat/import-pracownikow-tworzenie-jednostek`. Część 3 kopiuje istniejący wzorzec
reconcilera jednostek (klasyfikacja → decyzja per unikalny string → integracja
tworzy). Części 1–2 to warstwa widoków/szablonów/endpointów htmx.

**Tech stack:** Django, Foundation CSS + Foundation-Icons, htmx 2, Select2/DAL
(bundle.js globalny), PostgreSQL pg_trgm, django-liveops.

## Ograniczenia globalne (każde zadanie je dziedziczy)

- Max **88 znaków/linia** (ruff). `uv run` przed każdą komendą Pythona.
- Testy pytest-style (funkcje, `@pytest.mark.django_db`, `baker.make`), output
  do pliku + grep, `-n auto`. Select2/AJAX: symulować pisanie, nie wstrzykiwać PK.
- **Nie modyfikować migracji 0016** ani wydanych; nowa migracja **0017**.
  Baseline (`make baseline-update`) — dopiero przy scaleniu, NIE w tej pracy.
- Komentarze Django `{# #}` jedno-liniowe. Ikony publiczne: Foundation-Icons.
- Bez `except: pass` (loguj / re-raise / sensowny błąd).
- Confident status autora = `STATUS_TWARDY` (NIE „pewny"/„STATUS_PEWNY").

## Mapa własności plików i zrównoleglenia

`models.py`, `views.py`, `urls.py`, `analyze.py`, `integrate.py` są
**współdzielone** — nie wolno ich edytować dwoma subagentami naraz. Stąd fale:

| Fala | Zadania | Pliki (rozłączne w obrębie fali) | Równolegle? |
|---|---|---|---|
| **A** | T3.1, T1.1 | `import_common/core/tytul.py`+test; `bpp/views/autocomplete/authors.py`+`bpp/urls.py` | **TAK** (rozłączne) |
| **B** | T3.2–T3.7 | całe `import_pracownikow/*` backend tytułów | jeden subagent, sekwencyjnie |
| **C** | T1.2–T1.5 | `views.py`/`urls.py`/`_wiersz_preview.html`/`pewnosc.py` | jeden subagent (po B) |
| **D** | T2.1–T2.5 | `views.py`/`urls.py`/`models.py`/szablony hub | jeden subagent (po C) |
| **E** | T-final | newsfragment, pełne testy, run-site | main agent |

Fale B→C→D są sekwencyjne (kontencja na `views.py`/`urls.py`/`models.py`); każdy
subagent widzi na dysku zmiany poprzedniej fali. Fala A jest równoległa.

---

## FALA A (równolegle)

### Task T3.1 — `import_common/core/tytul.py` (klasyfikacja tytułów)

**Files:**
- Create: `src/import_common/core/tytul.py`
- Test: `src/import_common/core/tests/test_tytul.py` (sprawdź, czy katalog
  `tests/` istnieje; jeśli nie — `src/import_common/tests/test_core_tytul.py`
  obok istniejących testów core)

**Interfaces (Produces):**
```python
PROG_ZGADYWANIA_TYTULU = 0.85
STATUS_TYTUL_TWARDY = "twardy"
STATUS_TYTUL_ZGADYWANIE = "zgadywanie"
STATUS_TYTUL_BRAK = "brak"

def normalize_tytul(s: str) -> str: ...
    # lower + strip + collapse spacji (" ".join(split)) + usuń kropki
def sklasyfikuj_tytul(tytul_str):  # -> (Tytul|None, status, similarity|None)
def zaproponuj_skrot_tytulu(s: str) -> str: ...  # trim do 128
```

Wzorzec: `src/import_common/core/jednostka.py` (`sklasyfikuj_jednostke`,
TrigramSimilarity+Greatest, Q). Różnice: matchuj po WSZYSTKICH `bpp.Tytul` (bez
„puli afiliacyjnej"); porównanie exact po `normalize_tytul` OBU stron
(`Tytul.nazwa`/`skrot`); pusty/None `tytul_str` → `(None, BRAK, None)`.

- [ ] **Krok 1:** testy (test_tytul.py):
  - `test_pusty_tytul_brak`: `sklasyfikuj_tytul("")` == `(None, BRAK, None)`;
    `None` też.
  - `test_norm_exact_warianty` (`@pytest.mark.django_db`): `baker.make(Tytul,
    nazwa="doktor habilitowany", skrot="dr hab.")`; `"dr hab."`, `"Dr. Hab"`,
    `"dr hab"` → wszystkie `(tytul, TWARDY, None)`.
  - `test_zgadywanie_powyzej_progu`: literowo bliski skrót → `ZGADYWANIE`, sim
    ≥ 0.85 (dobierz fixture tak, by trigram był wysoki).
  - `test_smiec_brak`: „xyz123" → `(None, BRAK, None)`.
  - `test_zaproponuj_skrot_tnie_dluzszy_128`.
- [ ] **Krok 2:** uruchom → czerwone (brak modułu).
- [ ] **Krok 3:** implementacja wg wzorca jednostki.
- [ ] **Krok 4:** `uv run pytest <ścieżka test_tytul.py> -p no:cacheprovider`
  (testcontainers) → zielone.
- [ ] **Krok 5:** ruff format + check na obu plikach.

### Task T1.1 — autocomplete autorów dla importu (`import-autor-autocomplete`)

**Files:**
- Modify: `src/bpp/views/autocomplete/authors.py` (dopisz klasę na końcu)
- Modify: `src/bpp/urls.py` (dopisz `path` obok `autor-*-autocomplete`,
  ~linia 461-473)
- Test: `src/bpp/tests/test_autocomplete_import_autor.py` (lub dołóż do
  istniejącego testu autocomplete autorów, jeśli jest)

**Interfaces (Produces):** URL name `import-autor-autocomplete`, widok
`ImportAutorAutocomplete`.

Wzorzec: przeczytaj `authors.py` — `AutorAutocomplete` (create_field="nonzero"),
`AutorAktualnieZatrudnionyNaUczelni` (scope aktualnie zatrudnieni),
`PublicAutorAutocomplete` (scope „kiedykolwiek związani"). Nowy widok:
- scope = autorzy **kiedykolwiek związani z tą uczelnią** (dowolne
  `Autor_Jednostka` do jednostki tej uczelni, aktualne LUB historyczne — jak
  `PublicAutorAutocomplete`/„kiedykolwiek"),
- **`create_field = None`** (NIE tworzyć autorów z autocomplete — dry-run),
- `get_result_label` czytelny (nazwisko, imię, jednostka).

- [ ] **Krok 1:** test (`@pytest.mark.django_db`, `admin_client`):
  - autor z historycznym AJ do jednostki uczelni JEST w wynikach dla query po
    nazwisku;
  - autor bez żadnego związku z uczelnią NIE jest;
  - odpowiedź JSON nie zawiera opcji „create" (klucz `create_option` pusty /
    brak).
- [ ] **Krok 2:** czerwone (NoReverseMatch / brak klasy).
- [ ] **Krok 3:** implementacja + url.
- [ ] **Krok 4:** test zielony.
- [ ] **Krok 5:** ruff.

---

## FALA B — backend tytułów (jeden subagent, sekwencyjnie)

Kolejność wewnątrz: T3.2 → T3.7 → T3.3 → T3.4 → T3.6 → T3.5. Po każdej zmianie
modeli: `uv run python src/manage.py makemigrations import_pracownikow` (jedna
migracja **0017**).

### Task T3.2 — model `ImportPracownikowTytul` + pola + migracja 0017

**Files:** Modify `src/import_pracownikow/models.py`; Create migracja `0017`.

- [ ] Dodaj model `ImportPracownikowTytul` — **mirror `ImportPracownikowJednostka`**
  (models.py:614), uproszczony (bez parenta/wydziału). Pola: `parent`
  (related_name=`tytuly_do_decyzji`), `nazwa_zrodlowa` (max 512), `tryb`
  (`zgadywanie`/`brak`, TRYB_CHOICES), `auto_tytul` FK `bpp.Tytul` SET_NULL
  related_name="+", `auto_similarity` FloatField null, `nazwa_do_utworzenia`
  (max 512, blank, default=""), `skrot_do_utworzenia` (max 128, blank),
  `decyzja` (akceptuj/mapuj/pomin, default akceptuj, DECYZJA_CHOICES),
  `wybrany_tytul` FK Tytul SET_NULL related_name="+", `utworzony` FK Tytul
  SET_NULL related_name="+" (guard idempotencji). `unique_together
  (("parent","nazwa_zrodlowa"),)`, `ordering ["nazwa_zrodlowa"]`. Stałe
  `TRYB_*`/`DECYZJA_*` jak w jednostce.
- [ ] Dodaj do `ImportPracownikowRow`: `tytul_status` (CharField
  max_length=20, choices=STATUS_CHOICES, null, blank — noqa DJ001, jak
  `jednostka_status` models.py:261) i `zrodlo_tytulu` FK
  `ImportPracownikowTytul` SET_NULL null blank related_name="wiersze_tytul".
- [ ] Dodaj do `ImportPracownikow`: `tworz_brakujace_tytuly` BooleanField
  default=True + help_text (analog `tworz_brakujace_jednostki` models.py:70).
- [ ] `uv run python src/manage.py makemigrations import_pracownikow` → 0017.
  Sprawdź, że migracja jest addytywna (AddField/CreateModel), nie dotyka 0016.
- [ ] Test: `test_models_tytul.py` — `baker.make(ImportPracownikowTytul)`,
  `unique_together` (drugi create tej samej pary rzuca IntegrityError),
  `related_name` działa.

### Task T3.7 — symetryzacja `_check_autor_needs_update`

**Files:** Modify `src/import_pracownikow/models.py` (metoda ~339).

- [ ] Test regresji (`test_zmiany_potrzebne_tytul.py`): autor z tytułem, wiersz
  z `tytul=None` (pusty/pomin) → `check_if_integration_needed()` NIE zwraca True
  z powodu tytułu (inne pola bez zmian → False).
- [ ] Czerwone (dziś zwraca True bezwarunkowo `self.tytul_id != a.tytul_id`).
- [ ] Zmień ostatnią linię `_check_autor_needs_update`: porównuj tytuł tylko gdy
  `self.tytul_id is not None`:
  ```python
  if self.tytul_id is not None and self.tytul_id != a.tytul_id:
      return True
  return False
  ```
  (import USTAWIA tytuł, nigdy nie kasuje — spójne z `_integrate_autor`:390).
- [ ] Zielone. Uruchom istniejące testy modeli import_pracownikow — brak
  regresji.

### Task T3.3 — analiza: `_ReconcilerTytulow` + klasyfikacja w wierszu

**Files:** Modify `src/import_pracownikow/pipeline/analyze.py`.

- [ ] Dodaj `_ReconcilerTytulow` — **mirror `_ReconcilerJednostek`** (analyze.py:77):
  `reconciluj(nazwa_zrodlowa, tryb, auto_tytul, sim)` get_or_create po
  `nazwa_zrodlowa__iexact`, odświeża pola liczone, ZACHOWUJE
  `decyzja`/`wybrany_tytul`/`nazwa_do_utworzenia`/`skrot_do_utworzenia`; przy
  create ustawia `nazwa_do_utworzenia=nazwa_zrodlowa[:512]`,
  `skrot_do_utworzenia=zaproponuj_skrot_tytulu(nazwa_zrodlowa)`. `usun_stale`.
- [ ] Zastąp `_dopasuj_tytul` (analyze.py:160) klasyfikacją. W `_przetworz_wiersz`
  (gdzie dziś `tytul = _dopasuj_tytul(tytul_str)` ~:312):
  ```
  tytul, tyt_status, tyt_sim = sklasyfikuj_tytul(tytul_str)
  if not tytul_str:            row.tytul=None; row.tytul_status=None
  elif tyt_status == TWARDY:   row.tytul=tytul; row.tytul_status=TWARDY
  elif tyt_status == ZGADYWANIE or (BRAK and tworz_brakujace_tytuly):
       dec = reconciler_tytulow.reconciluj(tytul_str, tyt_status, tytul, tyt_sim)
       row.zrodlo_tytulu=dec; row.tytul=None; row.tytul_status=tyt_status
  else:                        row.tytul=None; row.tytul_status=BRAK
  ```
  `tworz_brakujace_tytuly` czytaj z `parent`. Reconciler instancjonuj raz na
  przebieg analizy (jak `_ReconcilerJednostek`), `usun_stale()` po pętli wierszy.
- [ ] `on_restart` (models.py:92) już kasuje wiersze; decyzje tytułów są
  współdzielone → NIE kasować ich w on_restart (mirror jednostki: reconciler
  `usun_stale` czyści znikłe nazwy). Zweryfikuj, że `tytuly_do_decyzji` nie są
  osierocane błędnie (test niżej).
- [ ] Testy (`test_analyze_tytuly.py`): niepusty niedopasowany tytuł → 1 decyzja
  na unikalny string (dedup iexact dla 2 wierszy „Dr. Hab"/„dr hab."); pusty
  tytuł → 0 decyzji; `usun_stale` kasuje decyzję znikłej nazwy; ponowna analiza
  zachowuje `decyzja` usera.

### Task T3.4 — integracja: `_rozstrzygnij_tytuly` (FAZA 0.5)

**Files:** Modify `src/import_pracownikow/pipeline/integrate.py`.

- [ ] Dodaj `unikalny_skrot_tytulu(base, zajete)` (może w `core/tytul.py` lub
  lokalnie) — mirror `unikalny_skrot` (jednostka.py:174) na `Tytul.skrot`.
- [ ] `_rozstrzygnij_jeden_tytul(dec, zajete_nazwy, zajete_skroty, p)` →
  `(Tytul|None, czy_utworzono)`. Guard `utworzony`; `pomin`→None;
  `mapuj`→`wybrany_tytul`; `akceptuj`+`zgadywanie`→`auto_tytul`;
  `akceptuj`+`brak`→ **unikalność OBU pól** (`Tytul.nazwa` i `skrot` są
  `unique=True`): `Tytul.objects.filter(nazwa__iexact=dec.nazwa_do_utworzenia)
  .first()` → jeśli jest, użyj; else `create(nazwa=nazwa_do_utworzenia[:512],
  skrot=unikalny_skrot_tytulu(skrot_do_utworzenia or zaproponuj_skrot_tytulu(...),
  zajete_skroty))`; dopisz do `zajete_nazwy`/`zajete_skroty`.
- [ ] `_podlacz_wiersze_do_tytulow(parent)` — mirror
  `_podlacz_wiersze_do_jednostek` (integrate.py:431). Dla wierszy z
  `zrodlo_tytulu`: `row.tytul = zrodlo_tytulu.utworzony` (zawsze).
  **GUARD (BLOCKER):** przelicz `zmiany_potrzebne` TYLKO gdy `row.autor_id is not
  None and row.autor_jednostka_id is not None`, monotonicznie:
  `row.zmiany_potrzebne = bool(row.diff_do_utworzenia) or
  row.check_if_integration_needed() or row.zmiany_potrzebne`. Wiersze bez autora:
  tylko `save(update_fields=["tytul"])`. Wiersze z autorem:
  `save(update_fields=["tytul","zmiany_potrzebne"])`.
- [ ] `_rozstrzygnij_tytuly(parent, p)`: `zajete_nazwy=set()`,
  `zajete_skroty=set()`; pętla `parent.tytuly_do_decyzji.all()`, per decyzja
  `transaction.atomic` + guard `utworzony`; na końcu `_podlacz_wiersze_do_tytulow`.
  W `integruj` (integrate.py:502) wywołaj **zaraz po** `_rozstrzygnij_jednostki`
  (przed snapshotem `stare_jednostki` i fazą nowych autorów).
- [ ] Testy (`test_integrate_tytuly.py`): `akceptuj+brak` tworzy `Tytul`
  (nazwa/skrót z decyzji, skrót unikalny przy kolizji); `mapuj` używa
  istniejącego; `pomin` → nowy autor bez tytułu, istniejący zachowuje tytuł;
  idempotencja (drugi `integruj` nie duplikuje — guard `utworzony`); wiersz
  `brak`-autora z `zrodlo_tytulu` NIE crashuje (guard); nazwa edytowana na
  istniejącą → dołącza (nie IntegrityError).

### Task T3.6 — toggle `tworz_brakujace_tytuly` w UI mapowania

**Files:** Modify `src/import_pracownikow/forms.py` (MapowanieForm),
`src/import_pracownikow/views.py` (MapowanieView.form_valid ~229),
`templates/.../mapowanie.html` (jeśli pola renderowane jawnie).

- [ ] Dodaj `tworz_brakujace_tytuly` do `MapowanieForm` (jak
  `tworz_brakujace_jednostki`); w `form_valid` zapisz do `update_fields`.
- [ ] Test: POST mapowania z checkboxem ustawia flagę na obiekcie.

### Task T3.5 — ekran `WeryfikacjaTytulowView` + `tytuly` URL + szablon

**Files:** Modify `views.py` (+klasa), `urls.py` (+path `tytuly`); Create
`templates/import_pracownikow/weryfikacja_tytulow.html`.

- [ ] `WeryfikacjaTytulowView` — **mirror `WeryfikacjaJednostekView`** (views.py:626).
  GET: `decyzje_brak`/`decyzje_zgadywanie`, `mapuj_opcje=Tytul.objects.all()`,
  `moze_edytowac = stan==PRZEANALIZOWANY`, DECYZJA_*. POST: zapis decyzji +
  edytowalne `nazwa_do_utworzenia`/`skrot_do_utworzenia` (tylko dla `brak`),
  tylko w stanie przeanalizowany. `liczba_osob=Count("wiersze_tytul", distinct=True)`.
- [ ] URL `path("<uuid:pk>/tytuly/", WeryfikacjaTytulowView.as_view(),
  name="tytuly")`.
- [ ] Szablon — mirror `weryfikacja_jednostek.html`. Sekcja „Do utworzenia"
  (`brak`): kolumny nazwa z pliku · osób · decyzja · **nazwa** (input
  `dec_{pk}_nazwa`) · **skrót** (input `dec_{pk}_skrot`) · mapuj-na (select
  Tytul). Sekcja „Dopasowane automatycznie" (`zgadywanie`): nazwa · osób ·
  auto-tytuł+similarity · decyzja · mapuj-na. Breadcrumb + „← wróć do przeglądu"
  (link do `przeglad` — do wpięcia w Fali D; tymczasowo do
  `importpracownikow-results`, D poprawi).
- [ ] Testy (`test_views_tytuly.py`): GET renderuje sekcje; POST zapisuje
  decyzję+nazwa/skrót; bramka stanu (poza przeanalizowany → 400/disabled).

**Po Fali B:** `uv run pytest src/import_pracownikow -n auto` (do pliku) — zielone.

---

## FALA C — dopasowanie autora (jeden subagent, po B)

### Task T1.2 — helper `_zwiaz_autora_z_wierszem` + `DopasujAutoraView`

**Files:** Modify `pewnosc.py` (lub `views.py`) — helper; `views.py` — widok +
refaktor `WybierzKandydataView`; `urls.py` — `dopasuj-autora`.

- [ ] Przeczytaj pełne `WybierzKandydataView` (views.py:314-357). Wyodrębnij
  `_zwiaz_autora_z_wierszem(row, autor)`:
  - `row.autor = autor`;
  - **guard**: `if row.jednostka_id is None:` →
    `row.diff_do_utworzenia.pop("autor_jednostka", None); row.autor_jednostka=None;
    row.zmiany_potrzebne=False` (mirror analyze.py:302); else
    `odtworz_autor_jednostka(row, autor)`;
  - `row.confidence=STATUS_TWARDY; row.utworz_nowego=False;
    row.przepnij_prace=False; row.wybrany_kandydat=None`;
  - `row.save(update_fields=["autor","confidence","autor_jednostka",
    "diff_do_utworzenia","zmiany_potrzebne","utworz_nowego","przepnij_prace",
    "wybrany_kandydat"])`.
- [ ] `WybierzKandydataView` wołaj helper, a PO nim ustaw
  `row.wybrany_kandydat=autor` + `save(update_fields=["wybrany_kandydat"])`
  (provenance) — istniejące testy WybierzKandydata muszą przejść.
- [ ] `DopasujAutoraView(_WierszImportuMixin)`: POST, `autor =
  get_object_or_404(Autor, pk=request.POST.get("autor"))`,
  `_zwiaz_autora_z_wierszem(row, autor)`, `_render_wiersz()`. Owner-scoped,
  bramka `przeanalizowany`.
- [ ] URL `dopasuj-autora`
  (`<uuid:pk>/wiersz/<int:row_pk>/dopasuj-autora/`).
- [ ] Testy (`test_dopasuj_autora.py`): wiąże autora, `confidence=twardy`,
  przelicza AJ/zmiany; wiersz `jednostka=None` NIE tworzy diff `{"jednostka":
  None}` i `zmiany_potrzebne=False`; owner-scoping; bramka stanu; zły pk → 404.

### Task T1.3 — usunięcie edycji XLS (`EdytujWierszView`/`_rematch_wiersz`)

**Files:** Modify `views.py` (usuń klasę+funkcję), `urls.py` (usuń
`edytuj-wiersz`); Delete/adjust `test_views_wiersz.py` (testy edycji); update
docstringi (integrate.py:178 G1 +DopasujAutoraView, integrate.py:327 F5,
test_integrate_nowy_autor.py:60).

- [ ] Usuń `EdytujWierszView`, `_rematch_wiersz`, URL `edytuj-wiersz` i testy
  edycji (`test_views_wiersz.py` sekcje edycji).
- [ ] Zaktualizuj docstringi wymieniające `EdytujWierszView`.
- [ ] Test regresji: `reverse("import_pracownikow:edytuj-wiersz", ...)` →
  NoReverseMatch.

### Task T1.4 — przebudowa `_wiersz_preview.html` (kolumna Akcje/zmiany)

**Files:** Modify `templates/.../partials/_wiersz_preview.html`.

- [ ] Kolumny Imiona/Nazwisko/Tytuł: read-only (bez inputów). Usuń formularz
  free-text.
- [ ] `wielu`: zostaw dropdown kandydatów (`wybierz-kandydata`); dodaj „inny
  autor…" — leniwy Select2 (`import-autor-autocomplete`) → `dopasuj-autora`.
- [ ] `brak`: Select2 „Dopasuj do istniejącego autora" → `dopasuj-autora` +
  checkbox „utwórz nowego" (`utworz-nowego`, bez zmian).
- [ ] `twardy`/`zgadywanie`: dyskretny „zmień autora" rozwijający Select2 →
  `dopasuj-autora` (`zgadywanie` badge warning „potwierdź").
- [ ] Select2: manualny wzorzec `importer_publikacji/partials/step_authors.html:530`
  (goły `<select>` + `select2({ajax:{url}})`), **init leniwie** po kliknięciu
  „zmień autora"/rozwinięciu, re-init na `htmx:afterSettle`.
- [ ] Test render partiala per stan (bez free-textu; obecność autocomplete/
  checkboxów wg stanu).

### Task T1.5 — testy integracyjne (opcjonalne, Playwright)

- [ ] `test_import_dopasuj_autora.py` (integration_tests): wiersz `brak`,
  wpisanie nazwiska w Select2 (`select_select2_autocomplete`), wybór autora →
  wiersz staje się „twardy". Wymaga `make assets`. Jeśli środowiskowo ciężkie —
  oznacz i uruchom lokalnie.

**Po Fali C:** `uv run pytest src/import_pracownikow -n auto` — zielone.

---

## FALA D — hub z kafelkami (jeden subagent, po C)

### Task T2.1 — liczniki na `ImportPracownikow`

**Files:** Modify `models.py`.

- [ ] `liczniki_ludzi_z_xls()` → dict `{twardy, zgadywanie, wielu, brak}` z
  `importpracownikowrow_set.values("confidence").annotate(Count("id"))`,
  **koaguluj `None`→`brak`**. `liczniki_jednostek()` /`liczniki_tytulow()` →
  `{do_utworzenia, do_sprawdzenia}` (nierozstrzygnięte
  `utworzona/utworzony__isnull=True`, split po `tryb`).
- [ ] Testy liczników.

### Task T2.2 — `PodgladImportuView` (hub) + `przeglad.html`

**Files:** Modify `views.py`, `urls.py`; Create `templates/.../przeglad.html`.

- [ ] `PodgladImportuView` (GroupRequiredMixin, DetailView) — owner-scoped
  `parent_object`. Kontekst: liczniki, flagi widoczności kafelków
  (`jednostki_do_decyzji.exists()`, `tytuly_do_decyzji.exists()`),
  `odpiecia_count`, `pary_z_pliku_puste` (dla ostrzeżenia), stan. CTA „Zapisz do
  bazy" (`zatwierdz`) gdy `stan==PRZEANALIZOWANY`.
- [ ] URL `przeglad` (`<uuid:pk>/przeglad/`).
- [ ] `przeglad.html`: 2–4 kafelki (🏢 Jednostki warunkowy, 👤 Ludzie z XLS
  zawsze, 🔗 Ludzie spoza XLS zawsze + ostrzeżenie gdy `pary_z_pliku` puste a
  odpięć dużo, 🎓 Tytuły warunkowy). Liczniki: pewne/luźne/do-akceptacji;
  do-utworzenia/do-sprawdzenia; K powiązań. Foundation kafelki (grid + callout),
  Foundation-Icons.
- [ ] Testy: hub renderuje się w każdym stanie; kafelki warunkowe (0 decyzji →
  ukryty); liczniki zgodne; CTA tylko w przeanalizowany.

### Task T2.3 — `OdpieciaView` + `odpiecia.html` + usuń odpięcia z results

**Files:** Modify `views.py` (nowy widok + `ImportPracownikowResultsView` usuń
`odpiecia` z kontekstu), `urls.py`; Create `templates/.../odpiecia.html`;
Modify `importpracownikowrow_list.html` (usuń sekcję odpięć).

- [ ] `OdpieciaView` (ListView/View), owner-scoped, queryset =
  `parent.odpiecia.select_related(...)` (przeniesiony z ResultsView:611).
- [ ] URL `odpiecia`. Szablon `odpiecia.html` — tabela + partial
  `_odpiecie_row.html` (bez zmian), breadcrumb + „← wróć do przeglądu".
- [ ] Z `importpracownikowrow_list.html` usuń sekcję `{% if odpiecia %}`; z
  `ResultsView.get_context_data` usuń `odpiecia`.
- [ ] Testy: `odpiecia` renderuje tabelę; `przelacz-odpiecie` działa; results
  NIE renderuje sekcji odpięć.

### Task T2.4 — wpięcie nawigacji (linki wejścia + „wróć do przeglądu")

**Files:** Modify `importpracownikow_list.html` (+link „Przegląd", NIE ruszać
`get_absolute_url`/live), `import_pracownikow_result.html` („Zobacz szczegóły" →
`przeglad`), `weryfikacja_jednostek.html` / `weryfikacja_tytulow.html` /
`odpiecia.html` / `importpracownikowrow_list.html` („← wróć do przeglądu" →
`przeglad`).

- [ ] Dodaj linki; test: podstrony mają link do `przeglad`; lista importów ma
  link „Przegląd"; panel wyniku linkuje do `przeglad`.

### Task T2.5 — testy huba end-to-end (widokowe)

- [ ] Osiągalność wszystkich URLi z huba; liczniki spójne z danymi testowymi.

**Po Fali D:** `uv run pytest src/import_pracownikow -n auto` — zielone.

---

## FALA E — finalizacja (main agent)

- [ ] Newsfragmenty towncrier (`src/bpp/newsfragments/`):
  `+import-pracownikow-dopasowanie-autora.feature.rst`,
  `+import-pracownikow-hub-kafelki.feature.rst`,
  `+import-pracownikow-tytuly-reconciler.feature.rst`.
- [ ] `ruff format . && ruff check .` (tylko zmienione pliki — nie `--all-files`).
- [ ] Pełne `uv run pytest src/import_pracownikow -n auto` + smoke reszty.
- [ ] Weryfikacja na `run-site` (jeśli biegnie): hub, dopasowanie autora, ekran
  tytułów, odpięcia — realny plik IHIT.
- [ ] `grunt build` jeśli dotknięto SCSS (kafelki mogą wymagać stylu — Foundation
  callout/grid zwykle wystarcza bez SCSS).
- [ ] **NIE** odświeżać baseline (przy scaleniu). **NIE** commitować bez zgody
  usera.

## Self-review planu

- Pokrycie speca: T3.* = reconciler tytułów (klasyfikacja/model/analiza/
  integracja/ekran/toggle/symetryzacja) ✓; T1.* = dopasowanie autora
  (autocomplete/helper+guardy/usunięcie edycji/partial) ✓; T2.* = hub
  (liczniki/landing/odpięcia/nawigacja) ✓.
- Findingi review wpięte: BLOCKER-guard (T3.4), unikalność nazwa+skrót (T3.4),
  scope autocomplete bez create (T1.1), guard jednostka=None (T1.2), symetryzacja
  (T3.7), UI toggle (T3.6), NULL confidence (T2.1), etykieta odpięć+ostrzeżenie
  (T2.2), kompletne update_fields (T1.2), manual Select2 lazy (T1.4), osierocone
  docstringi (T1.3), terminologia/link (T1.1/T2.4).
- Spójność typów: `STATUS_TWARDY` wszędzie; `zrodlo_tytulu`/`tytuly_do_decyzji`/
  `utworzony` konsekwentnie.
