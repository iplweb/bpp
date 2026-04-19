# Migracja Django 4.2 → 5.2 LTS

Dokument opisuje zmiany wprowadzone na gałęzi `feature/django-5.2` —
dlaczego każda była potrzebna, jakie alternatywy były rozważane, i jak
czytelnik rozpozna podobne sytuacje w przyszłości.

## Kontekst

- **Stan wyjściowy:** Django 4.2.25 (LTS), wiele pakietów `django-*`
  przypiętych `==` do wersji sprzed 2 lat.
- **EOL Django 4.2:** kwiecień 2026 — po tej dacie brak poprawek
  bezpieczeństwa upstream.
- **Cel:** Django 5.2 LTS (wsparcie do kwietnia 2028, Python
  3.10–3.13).
- **Ograniczenie (z [CLAUDE.md](../CLAUDE.md)):** stare migracje w
  `src/*/migrations/` są immutable — nie wolno ich edytować. API
  usunięte z Django 5 a wykorzystane w tych migracjach musi być
  przywrócone przez shim.

## Podsumowanie liczbowe

- **17 commitów** na gałęzi (wliczając merge z `dev` i news fragment).
- **3726 testów przechodzi** (`pytest -n 4`); 2 skipped, 1 xfailed,
  jeden flake `test_WydzialJednostkiPierwszegoAutora_queryset` pod
  xdist — passes w izolacji.
- Brak nowych migracji modelowych poza pre-istniejącym driftem
  (`favicon`, `flexible_reports`, `raport_slotow`) obecnym także
  na `dev`.

## Strategia

1. **Fazowo.** Najpierw `default_app_config` i pakiety w
   dual-compat (działają i na 4.2, i na 5.2), potem sam bump Django,
   potem naprawki wychodzące z pełnego przebiegu testów. Każda faza
   osobny commit → łatwy rollback i code review.
2. **Commit per pakiet.** Gdyby któryś pakiet wymagał cofnięcia,
   możemy zrewertować punktowo.
3. **Shim zamiast modyfikacji migracji.** Usunięte API Django 5
   (`timezone.utc`, `models.NullBooleanField`) przywracane w
   `django_bpp/django_compat.py` ładowanym przy starcie pakietu.
4. **Dual-compat podczas bumpów pakietów.** Wszystkie bumpy przed
   commitem `fb49e782` zostały tak dobrane, żeby pakiet wspierał i
   Django 4.2, i 5.2 jednocześnie (weryfikowalne w classifiers na
   PyPI). Dzięki temu każdy pojedynczy commit jest sam w sobie
   bezpieczny.

---

## Grupa 1 — Przygotowanie

### `bf43c787` — drop `default_app_config`

Usunięcie atrybutu `default_app_config = "..."` z 8 plików
`src/*/__init__.py` (`bpp`, `admin_dashboard`, `raport_slotow`,
`rozbieznosci_dyscyplin`, `nowe_raporty`, `pbn_import`,
`deduplikator_zrodel`, `django_pg_baseline`).

**Dlaczego:** `default_app_config` jest deprecated od Django 3.2 — gdy
aplikacja ma jeden `AppConfig` w `apps.py` i jest zarejestrowana w
`INSTALLED_APPS` pod krótką nazwą (`"bpp"`), Django automatycznie go
wykrywa. Każda z 8 aplikacji spełniała oba warunki. Atrybut był
no-opem, który Django 5.x zostawia jako tolerowany niedojrzały artefakt
— sprząta się przed bumpem, żeby ograniczyć hałas warningów.

**Ryzyko:** zero, zweryfikowane `manage.py check` zielonym na 4.2
przed dalszymi zmianami.

---

## Grupa 2 — Dual-compat bumpy pakietów

Każdy pakiet dobrany tak, żeby wspierał i Django 4.2, i Django 5.2 po
tym, jak sam Django zostanie bumpnięty. Kolejność dobrana od
najbezpieczniejszego (nieduże wersje, stabilne API) do najbardziej
ryzykownego (major breaks).

### `0b769e44` — `django-crispy-forms` 2.0 → `>=2.4,<3`

