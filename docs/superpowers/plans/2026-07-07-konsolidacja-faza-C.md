# Konsolidacja Wydział → Jednostka — Faza C (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Usunąć ostatecznie legacy model `Wydzial` i całą jego powierzchnię (API, autocomplete, importer-widget, demo-data, komendy, redirect), zdjąć markery konwersji `legacy_wydzial_id`/`jest_lustrem`, wyczyścić osierocone `ContentType`/`Permission`, i zaudytować konfigurowalny label poziomu top-level — kończąc konsolidację w jedno drzewo `Jednostka`.

**Architecture:** Faza B już scaliła strukturę: „wydział" = jednostka top-level (`parent IS NULL`), `Jednostka.wydzial` = denorm self-FK do korzenia. Faza B **już usunęła** `WydzialAdmin`, `WydzialInline`, `WydzialSitemap`, `WydzialView`, template'y wydziału, i **przepięła wszystkie 5 zewnętrznych FK** (`Kierunek_Studiow`, `Patent`, `Opi_2012_Afiliacja_Do_Wydzialu`, `Import_Dyscyplin_Row`, `Obslugujacy_Zgloszenia_Wydzialow`) z `Wydzial` na `Jednostka`. Faza C to więc: (1) przepięcie kilku miejsc, gdzie `Wydzial` NADAL wykonuje realną pracę (importer, demo-data, matchowanie, komendy), (2) usunięcie read-only powierzchni (API, autocomplete, redirect), (3) `DeleteModel('Wydzial')`, (4) drop markerów `legacy_wydzial_id`/`jest_lustrem`, (5) czyszczenie sierot uprawnień, (6) audit labela.

**Tech Stack:** Django 5, PostgreSQL, django-mptt, django-denorm-iplweb, django-import-export, DRF (api_v1), django-autocomplete-light, multiseek, pytest + model_bakery + testcontainers.

## Global Constraints

- **`uv run` przed KAŻDYM Pythonem.** Nigdy goły `python`/`pytest`. Testy: `PYTEST_TESTCONTAINERS_DISABLE=1` gdy masz własne `docker compose up db redis`, inaczej testcontainers same wstają.
- **Max line length: 88** (ruff). `ruff format` + `ruff check` czysto na zmienionych plikach. Pre-commit: NIGDY z argumentami; NIE `ruff --fix` — fixy ręcznie Editem.
- **NIE modyfikuj istniejących migracji.** Nowe migracje: liść bpp na `dev` to `src/bpp/migrations/0465_merge_20260707_0736.py` (Faza B = 0454–0464 + merge 0465). Sprawdź przed KAŻDYM taskiem: `git fetch origin dev` → `ls src/bpp/migrations | grep -E '^0[0-9]{3}_' | sort | tail -3` → renumeruj (Phase C startuje od 0466).
- **Zielony suite per task.** Pytest stosuje WSZYSTKIE migracje po baseline. **Task = jeden commit.**
- **⚠ Pułapka `filter(FK=<zła-instancja>)`:** Django **NIE rzuca**, gdy podasz obiekt złego modelu do `filter()` — po cichu porównuje `.pk`. Dlatego każde przepięcie „podaj `Wydzial` → podaj root `Jednostka`" i jego konsumenci MUSZĄ być w jednym commicie, z testem-inwariantem.
- **Baseline:** `make baseline-update` RAZ, na końcu (Task 13). NIE w trakcie.
- **22 historyczne migracje** referują `bpp.Wydzial` (`apps.get_model`, FK-decls historyczne). Działają na modelach HISTORYCZNYCH — `DeleteModel` na czubku grafu ich NIE łamie. Nie ruszamy ich.

---

## ✅ DECYZJE (ROZSTRZYGNIĘTE 2026-07-07)

