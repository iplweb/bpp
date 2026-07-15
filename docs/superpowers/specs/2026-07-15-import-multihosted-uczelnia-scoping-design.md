# Import pracowników i jednostek — twarde ograniczenie do bieżącej uczelni (multi-hosted)

Data: 2026-07-15
Moduł: `src/import_pracownikow/`
Status: zaakceptowany design → plan implementacji

## Cel

Na instalacjach multi-hosted import pracowników i jednostek ma **zawsze**
działać w zakresie uczelni bieżącego requestu (host → Site → Uczelnia), a
schematy mapowania kolumn mają być pamiętane/proponowane **per-uczelnia**.

Dwa wymagania użytkownika:

1. **Scoping do bieżącej uczelni.** Lista importów, wszystkie ekrany
   pojedynczego importu oraz pobierania plików widzą wyłącznie importy
   należące do uczelni z requestu. Import z innej uczelni jest niewidoczny —
   **dla każdego, także superusera**.
2. **Bramka „brak uczelni".** Gdy request nie ustala uczelni
   (`Uczelnia.objects.get_for_request(request) is None`), wejście na
   jakikolwiek URL importu → redirect na stronę główną + `messages.error`.
   Dotyczy wszystkich, także superusera.
3. **Profile mapowania per-uczelnia.** „Ostatnio użyty" / auto-dopasowany
   `ProfilMapowania` bierze pod uwagę wyłącznie profile bieżącej uczelni —
   zero przecieku między uczelniami.

Menu (`top_bar.html`) **zostaje bez zmian** — link jest zawsze widoczny.
Egzekwowanie jest wyłącznie na poziomie widoku: kto wejdzie bez uczelni,
dostaje redirect. Ukrywanie linku odpalałoby się tylko w tym samym edge'u,
który i tak łapie bramka w widoku, a `uczelnia.pk` w normalnej pracy jest
zawsze ustawione (kod to zakłada) — więc menu-hiding byłby martwym UI.

## Stan obecny (co już działa)

- `ImportPracownikow.uczelnia` (FK, null=True; migracja 0026) — łapana z
  requestu w `NowyImportView.form_valid` (`get_for_request`).
- `uczelnia_do_integracji()` = `self.uczelnia` albo fallback
  `get_single_uczelnia_or_none()` (single-tenant / stare importy).
- Pipeline w tle (analiza + integracja) już zawęża pule jednostek do
  `uczelnia_do_integracji()` (commit `f8e7f7004`).
- Wszystkie widoki są za `GroupRequiredMixin` (grupa „wprowadzanie danych",
  superuser-exempt) i owner-scoped (`owner=self.request.user`), a
  `ImportPracownikowResultsView` dodatkowo zwalnia superusera z owner-check.