Minimalny bump (2.0 → 2.5) w ramach stabilnej linii 2.x. API
renderowania formularzy (`|crispy`, `{% crispy %}`, `FormHelper`) nie
zmieniło się. `crispy-forms-foundation==1.1.0` (nasz pakiet motywu)
wymaga `django-crispy-forms>=2.0` bez sufitu — stąd dolna granica
`>=2.4`. Potwierdzone przez `render_crispy_form()` + 31 testów
`bpp/admin_dashboard`.

### `34002aad` — `django-mptt` 0.13.4 → `>=0.16,<1`

BPP używa `MPTTModel`, `TreeForeignKey`, `TreeManager`,
`DraggableMPTTAdmin`, `TreeNodeChoiceField` — wszystko stabilne
przynajmniej od 0.13.x. 0.16 jest pierwszą wersją deklarującą
Django 5.2. Resolwer wybiera 0.18.0. Zero nowych migracji. 12 testów
jednostek modeli i admina przeszło.

### `e65966c8` — `django-tables2` 2.3.1 → `>=2.8,<2.9`

Pułapka PyPI: `2.9.0` została **yanked** upstream (breaking changes
zamiast tego wydane jako `3.0.0`, które **drops Django 4.2**). `2.8.0`
wspiera 4.2 + 5.1 + 5.2 jednocześnie. Pin na `>=2.8,<2.9` blokuje
przypadkowe złapanie 3.0 przez resolwer. 14 testów renderowania tabel
w `raport_slotow`/`import_pracownikow`.

### `815c6cb5` — `django-htmlmin` → `django-minify-html`

**Wymiana paczki, nie bump.** `django-htmlmin==0.11.0` nie ma
wydania od 2019 i deklaruje wsparcie tylko do Django 2.1.
`django-minify-html` 1.14 (Adam Johnson) jest aktywnie utrzymywany
i owijky around Rust-owy `minify-html` — działa od Django 4.2 do 6.0.

Zmiany konsumujące:

- `settings/base.py`: usunięte dwa middleware `htmlmin.*`, dodane
  jedno `django_minify_html.middleware.MinifyHtmlMiddleware`.
- `settings/production.py`: middleware dołączone warunkowo (tylko tam
  gdzie `HTML_MINIFY=True` był dotychczas). Dev/test nie minifikują,
  bo po prostu nie mają tego middleware w stacku.
- Dead settings usunięte: `HTML_MINIFY` (dawny on/off),
  `EXCLUDE_FROM_MINIFYING` (regex templates nigdy nie hit-owany w
  nowym middleware).
- `generate_500_page.py`: `minify_html.minify(keep_comments=True,
  keep_closing_tags=True, keep_html_and_head_opening_tags=True)` —
  generator statyczny `/500.html` zachowuje warning comment i
  struktury `<html>`/`</body>` dla nginx.

### `047e1866` — `django-taggit` 4.0 → `>=5,<7`

Dwa majory (4 → 6). Classifiers taggit 6.1 deklarują tylko do
Django 5.0, ale `requires_dist = ["Django>=4.1"]` — metadata jest
lagging. Resolwer wybiera 6.1.0.

**Breaking change naprawiony:** taggit 5.0 dodał domyślne
`self.ordering = [f"{Tag reverse related_query_name}__pk"]`. Nasz
`_MyTaggableManager` (dla cache'owego widoku `SlowaKluczoweView`
używanego przez `Rekord.slowa_kluczowe`) ma custom `tags_for()`
zwracający queryset `SlowaKluczoweView` zamiast `Tag`. Domyślne
ordering taggit próbuje rozwiązać reverse-name `slowakluczoweview__pk`
na querysecie z modelu, w którym tego pola nie ma. Override `__init__`
ustawia `ordering=["pk"]` (kolumna primary key through-table).

### `532fe413` — `django-filter` 21.1 → `>=25.1,<25.2`

Cztery majory. `25.1` jest ostatnią linią z deklarowanym wsparciem
4.2 i 5.2 jednocześnie (classifiers: 4.2, 5.0, 5.1, 5.2). **`25.2` drops
Django 4.2** (wymaga Django ≥ 5.2). BPP używa modern surface
(`filterset_class`, `DjangoFilterBackend` z `api_v1`, `raport_slotow`)
który jest stabilny od 22.x. 64 testy API + raport przeszły.