- **D1 → Opcja A.** Redirect `/wydzial/<slug>/` mapuje 1:1 po slugu `Jednostka` i tak ma zostać. (Task 7 bez zmian.)
- **D2 → NIE.** Pole `Jednostka.wydzial` ZOSTAJE pod tą nazwą — bez renamu. **Task R1 SKREŚLONY.**
- **D3 → ODŁOŻONE.** Rename modelu `Jednostka` poza zakresem. (Task R2 = won't-do.)

Poniżej pełny kontekst decyzji (dla wykonawcy).

### D1 — Los `browse_wydzial_redirect` (stare URL-e `/wydzial/<slug>/`) — ROZSTRZYGNIĘTE: Opcja A
Redirect mapuje stary slug wydziału → węzeł przez `Wydzial.slug` + `legacy_wydzial_id`. Drop OBU (model + pole) kasuje to mapowanie. **`django.contrib.redirects` NIE jest zainstalowane** (sprawdzone), więc nie ma gotowego fallbacku.
- **Opcja A (rekomendowana, domyślna w planie):** zachowaj istniejący fallback po slugu Jednostki. Redirect zostaje jako `RedirectView`/funkcja, która: jeśli istnieje `Jednostka` o dokładnie tym slugu → 301; inaczej 404. Promowane 1-jednostkowe wydziały (0457) mają root == realna jednostka, więc ich slug ZWYKLE się zgadza. Syntetyczne lustra z suffiksem `[W<id>]` w nazwie → slug się różni → te URL-e dają 404. Koszt: część starych linków wydziałowych 404-uje. Tanie, bez nowej infry.
- **Opcja B:** przed dropem `legacy_wydzial_id` (Task 10) dodaj `django.contrib.redirects` (INSTALLED_APPS + `RedirectFallbackMiddleware` + migracja) i data-migracją zbackfilluj `Redirect(old_path=/wydzial/<slug>/, new_path=/jednostka/<node.slug>/)` z żywego `Wydzial`+węzła, PÓKI oba jeszcze istnieją. Zero martwych linków. Koszt: nowa aplikacja + middleware + trwała tabela redirectów.

**Domyślnie plan realizuje Opcję A** (Task 7). Jeśli chcesz B — powiedz, dopiszę data-migrację w Task 7/10.

### D2 — Rename `Jednostka.wydzial` → `jednostka_toplevel` — ROZSTRZYGNIĘTE: NIE
Denorm self-FK nazywa się `wydzial`, choć od Fazy B wskazuje KORZEŃ drzewa. **Decyzja usera: zostaw nazwę `wydzial` bez zmian.** Task R1 skreślony — zero renamu pola w Fazie C, zero ryzyka cichego `filter(pk)` z tego tytułu.

### D3 — Rename modelu `Jednostka` → `JednostkaOrganizacyjna` — ROZSTRZYGNIĘTE: ODŁOŻONE
Poza zakresem Fazy C. (Task R2 = won't-do.)

---

## Mapa usuwanej powierzchni (z inwentaryzacji na `origin/dev`)

**Wydzial NADAL wykonuje realną pracę (wymaga przepięcia PRZED dropem):**
- `src/bpp/admin/jednostka_import.py` — `WydzialGetOrCreateWidget` tworzy realne `Wydzial` przy imporcie XLSX.
- `src/bpp/demo_data/generators/wydzialy.py` — `create_wydzialy` bulk-tworzy `Wydzial`.
- `src/import_common/core/tytul_funkcja.py::matchuj_wydzial` + `src/import_common/core/jednostka.py::_wydzial_filtr` — matchowanie po `Wydzial`.
- `src/bpp/admin/helpers/site_filtered.py:44-47` — `Wydzial.objects.filter(uczelnia=…)` dla pola `wydzial` (już martwe po repoint FK w B — do usunięcia/przepięcia).
- Komendy: `import_jednostki_ipis.py`, `mapuj_kierunki_studiow.py`, `zaloz_jednostki_domyslne.py`, `rebuild_slugs.py`, `prace_do_rozliczenia.py`, `look_for_unused_fields.py` (string), `konwertuj_wydzialy_na_jednostki.py`, `waliduj_konwersje_wydzialow.py`.
- `src/bpp/models/struktura_konwersja.py` — fabryka węzła-lustra (zależy od żywego `Wydzial`).

**Read-only powierzchnia (czysta do usunięcia):**
- API: `src/api_v1/viewsets/struktura.py` (`WydzialViewSet`), `src/api_v1/serializers/struktura.py` (`WydzialSerializer`), `src/api_v1/urls.py:23,100`, `src/api_v1/views.py:95`.
- Autocomplete: `src/bpp/views/autocomplete/simple.py:201-217` (`WydzialAutocomplete`, `PublicWydzialAutocomplete`), `__init__.py:81,86`, `src/bpp/urls.py:51,61,371-373,386-388`.
- `src/bpp/views/browse.py:146-169` (`browse_wydzial_redirect`) + `src/bpp/urls.py:90,251-253` (per D1).
- Settings/dashboard: `src/django_bpp/settings/base.py:1413`, `src/django_bpp/settings/production.py:109`, `src/django_bpp/dashboard.py:46`.

**Model + markery:**
- `src/bpp/models/wydzial.py` (cały plik: klasa `Wydzial`, `JednostkaCreateManager`, 2 sygnały, helper).
- Eksporty/importy: `src/bpp/models/struktura.py:14-18`, `src/bpp/models/jednostka.py:32`.
- `Jednostka.legacy_wydzial_id` (`jednostka.py:198`), `Jednostka.jest_lustrem` (`jednostka.py:208`).

**ZOSTAJE (NIE ruszać):**
- `Uczelnia.uzywaj_wydzialow` (flaga per-uczelnia — Decyzja #5, ZOSTAJE; tylko audit labela).
- `WydzialQueryObject`/`PierwszyWydzialQueryObject`/`JednostkaNadrzednaQueryObject` (multiseek — operują na denorm `Jednostka.wydzial`, NIE na modelu `Wydzial`).
- `Obslugujacy_Zgloszenia_Wydzialow` (już `Jednostka`-backed).
- `Jednostka.wydzial` denorm field (D2=nie — nazwa `wydzial` zostaje).
- `PublicJednostkaWydzialRankinguAutocomplete` (`units.py` — Jednostka-backed, zastąpił stary public-wydzial-autocomplete).

---

## Sub-plan C-1 — Przepięcie funkcjonalnych użytkowników `Wydzial` (przed dropem)

### Task 1: Repoint matchowania importu (`matchuj_wydzial` + `_wydzial_filtr`)

**Files:**
- Modify: `src/import_common/core/tytul_funkcja.py:26-33` (`matchuj_wydzial`)
- Modify: `src/import_common/core/jednostka.py:20-41` (`_wydzial_filtr`), usuń import `matchuj_wydzial`
- Test: `src/import_common/tests/test_core.py` (istnieje; hity `legacy_wydzial_id` w :67-117)

**Interfaces:**
- Produces: `matchuj_wydzial(nazwa) -> Jednostka | None` (root top-level zamiast `Wydzial`); `_wydzial_filtr(wydzial_nazwa) -> Q` filtrujące po korzeniu-Jednostce.

- [ ] **Step 1: Zaktualizuj test** — istniejące testy w `test_core.py` tworzą `Wydzial` + oczekują matchu po `legacy_wydzial_id`. Przepisz je tak, by tworzyły top-level `Jednostka` (rolę wydziału) i sprawdzały, że `matchuj_jednostke(nazwa, wydzial=<nazwa-roota>)` dobiera właściwą jednostkę pod korzeniem. Wzorzec fixture: `baker.make(Jednostka, nazwa="Wydział X", parent=None)` + dziecko `baker.make(Jednostka, parent=root)`.

- [ ] **Step 2: Uruchom test → RED**
  Run: `uv run pytest src/import_common/tests/test_core.py -v`
  Expected: FAIL (matchuj_wydzial wciąż zwraca Wydzial / import się sypie po zmianie).

- [ ] **Step 3: Przepisz `matchuj_wydzial`**
```python
def matchuj_wydzial(nazwa: str | None):
    """Dobiera jednostkę TOP-LEVEL (rolę dawnego wydziału) po nazwie.

    Faza C (#438): model ``Wydzial`` usunięty — „wydział" to jednostka
    z ``parent IS NULL``. Zwraca ``Jednostka | None``.
    """
    if nazwa is None:
        return
    return Jednostka.objects.filter(
        parent__isnull=True, nazwa__iexact=nazwa.strip()
    ).first()
```
   (Zmień import na `from bpp.models import Jednostka`; usuń import `Wydzial`.)

- [ ] **Step 4: Uprość `_wydzial_filtr`** — skoro `matchuj_wydzial` zwraca już root-Jednostkę:
```python
def _wydzial_filtr(wydzial):
    """``Q`` zawężające jednostki do dawnego wydziału podanego NAZWĄ.

    Faza C (#438): „wydział" = jednostka top-level. Dobieramy root po
    nazwie, potem filtrujemy jednostki pod nim (denorm ``wydzial``) ORAZ
    sam root. Fallback na nazwę korzenia, gdy nie ma roota o tej nazwie.
    """
    root = matchuj_wydzial(wydzial)
    if root is not None:
        return Q(wydzial=root) | Q(pk=root.pk)
    return Q(wydzial__nazwa__iexact=wydzial)
```
   (Import `matchuj_wydzial` zostaje; usuń wszelkie `legacy_wydzial_id`.)

- [ ] **Step 5: Uruchom test → GREEN**
  Run: `uv run pytest src/import_common/tests/test_core.py src/import_common -v`
  Expected: PASS.

- [ ] **Step 6: Commit**
```bash
git add src/import_common/core/tytul_funkcja.py src/import_common/core/jednostka.py src/import_common/tests/test_core.py
git commit -m "refactor(438-C): matchuj_wydzial/wydzial_filtr → jednostka top-level (drop Wydzial dep)"
```

### Task 2: Repoint importer-widget `WydzialGetOrCreateWidget` → top-level Jednostka

**Files:**
- Modify: `src/bpp/admin/jednostka_import.py:30,82-139,158-164` (import, klasa widgetu, docstringi)
- Test: `src/bpp/tests/test_admin/` (znajdź test importu jednostek; jeśli brak — dodaj `test_jednostka_import.py`)

**Interfaces:**
- Produces: `WydzialGetOrCreateWidget.clean(value, row) -> Jednostka` — get-or-create top-level `Jednostka` (parent=None) po `nazwa`; pole zasobu `wydzial` nadal pisze do `parent`.

- [ ] **Step 1: Test** — resource importuje wiersz z nowym wydziałem → powstaje `Jednostka(parent=None, nazwa=...)`, a jednostka-dziecko dostaje ten root jako `parent`. Drugi wiersz z tą samą nazwą wydziału → NIE tworzy duplikatu roota.
```python
@pytest.mark.django_db
def test_import_tworzy_wydzial_jako_jednostke_toplevel(uczelnia):
    from bpp.admin.jednostka_import import JednostkaImportResource
    from bpp.models import Jednostka
    import tablib
    ds = tablib.Dataset(headers=["Uczelnia", "Wydział", "Katedra/Zakład/Klinika"])
    ds.append([uczelnia.nazwa, "Wydział Testowy", "Katedra Alfa"])
    JednostkaImportResource().import_data(ds, raise_errors=True)
    root = Jednostka.objects.get(nazwa="Wydział Testowy")
    assert root.parent is None
    katedra = Jednostka.objects.get(nazwa="Katedra Alfa")
    assert katedra.parent_id == root.pk
```

- [ ] **Step 2: RED** — `uv run pytest src/bpp/tests/test_admin/test_jednostka_import.py -v` → FAIL (widget tworzy Wydzial).

- [ ] **Step 3: Przepisz widget** — target modelu na `Jednostka`, get-or-create top-level:
```python
class WydzialGetOrCreateWidget(ForeignKeyWidget):
    """ForeignKey widget: get-or-create jednostki TOP-LEVEL po ``nazwa``.

    Faza C (#438): model ``Wydzial`` usunięty. „Wydział" = jednostka z
    ``parent IS NULL``; pole zasobu pisze wynik do ``parent`` importowanej
    jednostki. Uczelnia z kolumny ``Uczelnia`` (obiekt Jednostka jeszcze
    nie istnieje, więc nie sięgniemy przez FK).
    """

    def __init__(self, **kwargs):
        super().__init__(Jednostka, field="nazwa", **kwargs)

    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        nazwa = str(value).strip()
        if not nazwa:
            return None

        existing = Jednostka.objects.filter(
            parent__isnull=True, nazwa=nazwa
        ).first()
        if existing is not None:
            return existing

        uczelnia_value = (row or {}).get(COLUMN_UCZELNIA)
        if not uczelnia_value:
            raise ValueError(
                f"Brak kolumny '{COLUMN_UCZELNIA}' dla wydziału '{nazwa}'."
            )
        try:
            uczelnia = Uczelnia.objects.get(nazwa=str(uczelnia_value).strip())
        except Uczelnia.DoesNotExist as exc:
            raise ValueError(
                f"Uczelnia '{str(uczelnia_value).strip()}' nie istnieje. "
                "Utwórz ją ręcznie i ponów import."
            ) from exc

        used = set(Jednostka.objects.values_list("skrot", flat=True))
        skrot = unique_skrot(abbreviate_wydzial(nazwa), used, max_len=128)
        return Jednostka.objects.create(
            uczelnia=uczelnia, nazwa=nazwa, skrot=skrot, parent=None
        )
```
   Usuń import `Wydzial` (`:30`) i import `znajdz_lub_utworz_wezel_wydzialu` (`:105`). Zaktualizuj docstring modułu (`:14-20`) i komentarze `:101-104,158-159`.

- [ ] **Step 4: GREEN** — `uv run pytest src/bpp/tests/test_admin/test_jednostka_import.py -v` → PASS.

- [ ] **Step 5: Commit**
```bash
git add src/bpp/admin/jednostka_import.py src/bpp/tests/test_admin/test_jednostka_import.py
git commit -m "refactor(438-C): importer XLSX tworzy wydział jako jednostkę top-level"
```

### Task 3: Repoint demo-data `create_wydzialy` → top-level Jednostka

**Files:**
- Modify: `src/bpp/demo_data/generators/wydzialy.py` (cały generator)
- Modify: `src/bpp/demo_data/manifest.py:30` (`"bpp.Wydzial"` w spisie modeli)
- Inspect+Modify: `src/bpp/demo_data/orchestrator.py`, `generators/jednostki.py` (jak konsumują wynik `create_wydzialy` — root dla jednostek)
- Test: `src/bpp/tests/test_demo_data/test_command_create.py` (hit `legacy_wydzial_id` :57), `test_e2e.py:61`

**Interfaces:**
- Produces: `create_wydzialy(...) -> list[Jednostka]` — top-level jednostki (`parent=None`), manifest `"bpp.Jednostka"`.

- [ ] **Step 1: Przeczytaj** `orchestrator.py` + `generators/jednostki.py`, ustal jak `create_wydzialy` wynik trafia jako `parent`/root do jednostek (podłączenie MPTT). Zanotuj kontrakt.

- [ ] **Step 2: Test** — `test_command_create.py`/`test_e2e.py` asertują na `Wydzial`/`legacy_wydzial_id`; przepisz na: demo tworzy N top-level jednostek (`parent__isnull=True`) o rodzaju „Wydział", a niższe jednostki mają je jako `parent`.

- [ ] **Step 3: RED** — `uv run pytest src/bpp/tests/test_demo_data/ -v` → FAIL.

- [ ] **Step 4: Przepisz `create_wydzialy`** — buduj `Jednostka(parent=None, uczelnia=…, nazwa=…, skrot=…, rodzaj=<RodzajJednostki „Wydział">, kolejnosc=i)`; `bulk_create` NIE ustawia pól MPTT — po bulku wywołaj `Jednostka.objects.rebuild()` (mptt) LUB twórz pojedynczo `Jednostka.objects.create(...)` (MPTT liczy lft/rght). Manifest: `manifest.append("bpp.Jednostka", …)`. Zaktualizuj `manifest.py:30`.
   ⚠ MPTT + bulk_create: pola drzewa muszą zostać przeliczone — najbezpieczniej `Jednostka.objects.rebuild()` po bat/u, albo `create()` per-obiekt (wolniej, ale demo).

- [ ] **Step 5: GREEN** — `uv run pytest src/bpp/tests/test_demo_data/ -v` → PASS. Dodatkowo odpal `uv run python src/manage.py` demo-command smoke, jeśli istnieje w teście e2e.

- [ ] **Step 6: Commit**
```bash
git add src/bpp/demo_data/ src/bpp/tests/test_demo_data/
git commit -m "refactor(438-C): demo-data generuje wydziały jako jednostki top-level"
```

### Task 4: Przepięcie/usunięcie komend zarządzania + admin site_filtered

**Files:**
- Delete: `src/bpp/management/commands/konwertuj_wydzialy_na_jednostki.py`, `waliduj_konwersje_wydzialow.py` (jednorazowe narzędzia konwersji Fazy A/B — martwe po dropie). Usuń też ich testy: `test_konwertuj_wydzialy.py`, `test_*waliduj*`.
- Delete: `src/bpp/management/commands/import_jednostki_ipis.py` (jednorazowy skrypt z zahardkodowaną ścieżką `/Users/mpasternak/...jednostki-uniq.txt` — nie repointować, usunąć).
- Modify: `src/bpp/management/commands/mapuj_kierunki_studiow.py:6,31-35` (repoint `Wydzial` → top-level `Jednostka`), `zaloz_jednostki_domyslne.py:23,135-140`, `rebuild_slugs.py:4,12` (usuń `Wydzial` z listy `[Autor, Jednostka, Wydzial, Uczelnia, Zrodlo]`), `prace_do_rozliczenia.py:14,44` (`for wydzial in Wydzial.objects.all()` → rooty), `look_for_unused_fields.py:15` (usuń string `"Wydzial"` ze skip-listy).
- Modify: `src/bpp/admin/helpers/site_filtered.py:44-47` — usuń gałąź `db_field.name == "wydzial"` z `Wydzial.objects` (FK `wydzial` konsumentów jest już `Jednostka`-typed po B; gałąź daje ZŁY queryset). Zostaw gałąź `jednostka`.

- [ ] **Step 1: Grep-inwentaryzacja żywych callerów** usuwanych komend:
  Run: `git grep -n "konwertuj_wydzialy_na_jednostki\|waliduj_konwersje_wydzialow\|import_jednostki_ipis" -- src/ docs/ | grep -v /migrations/`
  Expected: brak wywołań z kodu produkcyjnego (tylko definicje/docs). Jeśli coś jest — obsłuż.

- [ ] **Step 2: Test dla repointowanych komend** — dla `mapuj_kierunki_studiow`, `zaloz_jednostki_domyslne`, `prace_do_rozliczenia`: jeśli mają testy, przepisz fixtury `Wydzial` → root `Jednostka`. Jeśli nie mają — dodaj minimalny smoke (`call_command(...)` na fixture z rootem).

- [ ] **Step 3: RED** — `uv run pytest src/bpp/tests/test_management*/ -v` (odpowiednie moduły) → FAIL na starych fixturach.

- [ ] **Step 4: Usuń martwe komendy + przepnij żywe** wg listy Files. Dla `mapuj_kierunki_studiow`/`zaloz_jednostki_domyslne`/`prace_do_rozliczenia`: `Wydzial.objects.all()` → `Jednostka.objects.filter(parent__isnull=True)`; `Wydzial.objects.get(skrot=…)` → `Jednostka.objects.get(parent__isnull=True, skrot=…)`. Usuń importy `Wydzial`.

- [ ] **Step 5: GREEN** — `uv run pytest src/bpp/tests/test_management*/ src/bpp/tests/test_admin/ -v` → PASS.

- [ ] **Step 6: Commit**
```bash
git add -A
git commit -m "refactor(438-C): usuń martwe komendy konwersji, przepnij żywe komendy+admin na jednostki top-level"
```

---

## Sub-plan C-2 — Usunięcie read-only powierzchni Wydzial

### Task 5: Usuń API v1 `/api/v1/wydzial/`

**Files:**
- Modify: `src/api_v1/viewsets/struktura.py:6,8,16-18` (usuń import `Wydzial`, `WydzialSerializer`, klasę `WydzialViewSet`)
- Modify: `src/api_v1/serializers/struktura.py:3,23-29` (usuń import + `WydzialSerializer`). `JednostkaSerializer.wydzial` (:48-51,70) już wskazuje jednostka-detail — ZOSTAW; usuń komentarz „żyje do Fazy C" (:50).
- Modify: `src/api_v1/urls.py:23,100` (usuń import + `router.register(r"wydzial", …)`)
- Modify: `src/api_v1/views.py:95` (usuń `"wydzial"` z grupy `authors_and_units` w indeksie)
- Test: `src/api_v1/tests/` — znajdź test oczekujący `/api/v1/wydzial/` 200; zmień na 404.

- [ ] **Step 1: Test** — `GET /api/v1/wydzial/` → 404; `GET /api/v1/` (indeks) NIE zawiera klucza `wydzial`; `GET /api/v1/jednostka/<pk>/` nadal serializuje pole `wydzial` (root).
```python
@pytest.mark.django_db
def test_api_wydzial_usuniete(client):
    assert client.get("/api/v1/wydzial/").status_code == 404
```

- [ ] **Step 2: RED** — `uv run pytest src/api_v1/tests/ -v -k wydzial` → FAIL (endpoint jeszcze żyje).

- [ ] **Step 3: Usuń** wg Files.

- [ ] **Step 4: GREEN** — `uv run pytest src/api_v1/tests/ -v` → PASS.

- [ ] **Step 5: Commit**
```bash
git add src/api_v1/
git commit -m "feat(438-C)!: usuń /api/v1/wydzial/ (WydzialViewSet+Serializer) — koniec deprecacji"
```

### Task 6: Usuń autocomplete Wydzial

**Files:**
- Modify: `src/bpp/views/autocomplete/simple.py:23,201-217` (usuń import `Wydzial`, `WydzialAutocomplete`, `PublicWydzialAutocomplete`)
- Modify: `src/bpp/views/autocomplete/__init__.py:81,86` (usuń eksporty)
- Modify: `src/bpp/urls.py:51,61,371-373,386-388` (usuń importy + route `wydzial-autocomplete`, `public-wydzial-autocomplete`)
- Test: `src/bpp/tests/test_autocomplete*` — znajdź testy tych route'ów; usuń/zmień na 404.

- [ ] **Step 1: Grep konsumentów** URL-nazw:
  Run: `git grep -n "wydzial-autocomplete\|public-wydzial-autocomplete\|WydzialAutocomplete\|PublicWydzialAutocomplete" -- src/ templates/ | grep -v /migrations/`
  Expected: tylko definicje/rejestracje + ew. testy. Jeśli template/JS referuje — przepnij na `public-jednostka-...` (units.py) lub usuń.

- [ ] **Step 2: Test** — `reverse("...wydzial-autocomplete")` → `NoReverseMatch` (albo test na usunięcie route'u).

- [ ] **Step 3: RED → usuń → GREEN**
  Run: `uv run pytest src/bpp/tests/ -v -k autocomplete` → PASS po usunięciu.

- [ ] **Step 4: Commit**
```bash
git add src/bpp/views/autocomplete/ src/bpp/urls.py src/bpp/tests/
git commit -m "refactor(438-C): usuń WydzialAutocomplete/PublicWydzialAutocomplete + route'y"
```

### Task 7: Rozstrzygnij `browse_wydzial_redirect` (Opcja A — domyślna, patrz D1)

**Files:**
- Modify: `src/bpp/views/browse.py:34,43,146-169` (uprość funkcję; usuń import `Wydzial`)
- Modify: `src/bpp/urls.py:90,251-253` (route zostaje, cel bez zmian)
- Test: `src/bpp/tests/test_views/test_views_browse.py`

- [ ] **Step 1: Test** — `/wydzial/<slug>/` gdy istnieje `Jednostka` o tym slugu → 301 na `/jednostka/<slug>/`; gdy nie istnieje → 404.
```python
@pytest.mark.django_db
def test_browse_wydzial_redirect_po_slugu_jednostki(client, jednostka):
    r = client.get(f"/wydzial/{jednostka.slug}/")
    assert r.status_code == 301
    assert r.url == f"/jednostka/{jednostka.slug}/"

@pytest.mark.django_db
def test_browse_wydzial_redirect_404_gdy_brak(client):
    assert client.get("/wydzial/nie-ma-takiego/").status_code == 404
```

- [ ] **Step 2: RED** — `uv run pytest src/bpp/tests/test_views/test_views_browse.py -v -k redirect` → FAIL (funkcja importuje Wydzial).

- [ ] **Step 3: Uprość funkcję** — bez `Wydzial`/`legacy_wydzial_id`:
```python
def browse_wydzial_redirect(request, slug):
    """Legacy URL (`/wydzial/<slug>/`) → 301 na odpowiednik w drzewie ``Jednostka``.

    Faza C (#438): model ``Wydzial`` usunięty. Mapujemy 1:1 po slugu:
    promowane 1-jednostkowe wydziały mają root == realna jednostka (ten sam
    slug). Gdy slug nie odpowiada żadnej ``Jednostka`` → 404 (stare linki
    syntetycznych węzłów-luster z sufiksem nazwy nie mają odpowiednika).
    """
    get_object_or_404(Jednostka, slug=slug)
    return redirect("bpp:browse_jednostka", slug=slug, permanent=True)
```
   Usuń import `Wydzial` (`browse.py:34`).

- [ ] **Step 4: GREEN** — `uv run pytest src/bpp/tests/test_views/test_views_browse.py -v` → PASS.

- [ ] **Step 5: Commit**
```bash
git add src/bpp/views/browse.py src/bpp/tests/test_views/test_views_browse.py
git commit -m "refactor(438-C): browse_wydzial_redirect mapuje 1:1 po slugu jednostki (drop Wydzial)"
```

### Task 8: Usuń referencje w settings/dashboard/cacheops

**Files:**
- Modify: `src/django_bpp/settings/base.py:1413` (usuń `"bpp.Wydzial"` z listy modeli)
- Modify: `src/django_bpp/settings/production.py:109` (usuń wpis `"bpp.wydzial": {...}` cachalot/cacheops)
- Modify: `src/django_bpp/dashboard.py:46` (usuń `"bpp.models.wydzial"` z ModelList „Struktura")

- [ ] **Step 1: Grep** pozostałych literałów:
  Run: `git grep -in "bpp\.wydzial\|bpp\.models\.wydzial\|\"bpp.Wydzial\"" -- src/django_bpp/ | grep -v /migrations/`

- [ ] **Step 2: Usuń** wszystkie 3 wpisy.

- [ ] **Step 3: Weryfikacja** — `uv run python src/manage.py check` → 0 errors (dashboard nie próbuje zresolvować nieistniejącego modelu).

- [ ] **Step 4: Commit**
```bash
git add src/django_bpp/
git commit -m "chore(438-C): usuń referencje bpp.Wydzial z settings/dashboard/cacheops"
```

---

## Sub-plan C-3 — Drop modelu Wydzial

### Task 9: Usuń `struktura_konwersja.py` + model `Wydzial` + `DeleteModel`

**Files:**
- Delete: `src/bpp/models/struktura_konwersja.py` (fabryka lustra — martwa po Task 1-4; nic już jej nie woła)
- Delete: `src/bpp/models/wydzial.py` (klasa `Wydzial`, `JednostkaCreateManager`, 2 sygnały, helper)
- Modify: `src/bpp/models/struktura.py:14-18` (usuń `from .wydzial import (…)`)
- Modify: `src/bpp/models/jednostka.py:32` (usuń `from .wydzial import Wydzial`)
- Modify: `src/bpp/models/__init__.py` — sprawdź czy `Wydzial`/`JednostkaCreateManager`/`invalidate_uczelnia_cache_on_wydzial_change` są w `__all__`; usuń.
- Create: `src/bpp/migrations/0466_faza_c_drop_wydzial.py` (renumeruj wg aktualnego liścia!) — `migrations.DeleteModel("Wydzial")`.
- Test: `src/bpp/tests/test_models/` — dodaj `test_wydzial_usuniety.py`.

**Interfaces:**
- Consumes: wszystkie miejsca importujące `Wydzial` muszą być zdjęte (Task 1-8). Przed tym taskiem: `git grep -n "\bWydzial\b" -- src/ | grep -v /migrations/ | grep -v test` MUSI być pusty (poza tym plikiem).

- [ ] **Step 1: Grep-gate** — potwierdź brak żywych referencji:
  Run: `git grep -n "import Wydzial\|from bpp.models.wydzial\|Wydzial\.objects\|sender=Wydzial\|znajdz_lub_utworz_wezel_wydzialu\|struktura_konwersja" -- src/ | grep -v /migrations/`
  Expected: PUSTO (poza plikami, które ten task usuwa). Jeśli coś zostało — wróć do C-1/C-2.

- [ ] **Step 2: Test** — model nie istnieje w rejestrze:
```python
def test_model_wydzial_nie_istnieje():
    from django.apps import apps
    import pytest
    with pytest.raises(LookupError):
        apps.get_model("bpp", "Wydzial")
```

- [ ] **Step 3: RED** — `uv run pytest src/bpp/tests/test_models/test_wydzial_usuniety.py -v` → FAIL (model jeszcze jest).

- [ ] **Step 4: Usuń pliki + importy** wg Files. `struktura.py:14-18` i `jednostka.py:32` — skasuj importy. Sprawdź, że `sumy_views.py`/inne nie importują usuwanych symboli (grep w Step 1 to złapał).

- [ ] **Step 5: Migracja** — ustal liść:
  Run: `git fetch origin dev && ls src/bpp/migrations | grep -E '^0[0-9]{3}_' | sort | tail -3`
  Utwórz `0466_faza_c_drop_wydzial.py` (numer = liść+1), `dependencies` = ostatni liść bpp:
```python
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [("bpp", "0465_merge_20260707_0736")]  # aktualny liść
    operations = [migrations.DeleteModel(name="Wydzial")]
```

- [ ] **Step 6: GREEN + pełne migracje** — `uv run pytest src/bpp/tests/test_models/test_wydzial_usuniety.py -v` → PASS; potem `uv run python src/manage.py makemigrations --check --dry-run` → „No changes" (state zgodny); `uv run pytest src/bpp/tests/test_models/ -v`.

- [ ] **Step 7: Commit**
```bash
git add src/bpp/models/ src/bpp/migrations/0466_faza_c_drop_wydzial.py src/bpp/tests/test_models/test_wydzial_usuniety.py
git commit -m "feat(438-C)!: DROP model Wydzial + usuń struktura_konwersja (jedno drzewo Jednostka)"
```

---

## Sub-plan C-4 — Drop markerów konwersji

### Task 10: Drop `Jednostka.legacy_wydzial_id` (+ `jest_lustrem`)

**Files:**
- Modify: `src/bpp/models/jednostka.py:198-210` (usuń `legacy_wydzial_id` oraz `jest_lustrem` + komentarz `:199-207`)
- Modify: readery `legacy_wydzial_id` w `jednostka.py` (`:403,408,421,435-436,490,517` — metody `wydzial_dnia`/subtree; sprawdź, czy po dropie modelu jeszcze potrzebują pola — jeśli tylko odzyskiwały „stary Wydzial", usuń tę gałąź)
- Create: `src/bpp/migrations/0467_faza_c_drop_legacy_markery.py` — `RemoveField(legacy_wydzial_id)` + `RemoveField(jest_lustrem)`
- Test: `src/bpp/tests/test_models/test_jednostka_pola_faza_a.py:15,18` (asertuje pola — zmień na „pola nie istnieją")

**⚠ Uwaga:** `jest_lustrem` był używany WYŁĄCZNIE przez sygnał `usun_wezel_lustro_wydzialu` (usunięty w Task 9) i matchowanie (Task 1). Potwierdź grepem, że nikt go już nie czyta. Jeśli coś zostało — dodaj do zakresu.

- [ ] **Step 1: Grep-gate**:
  Run: `git grep -n "legacy_wydzial_id\|jest_lustrem" -- src/ | grep -v /migrations/ | grep -v /tests/`
  Expected: tylko definicja pola w `jednostka.py` + ew. metody `wydzial_dnia`. Obsłuż każdą.

- [ ] **Step 2: Przejrzyj `wydzial_dnia()` i subtree-helpery** (`jednostka.py:395-520`) — ustal, czy `legacy_wydzial_id` służy tam do czegoś poza odzyskiwaniem dawnego `Wydzial`. Po dropie modelu ta gałąź jest martwa → usuń, zostaw czystą logikę drzewa (`parent`/`get_root`).

- [ ] **Step 3: Test** — pola nie ma:
```python
def test_jednostka_bez_legacy_markerow():
    from bpp.models import Jednostka
    names = {f.name for f in Jednostka._meta.get_fields()}
    assert "legacy_wydzial_id" not in names
    assert "jest_lustrem" not in names
```

- [ ] **Step 4: RED** → usuń pola + readery + migracja (renumeruj!) → **GREEN**:
```python
class Migration(migrations.Migration):
    dependencies = [("bpp", "0466_faza_c_drop_wydzial")]
    operations = [
        migrations.RemoveField("jednostka", "legacy_wydzial_id"),
        migrations.RemoveField("jednostka", "jest_lustrem"),
    ]
```
  Run: `uv run pytest src/bpp/tests/test_models/ -v` + `makemigrations --check --dry-run` → „No changes".

- [ ] **Step 5: Commit**
```bash
git add src/bpp/models/jednostka.py src/bpp/migrations/0467_faza_c_drop_legacy_markery.py src/bpp/tests/
git commit -m "feat(438-C): drop legacy_wydzial_id + jest_lustrem (markery konwersji Fazy B)"
```

---

## Sub-plan C-5 — Higiena danych

### Task 11: Wyczyść osierocone `ContentType`/`Permission` po Wydzial

**Files:**
- Create: `src/bpp/migrations/0468_faza_c_czysc_contenttype_wydzial.py` — RunPython (idempotent, reversible=noop)
- Test: `src/bpp/tests/test_migrations/test_0468_czysc_ct.py`

- [ ] **Step 1: Test** — po migracji brak `ContentType(app_label="bpp", model="wydzial")` i skojarzonych `Permission`.
```python
@pytest.mark.django_db
def test_brak_contenttype_wydzial():
    from django.contrib.contenttypes.models import ContentType
    assert not ContentType.objects.filter(app_label="bpp", model="wydzial").exists()
```

- [ ] **Step 2: RunPython** — usuń CT + kaskadowo Permission (Permission FK→CT CASCADE, ale usuń jawnie dla pewności):
```python
def czysc(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    ct = ContentType.objects.filter(app_label="bpp", model="wydzial")
    Permission.objects.filter(content_type__in=ct).delete()
    ct.delete()

class Migration(migrations.Migration):
    dependencies = [("bpp", "0467_faza_c_drop_legacy_markery"),
                    ("contenttypes", "0001_initial"), ("auth", "0001_initial")]
    operations = [migrations.RunPython(czysc, migrations.RunPython.noop)]
```
   Uwaga: `system.py` NIE ma `Wydzial` w grupach (sprawdzone) → grupy bez zmian; `Obslugujacy_Zgloszenia_Wydzialow` ZOSTAJE.

- [ ] **Step 3: GREEN** — `uv run pytest src/bpp/tests/test_migrations/test_0468_czysc_ct.py -v` → PASS.

- [ ] **Step 4: Commit**
```bash
git add src/bpp/migrations/0468_faza_c_czysc_contenttype_wydzial.py src/bpp/tests/test_migrations/
git commit -m "chore(438-C): wyczyść osierocone ContentType/Permission po modelu Wydzial"
```

---

## Sub-plan C-6 — Audit flagi/labela (uzywaj_wydzialow ZOSTAJE)

### Task 12: Audit konfigurowalnego labela poziomu top-level

**Kontekst:** Sprzeczność w specu ROZSTRZYGNIĘTA: sekcje „Fazy wdrożenia"/„Świadomie odłożone" mówią „usunięcie `uzywaj_wydzialow`", ale changelog decyzji (runda 3+4, autorytet) + plan mówią **flaga ZOSTAJE**. Faza C **NIE usuwa** `uzywaj_wydzialow`. Ten task to wyłącznie **audit** (dokumentacja + ew. drobny label), nie refaktor.

**Files:**
- Inspect: `src/bpp/models/uczelnia.py:631` (`uzywaj_wydzialow`), `src/bpp/models/jednostka.py:233` (`SKROT_WYDZIALU_W_NAZWIE`), miejsca renderujące label „Wydział" w UI (browse/menu/multiseek).
- Doc: `docs/superpowers/specs/2026-07-02-...-design.md` — dopisz notę, że sprzeczność rozstrzygnięta na korzyść „flaga zostaje".

- [ ] **Step 1: Zbierz** wszystkie hardkody stringa „Wydział"/„wydziały" w UI, które przy `uzywaj_wydzialow=True` powinny być konfigurowalne (audytowa lista, bez zmiany kodu). Zapisz w `docs/superpowers/2026-07-07-audit-label-toplevel.md`.

- [ ] **Step 2: Rekomendacja** w tym dokumencie: czy wprowadzać `Uczelnia.label_poziomu_toplevel` (CharField default „Wydział") — to osobny, przyszły temat (YAGNI teraz). Faza C tylko dokumentuje.

- [ ] **Step 3: Commit**
```bash
git add docs/superpowers/
git commit -m "docs(438-C): audit labela poziomu top-level + rozstrzygnięcie sprzeczności uzywaj_wydzialow"
```

---

## Sub-plan C-7 — Infrastruktura

### Task 13: baseline-update + rebuild cache + pełna suita

- [ ] **Step 1: Pełna suita bez playwright**
  Run: `make tests-without-playwright`
  Expected: zielono.

- [ ] **Step 2: Baseline update** (delta nowych migracji 0466-0468):
  Run: `make baseline-update`
  Commituj OBA: `baseline-sql/baseline.sql` + `baseline-sql/baseline.meta.json`.

- [ ] **Step 3: Rebuild cache/denorm** — jeśli drop pól ruszył denorm/cachalot: `uv run python src/manage.py denorm_rebuild` (jeśli dotyczy) + invalidacja cache.

- [ ] **Step 4: Reszta suite** — `make tests-only-playwright` + `make js-tests` (dokończ, nie pomijaj).

- [ ] **Step 5: Commit + push + PR**
```bash
git add baseline-sql/
git commit -m "chore(438-C): baseline-update po drop Wydzial + markery (0466-0468)"
git push -u origin feat/438-faza-C
gh pr create --base dev --title "feat(#438): Faza C — drop modelu Wydzial + sprzątanie" --body "..."
```

---

## Appendix — decyzje zamknięte

### Task R1 — SKREŚLONY (D2=nie)
Rename `Jednostka.wydzial` → `jednostka_toplevel` **nie jest robiony** w Fazie C. Pole zostaje pod nazwą `wydzial`.

### Task R2 — won't-do (D3=odłożone)
Rename `Jednostka` → `JednostkaOrganizacyjna` odłożony, poza zakresem Fazy C.

---

## Self-review (writing-plans)

- **Pokrycie zakresu Fazy C (spec §294-296 + user):** drop `Wydzial` (T9) ✓, drop `legacy_wydzial_id` (T10) ✓, twarde usunięcie `/api/v1/wydzial/` (T5) ✓, autocomplete (T6) ✓, browse redirect (T7) ✓, ContentType/Permission (T11) ✓, `uzywaj_wydzialow` audit (ZOSTAJE, T12) ✓, rename `wydzial`→`jednostka_toplevel` SKREŚLONY (D2=nie), rebuild cache + baseline (T13) ✓. Follow-upy PR#446 (F6 sufiks `[W<id>]`, F7 ranking, cache/rekord.py:275) — NIE w tym planie (data-dependent / osobne); dopisać jeśli user chce.
- **Ordering:** funkcjonalne repointy (C-1) PRZED usuwaniem powierzchni (C-2) PRZED `DeleteModel` (C-3) PRZED drop pól (C-4) — bo grep-gate w T9/T10 wymaga zera żywych referencji. ✓
- **Pułapka `filter(pk)`:** repointy podające instancję modelu (T1,T2,T4) mają test-inwariant + są atomowe (jeden commit). ✓
- **Migracje:** renumeracja `git fetch origin dev` przed KAŻDYM taskiem migracyjnym (T9,T10,T11,T13). Liść na dziś: `0465_merge_20260707_0736`; Phase C = 0466-0468. ✓
- **Placeholdery:** load-bearing taski (T1,T2,T7,T9,T10,T11) mają realny kod; mechaniczne usunięcia (T5,T6,T8) mają dokładne lokalizacje + test. T3,T4 mają krok „przeczytaj X" tam, gdzie ciało helpera trzeba dopracować przy wykonaniu (orchestrator demo-data, ciała komend). ✓
- **Decyzje ROZSTRZYGNIĘTE (2026-07-07):** D1=Opcja A (redirect po slugu jednostki), D2=NIE (pole `wydzial` bez renamu, R1 skreślony), D3=odłożone (R2 won't-do).