Czego brakuje: warstwy **dostępu/scopingu w widokach** (bramka „brak
uczelni" + filtrowanie do bieżącej uczelni) oraz **per-uczelnia** dla
`ProfilMapowania` (dziś globalny: `nazwa` unique w całej instancji, brak FK
`uczelnia`, `dopasuj_profil`/`wybierz_profil_fallback` skanują `.all()`).

## Architektura

### 1. View-mixin jako bramka i scoping (`views.py`)

Nowy `WymagajUczelniZRequestuMixin`:

```python
class WymagajUczelniZRequestuMixin:
    @cached_property
    def uczelnia_biezaca(self):
        from bpp.models import Uczelnia
        return Uczelnia.objects.get_for_request(self.request)

    def dispatch(self, request, *args, **kwargs):
        if self.uczelnia_biezaca is None:
            messages.error(
                request,
                "Nie ustalono uczelni dla tej domeny — import pracowników i "
                "jednostek jest niedostępny.",
            )
            return redirect("root")  # strona główna BPP (django_bpp.urls: name="root")
        return super().dispatch(request, *args, **kwargs)

    def sprawdz_uczelnie(self, obj):
        if obj.uczelnia_do_integracji() != self.uczelnia_biezaca:
            raise Http404
```

Kolejność baz (MRO): `GroupRequiredMixin, WymagajUczelniZRequestuMixin,
<widok generyczny>` — najpierw auth/grupa (anonim → login, brak grupy →
403), potem bramka uczelni. Dzięki temu bramka uczelni działa też dla
superusera, ale nie przechwytuje anonima przed loginem.

**Dwa różne tryby odmowy (celowo):**

- **brak uczelni w ogóle** (`uczelnia_biezaca is None`) → redirect na home +
  komunikat. Realne przyczyny: multi-hosted i domena bez mapowania
  Site→Uczelnia; 0 uczelni (pusty setup).
- **uczelnia jest, ale obiekt należy do innej** → `Http404` (spójne z
  istniejącym owner-scopingiem przez `get_object_or_404`).

`sprawdz_uczelnie` używa `obj.uczelnia_do_integracji()` (a nie surowego
`obj.uczelnia`), więc semantyka jest identyczna jak w tle:
- single-tenant: `uczelnia_do_integracji()` = jedyna uczelnia = `biezaca`
  (także dla legacy `NULL` — fallback). Zawsze match.
- multi-tenant: `obj.uczelnia` ustawione → porównanie wprost; legacy `NULL`
  → fallback `get_single_uczelnia_or_none()` = `None` (bo >1) → `None !=
  biezaca` → 404 (poprawnie ukryte).

### 2. Manager-owe filtrowanie zbiorów

`ImportPracownikow.objects.widoczne_dla_uczelni(u)` oraz
`ProfilMapowania.objects.dla_uczelni(u)` — jeden wzorzec, ORM-owy odpowiednik
`uczelnia_do_integracji`:

```python
def widoczne_dla_uczelni(self, uczelnia):
    from bpp.models import Uczelnia
    if Uczelnia.objects.exclude(pk=uczelnia.pk).exists():
        # multi-tenant — ściśle
        return self.filter(uczelnia=uczelnia)
    # single-tenant — bieżąca albo legacy NULL
    return self.filter(Q(uczelnia=uczelnia) | Q(uczelnia__isnull=True))
```

### 3. Punkty wpięcia w widokach

Do wszystkich klas dołożyć `WymagajUczelniZRequestuMixin` (bezpośrednio lub
przez wewnętrzne `_ImportPodgladMixin` / `_WierszImportuMixin` /
`_PkOwnerRestartMixin`):

- `ListaImportowView.get_queryset` →
  `ImportPracownikow.objects.widoczne_dla_uczelni(self.uczelnia_biezaca)
  .filter(owner=self.request.user)` (owner-scoping bez zmian).
- `NowyImportView.form_valid` → `self.object.uczelnia = self.uczelnia_biezaca`
  (bramka gwarantuje non-None; efekt jak dziś).
- `MapowanieView.object`, `ImportPracownikowResultsView.parent_object`,
  `_PkOwnerRestartMixin.get_object`, `PodgladImportuView`, `OdpieciaView`,
  `LogZmianView`, `Weryfikacja*View`, `PobierzOryginalView`,
  `PobierzPoImporcieView`, HTMX-owe akcje wiersza → po fetchu wołają
  `self.sprawdz_uczelnie(obj)`. W results view superuser nadal przekracza
  ownera, ale **nie** uczelnię.

### 4. Profile mapowania per-uczelnia

Model `ProfilMapowania`:
- + FK `uczelnia` (`on_delete=CASCADE`, `null=True` dla back-compat).
- `nazwa` traci `unique=True`; dochodzi `Meta.unique_together = (("uczelnia",
  "nazwa"),)` — ta sama nazwa profilu dozwolona na różnych uczelniach.
- manager `dla_uczelni(u)` (jak wyżej).

`mapping.py`:
- `dopasuj_profil(naglowki, uczelnia)` — baza `ProfilMapowania.objects
  .dla_uczelni(uczelnia)` zamiast `.all()`.
- `wybierz_profil_fallback(naglowki, uczelnia, prog=0.5)` — filtr po
  `dla_uczelni(uczelnia)` przed `order_by("-ostatnio_uzyty")`.

`views.py` (`MapowanieView`):
- `get_form_kwargs` przekazuje `self.uczelnia_biezaca` do obu funkcji.
- zapis profilu: `ProfilMapowania.objects.update_or_create(uczelnia=
  self.uczelnia_biezaca, nazwa=…, defaults=…)`.
- stempel `ostatnio_uzyty` na `profil_zastosowany` bez zmian (profil już
  jest w zakresie uczelni, bo tylko takie oferujemy).

### 5. Migracja `import_pracownikow/0027`

Jeden plik, kolejność operacji:
1. `AddField` `ProfilMapowania.uczelnia` (null=True).
2. `RunPython` **backfill**: jeżeli w systemie jest dokładnie jedna
   `Uczelnia`, ustaw ją na wszystkich `NULL`-owych `ProfilMapowania` **oraz**
   `ImportPracownikow`. Dzięki temu na single-tenant ścisłe filtrowanie
   niczego nie ukrywa. (reverse: no-op.)
3. `AlterField` `ProfilMapowania.nazwa` — usuń `unique=True`.
4. `AlterUniqueTogether` `ProfilMapowania` → `{("uczelnia", "nazwa")}`.

Backfill nie rusza instalacji z 0 lub >1 uczelniami (tam wiersze są albo
nowe i już ostemplowane, albo brak jednoznacznej uczelni).

### 6. Baseline

`make baseline-update` — **dopiero przy scalaniu do `dev`**, nie w tej
gałęzi (reguła: baseline nie odświeżamy w równoległych branchach).

## Testy

Rozszerzenie `tests/test_views_uczelnia.py` + testy profili:

- Bramka: >1 uczelnia, host bez mapowania → lista / „nowy" / URL obiektu →
  redirect na home + komunikat; **superuser też** zablokowany.
- Scoping listy: multi-tenant pokazuje tylko importy bieżącej uczelni;
  single-tenant widzi także legacy `NULL`.
- Obiekt z innej uczelni → 404 (także superuser w `ResultsView`).
- Profile: profil uczelni B nie jest proponowany ani „ostatnio użyty" dla
  uczelni A; ta sama `nazwa` zapisywalna na dwóch uczelniach (unique_together);
  `update_or_create` stempluje `uczelnia`.
- Backfill: single-tenant → `NULL`-owe `ProfilMapowania` i `ImportPracownikow`
  dostają jedyną uczelnię.

Uruchamiane lokalnie (`uv run pytest src/import_pracownikow/tests/ -n auto`,
output do pliku i grep) — zgodnie z regułami repo.

## Newsfragment

`src/bpp/newsfragments/import-uczelnia-scoping.bugfix.rst` — domknięcie multi-hosted:
import pracowników/jednostek i profile mapowania działają ściśle w zakresie
uczelni bieżącej domeny.

## Poza zakresem (YAGNI)

- Ukrywanie linku w menu (menu zostaje).
- Profile współdzielone/globalne (`uczelnia=NULL` widoczne wszędzie) —
  odrzucone; profile są ściśle per-uczelnia.
- Zmiana owner-scopingu (per-user) — zostaje jak jest, dokładamy tylko
  warstwę uczelni.
- Zmiany w pipeline w tle — już zawęża pule do `uczelnia_do_integracji()`.