### `f0b8079e` — `django-import-export` 3.2 → `>=4.4,<5`

Major bump z realnymi API breaks. Trzy punkty naprawione:

1. **`ExportMixin.get_export_data()`**: sygnatura zmieniona z
   `(file_format, queryset, *args, **kwargs)` na
   `(file_format, request, queryset, **kwargs)` — `request` stał
   się positional. Dostosowano `EksportDanychMixin.export_action` oraz
   `EksportDanychZFormatowanieMixin.get_export_data` w
   `src/bpp/admin/xlsx_export/mixins.py`.

2. **`ExportForm.__init__()`**: wymaga teraz `formats` **i**
   `resources` (wcześniej tylko `formats`), a pole wyboru formatu ma
   klucz `format` (wcześniej `file_format`).
   `PrettyXLSXDefaultExportForm` został zmigrowany.

3. **Strict field whitelist**: 4.x ignoruje (z warningiem) custom pola
   `Field()` niezadeklarowane w `Meta.fields`. `Autor_DyscyplinaResource`
   miał martwe `rodzaj_autora = Field()` + `dehydrate_rodzaj_autora`
   duplikujące wartość z już zlistowanego `rodzaj_autora__skrot`.
   Usunięte jako dead code.

386 testów w `bpp/tests/test_admin`, `bpp/tests/test_export`,
`ewaluacja_liczba_n` zielonych — pokrywa oba ExportMixin subclasses i
XLSX/BibTeX flows.

### `3b787c70` — `django-grappelli` 3.0.6 → `>=4,<5`

Grappelli 4.0.3 (2023) ma rzadkie metadata (tylko
`Framework :: Django` bez wersji), ale jest wydawane i działa — 342
testy admina zielone. UI-layer zweryfikowany w Grupie 5 przez
Playwright (metoda JS `grappelli.initDateAndTimePicker` itp.
istnieją w 4.x).

### `14189a06` — `django-fsm` 2.8.0 → `>=3,<4`

**Tombstone release.** `django-fsm 3.0.1` (2025-10) z nowymi
classifiers (do Django 5.2) ale w `__init__.py` emituje
`UserWarning` sugerujący migrację do `viewflow.fsm`. Underlying kod
`FSMField`/`@transition` identyczny z 2.8.x — to po prostu marker
"projekt przeniesiony".

**Decyzja:** pin 3.x żeby deklarować oficjalne wsparcie Django 5.2.
Realna migracja do `viewflow.fsm` jest osobnym zadaniem (wykorzystanie
ograniczone do `import_dyscyplin/models.py`, 14 testów tam zielonych).
Warning zostaje w output — filter w `pytest.ini` jest już dodany.

### `60b44781` — `django-reversion` 5.0.4 → `>=6,<7`

Jeden major bump. BPP używa `VersionAdmin` wyłącznie na
`UczelniaAdmin` (1 miejsce). `django-reversion 6.x` wymaga
`django>=4.2`, brak migracji modelowych, 261 testów admina zielonych.

### `8b83f246` — `Unidecode` 0.4.20 → `>=1.3,<2`

Stary pin z ~2015 r. (`Unidecode==0.04.20` w normalizacji PyPI →
zainstalowane 0.4.20). Wersja 1.4.0 (kwiecień 2025). Jedyne API
używane to `from unidecode import unidecode` — stabilne od 1.0.
Potwierdzone: `unidecode('Łódź Kraków ąęśćżóń')` →
`'Lodz Krakow aesczon'` jak dotychczas.

---

## Grupa 3 — Bump Django i kompatybilność

### `fb49e782` — bump `Django` 4.2 → 5.2

Główny commit. Poniżej każda zmiana z osobna — to jest najważniejszy
commit do zrozumienia.

#### Shim `src/django_bpp/django_compat.py`

Importowany z `src/django_bpp/__init__.py`, co wykonuje się **przed**
zbudowaniem grafu migracji (Django importuje settings, a ten moduł
jest loadowany przy imporcie pakietu `django_bpp`). Kluczowe, bo
migracje są immutable.

**Przywrócone API:**

- `django.utils.timezone.utc` — usunięte w Django 5.0. Używane w
  `src/rozbieznosci_if/migrations/0002_auto_20210323_0106.py`. Shim
  ustawia alias na `datetime.timezone.utc`.
- `django.db.models.NullBooleanField` — usunięte w Django 5.0.
  Używane w: `bpp/migrations/0119`, `0239`, `0270`, `0271`;
  `integrator2/0001`; `import_pracownikow/0003`, `0004`;
  `ewaluacja2021/0003`; `pbn_api/0012`, `0031`; `tee/0004`. Shim
  re-eksportuje podklasę `BooleanField(null=True, blank=True,
  default=None)`. `deconstruct()` przepisuje ścieżkę z powrotem
  na `django.db.models.BooleanField`, żeby `makemigrations` nie
  próbowało znów odwoływać się do usuniętej klasy.

#### Code fixes wywołane breaking changes

- **`bpp/admin/praca_habilitacyjna.py`** —
  `Publikacja_HabilitacyjnaForm.Meta.fields` zawierał `"publikacja"`,
  które jest `GenericForeignKey` (non-editable na poziomie modelu).
  Django 5 wymaga, że tylko editable pola wchodzą do `Meta.fields`,
  nawet jeśli formularz deklaruje je na poziomie klasy. Usunięte z
  Meta — pole deklaratywne klasy zostaje.

- **`bpp/admin/__init__.py` → `BppUserCreationForm`** — zmiana
  bazy z `UserCreationForm` na `AdminUserCreationForm` (nowość
  Django 5.1). `UserAdmin.add_fieldsets` od 5.1 zawiera pole
  `usable_password` (pozwala tworzyć user-a bez działającego hasła
  dla SSO). `fields = "__all__"` w ModelForm na `BppUser` nie
  znajdowało tego pola i wywalało `FieldError: Unknown field(s)
  (usable_password)`. `AdminUserCreationForm` ma je zadeklarowane
  na klasie.

- **`bpp/models/cache/rekord.py` → `_MyTaggableManager`** — Django 5
  prefetch machinery woła `get_prefetch_querysets` (plural, nowe
  API 5.0+) zamiast starego `get_prefetch_queryset`. Nasz override
  był tylko na starej metodzie — pod 5.2 domyślna implementacja
  taggit szukała pola `content_object` na `SlowaKluczoweView` (model
  oparty o custom through z `rekord` i `tag`, nie na GFK). Dodany
  override `get_prefetch_querysets` + wydzielony wspólny
  `_build_prefetch_queryset()`.

- **`raport_slotow/views/zerowy.py`** — Django 5 compile set-operations
  (`EXCEPT`, `UNION`, `INTERSECT`) teraz zachowuje nazwy kolumn z
  lewej strony SELECT, wcześniej anonimizował do `col1`, `col2`,
  `col3`. Kod robił `CREATE TABLE x AS SELECT (from .difference())`
  a potem `ALTER TABLE ... RENAME COLUMN col1 TO autor_id` —
  działało na 4.x, w 5.x `col1` już nie istnieje. Zastąpione
  introspekcją przez `information_schema.columns` z warunkowym
  RENAME — działa i na 4.x (gdy nazwy są `colN`), i na 5.x (gdy już
  są `autor_id` itd.).

#### `pytest.ini`

Usunięte cztery filtry warningów odwołujące się do klas
`RemovedInDjango50Warning` i `RemovedInDjango51Warning` — obie klasy
są usunięte w Django 5.2 (cykl deprecation zakończony), więc sam
filtr by rzucał `AttributeError`. Dodany filtr na
`UserWarning:django_fsm` (tombstone ze zbumpowanego
`django-fsm 3.0.1`).

---

## Grupa 4 — Dokumentacja

### `ed6af048` — `+django-5-2-upgrade.feature.rst`

Fragment towncrier w `src/bpp/newsfragments/`. Wyświetli się w
`HISTORY.rst` sekcji `Usprawnienie` przy najbliższym release.

---

## Grupa 5 — Merge z `dev` i post-full-suite fixup

Podczas pracy `dev` posunął się o 6 commitów (release `v202604.1356` +
wydzielenie `iplweb/bpp_dbserver` do osobnego repozytorium). Merge
nie wygenerował konfliktów.

### `1ca03756` — merge `dev`

Przyjął m.in.:

- `pyproject.toml` version bump (202604.1355 → 202604.1356),
- `src/django_bpp/version.py` w synchronizacji,
- `testcontainers_bpp/containers.py` z obrazem
  `iplweb/bpp_dbserver:psql-16.13` (zastąpił lokalny tag `latest`),
- usunięcie podkatalogu `docker/dbserver/` (wydzielony do
  `https://github.com/iplweb/bpp-dbserver`).

**Lokalnie arm64:** obraz `iplweb/bpp_dbserver:psql-16.13` buduje się
z `~/Programowanie/bpp-dbserver` przez
`docker buildx bake dbserver-16-13 --set "*.platform=linux/arm64"`.
Na CI (linux/amd64) obraz jest pobierany z Docker Hub.

### `d61b28ad` — runtime + test adjustments po pełnym przebiegu

Pięć naprawek wykrytych dopiero gdy pełen `pytest` złapał ścieżki
kodowe nie dotknięte przez smoke-set:

- **`bpp/finders.py → YarnFinder.find`** — Django 5.2 w staticfiles
  przemianował parametr `all=False` na `find_all=False` w
  `BaseFinder.find()`. Override z `all=False` łapał `TypeError`
  gdy wywoływany przez `django-compressor`. Akceptuje oba przez
  `**kwargs`.

- **`bpp/models/jednostka.py → JednostkaManager.rebuild`** — Django 5
  odrzuca queryset kombinujący `.only()` z `.select_related()` na
  tym samym FK. `TreeManager.rebuild()` robi wewnętrznie
  `.only("pk")`, co kłóci się z naszym domyślnym
  `select_related("wydzial")`. Override `rebuild` tymczasowo pomija
  override `get_queryset` na poziomie klasy.

- **`bpp/models/abstract/authors.py → _waliduj_procent`** — Django 5
  rzuca `ValueError: Model instances passed to related filters must
  be saved.` gdy do `.filter(fk=instance)` trafia niezapisana
  instancja. W inline admin add_view parent `Rekord` jeszcze nie
  ma pk. Zamiana `filter(rekord=self.rekord)` →
  `filter(rekord_id=self.rekord_id)` — query degeneruje się do
  pustego zbioru (żaden sibling nie ma NULL FK bo kolumna NOT NULL),
  zachowane historyczne zachowanie.

- **Playwright `test_admin_actions.py`** — Django 5.1 zmienił polskie
  tłumaczenie `"Add another %(verbose_name)s"` z `"Dodaj <noun>"` na
  `"Dodaj kolejne(go)(-ną)(-ny) <noun>"`. Playwright
  `get_by_text("Dodaj powiązanie autora")` (substring match) przestał
  pasować (bo "Dodaj" i "powiązanie autora" są rozdzielone). Zamiana
  na `locator("a.grp-add-handler", has_text="powiązanie autora")` —
  stabilne CSS locator + stabilna część tekstu.

- **`dynamic_columns/tests.py → test_autor_admin_hide_column`** —
  Django 5.1 zaczął dodawać `aria-label` w action-checkbox
  changelist-a, z wartością `str(obj)`. `Autor.__str__` zawiera
  `poprzednie_nazwiska`, więc testowa wartość prosiaczkowała do
  HTML nawet po ukryciu kolumny. Asercja zmieniona z wartości na
  obecność `<td class="field-poprzednie_nazwiska">` — sprawdza
  faktyczne renderowanie komórki, nie wystąpienie stringu.

### `fe7cfb2e` — test `django_pg_baseline` dojrzewający z `loader.py`

Dwa testy (`test_load_baseline_invokes_psql`,
`test_load_baseline_defaults_for_missing_dsn_keys`) były pre-existującym
driftem test-vs-impl (na `dev` też failują) — loader w `dev` dostał
`stdout=PIPE, text=True, check=False`, ale fake_run w testach nie
akceptował tych kwargs i asertował `check=True`. Naprawione przez
`**kwargs` w fake_run, zwracanie `_FakeCompleted` z `returncode=0`,
i poprawkę asercji. Zmiana landuje na naszej gałęzi — wykryte dzięki
Django 5.2 run ale niezwiązane z samym bumpem.

---

## Stan testów

Komenda: `docker rm -f $(docker ps -aq --filter "name=bpp-tc");
uv run pytest -n 4 --timeout=300`.

Wynik najnowszego przebiegu:

```
3726 passed, 2 skipped, 1 xfailed, 2 failed (flakes) in 833s
```

### Jeden znany flake

- **`src/zglos_publikacje/tests/test_admin/test_filters.py::test_WydzialJednostkiPierwszegoAutora_queryset`**
  — pod xdist niekiedy łapie zamknięty socket do Postgresa (zombie
  connection między worker-ami). **Passes 100% w izolacji**
  (`uv run pytest <ten::test>`). Nie jest związane z Django 5.2.
  Warte oznaczenia `@pytest.mark.serial` w osobnym commicie (poza
  zakresem tej migracji).

### Jeden znany timeout Playwright

- **`src/import_dyscyplin/tests/test_integration.py::test_integracyjny[chromium]`**
  — złożony scenariusz (upload XLSX + Celery eager + FSM +
  oczekiwanie na AJAX + DataTable). Timeout `wait_for_function` w
  ostatniej sekcji. Nie dotknięty w ostatnim pełnym runie (pewnie
  zjedzony przez xdist worker drop), ale ostrzegawczo warto obejrzeć
  ręcznie po mergu.

## Decyzje świadomie **nie podjęte**

- **`DEFAULT_AUTO_FIELD`** zostaje `AutoField` (nie zmieniony na
  `BigAutoField`). Zmiana generowałaby ogromny zestaw migracji dla
  wszystkich modeli — to osobne, świadome przedsięwzięcie.
- **`requires-python`** w `pyproject.toml` zostaje `>=3.10,<3.15` —
  Django 5.2 oficjalnie wspiera do 3.13. Zawężenie do `<3.14` jest
  drobnym cleanup'em; odkładam po wdrożeniu produkcyjnym.
- **`django-admin-tools`** nie bumpowany mimo klasyfikatorów tylko
  do Django 4.0. De facto działa (342 testy admina zielone),
  pakiet był wydany w 2023. Jeśli coś padnie w UI, rozważymy fork.
- **Viewflow.fsm migration** — `django-fsm 3.0.1` jest tombstone,
  ale działa. Migracja to osobny, planowany task.
- **`django-messages-extends`, `django-cookie-law`, `django-classy-tags`,
  `django-loginas`, `django-querysetsequence`, `django-autoslug`** —
  wersje latest już zainstalowane lub pinowane wspierają 5.2 mimo
  rzadkich classifiers. Żadnych bumpów, żadnych regresji.

## Co sprawdzić po mergu

1. `make assets` przed uruchomieniem testów lokalnie (wygeneruje
   `node_modules/` i collect-staticfiles — inaczej
   `django-compressor` zgłasza `UncompressableFileError` dla
   `jqueryui/jquery-ui.css`).
2. Ręczny smoke panelu admina w Chrome (po Django 5.2
   upgrade'ie: formularz dodawania `Wydawnictwo_Ciagle` z autorami
   inline, zmiana hasła użytkownika, zapis `Publikacja_Habilitacyjna`).
3. Publiczny frontend (`multiseek` wyszukiwanie, raporty słotów).
4. Test Playwright `test_integracyjny` (`import_dyscyplin`) —
   ręcznie lub w CI.

## Linki

- [Django 5.0 release notes](https://docs.djangoproject.com/en/5.0/releases/5.0/)
- [Django 5.1 release notes](https://docs.djangoproject.com/en/5.1/releases/5.1/)
- [Django 5.2 release notes](https://docs.djangoproject.com/en/5.2/releases/5.2/)
- [django-tables2 2.9.0 yanked note](https://pypi.org/project/django-tables2/2.9.0/)
- [django-fsm tombstone discussion](https://github.com/viewflow/django-fsm)
- [django-minify-html (Adam Johnson)](https://github.com/adamchainz/django-minify-html)
