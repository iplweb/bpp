# Konfigurowalne raporty: model `DefinicjaRaportu` + uprawnienia (slice B + C)

Data: 2026-05-31
Status: do recenzji użytkownika
Branch: `feat/nowe-raporty-konfigurowalne` (stackowany na
`feat/nowe-raporty-seed-domyslnych` / slice A)

## Problem

Dziś są **4 zahardkodowane** raporty (autor/jednostka/wydział/uczelnia): każdy
ma własny `*FormView` + `*Form` + mixin auth + URL pattern + `report_slug` w
`src/nowe_raporty/views.py`. Lista jest **kodem, nie danymi** — nie da się dodać
drugiego raportu dla autora bez pisania kodu. Uprawnienia siedzą na obiekcie
`Uczelnia` (`pokazuj_raport_autorow/jednostek/wydzialow/uczelni` +
`OpcjaWyswietlaniaField` + grupa `GR_RAPORTY_WYSWIETLANIE`), więc są
jedno-uczelniane i wspólne dla wszystkich raportów danego typu.

## Cel

- **Kilka raportów na każdym poziomie** (uczelnia/wydział/jednostka/autor),
  definiowalnych z admina. Każda definicja ma nazwę, slug, poziom i wskazuje
  na definicję `flexible_reports.Report` (swój template/schemat).
- **Uprawnienia per raport** (slice C): wyciągnięte z `Uczelnia` na nową
  definicję; poziom dostępu + wymagane grupy + (multi-tenant-ready) lista
  uczelni, na których raport się pokazuje.
- **Data-driven menu** (płaska lista) + widoki/formularze/URL generyczne.

## Decyzje (zatwierdzone w brainstormingu)

1. **Multi-tenant: tylko model gotowy-pod-multitenant.** Budujemy M2M
   `raport ↔ uczelnia` + poziom dostępu + grupy. „Bieżąca uczelnia" nadal przez
   istniejące `Uczelnia.objects.get_for_request` (dziś `first()`). Rozpoznawanie
   tenanta per-request (middleware/domena) — POZA zakresem, później.
2. **Uprawnienia = dwa wymiary.** Poziom dostępu (wszyscy / zalogowani / staff /
   superuser) ORAZ opcjonalny zbiór grup jako **AND** (member którejkolwiek =
   OR wewnątrz zbioru). Superuser zawsze przechodzi (poza filtrem uczelni).
3. **Menu: płaska lista** wszystkich widocznych raportów pod „raporty".
4. **Opcje formularza:** obecne (zakres lat, „tylko afiliowane") + 3-4
   zaawansowane, **schowane domyślnie** (propozycja niżej). Rozszerzalne w kodzie.

## Model danych

Nowy model BPP `DefinicjaRaportu` (`src/nowe_raporty/models.py`):

```python
class DefinicjaRaportu(models.Model):
    POZIOM_UCZELNIA = "uczelnia"
    POZIOM_WYDZIAL = "wydzial"
    POZIOM_JEDNOSTKA = "jednostka"
    POZIOM_AUTOR = "autor"
    POZIOM_CHOICES = [...]  # 4 poziomy

    # dostep
    DOSTEP_WSZYSCY = "wszyscy"        # także anonim
    DOSTEP_ZALOGOWANI = "zalogowani"
    DOSTEP_STAFF = "staff"            # is_staff (edytujący)
    DOSTEP_SUPERUSER = "superuser"
    DOSTEP_CHOICES = [...]

    nazwa = CharField(max_length=200)          # etykieta w menu
    slug = SlugField(unique=True)              # URL + tożsamość
    poziom = CharField(choices=POZIOM_CHOICES)
    report = ForeignKey("flexible_reports.Report", PROTECT)  # template/schemat
    kolejnosc = PositiveIntegerField(default=0)  # porządek w menu
    aktywny = BooleanField(default=True)         # zastępuje "nigdy"

    # uprawnienia (slice C)
    poziom_dostepu = CharField(choices=DOSTEP_CHOICES, default=DOSTEP_ZALOGOWANI)
    wymagane_grupy = ManyToManyField(Group, blank=True)
    uczelnie = ManyToManyField("bpp.Uczelnia", blank=True)  # puste = WSZĘDZIE

    class Meta:
        ordering = ["kolejnosc", "nazwa"]
```

`report` jako FK (`PROTECT`) — wiele definicji może wskazywać na różne
`Report`-y; usunięcie `Report` używanego przez definicję jest blokowane.

### Sprawdzanie widoczności

Metoda `DefinicjaRaportu.widoczny_dla(request)` (jedno źródło prawdy dla menu
i dla dispatcha widoku):

```
nieaktywny                      -> False
uczelnie ustawione i biezaca-uczelnia not in uczelnie  -> False   (także superuser)
superuser                       -> True   (pomija poziom dostepu i grupy)
poziom_dostepu:
    WSZYSCY     -> tier_ok = True
    ZALOGOWANI  -> tier_ok = user.is_authenticated
    STAFF       -> tier_ok = user.is_staff
    SUPERUSER   -> tier_ok = user.is_superuser
tier nie-ok                     -> False
wymagane_grupy ustawione:
    user nie zalogowany         -> False
    user nie ma żadnej z grup   -> False
True
```

„Bieżąca uczelnia" = `Uczelnia.objects.get_for_request(request)` (dziś jedna).
Filtr `uczelnie` jest więc zapisywany i honorowany od razu; pełnego sensu nabiera
gdy dojdzie rozpoznawanie tenanta.

## Poziomy — rejestr w kodzie

`get_base_queryset` per poziom NIE da się zapisać jako dana (to logika ORM —
patrz slice A: pinowanie roli autora na wierszu autorstwa). Zostaje w kodzie
jako rejestr `POZIOMY` w `src/nowe_raporty/poziomy.py`:

```python
POZIOMY = {
    "autor":     PoziomConfig(model=Autor,     ma_pk_w_url=True,  base_queryset=...),
    "jednostka": PoziomConfig(model=Jednostka, ma_pk_w_url=True,  base_queryset=...),
    "wydzial":   PoziomConfig(model=Wydzial,   ma_pk_w_url=True,  base_queryset=...),
    "uczelnia":  PoziomConfig(model=Uczelnia,  ma_pk_w_url=False, base_queryset=...),
}
```

Każdy `PoziomConfig` niesie: model obiektu, czy URL ma `pk` (uczelnia nie ma),
funkcję `base_queryset(obiekt, tylko_afiliowane)` (dzisiejsze
`prace_autora`/`prace_jednostki`/`prace_wydzialu`/`all`+`afiliuje`), oraz pole
wyboru obiektu do formularza. **To jest jedyna część „raportu", która zostaje
kodem; reszta (które raporty, ich nazwa/slug/template/uprawnienia) staje się
danymi.**

## Widoki / formularze / URL (generyczne)

Zamiast 4× `*FormView` + `*Generuj` — **jedna para** generycznych widoków
parametryzowana `slug`-iem definicji:

- `RaportFormView` — `…/nowe_raporty/<slug>/` — ładuje `DefinicjaRaportu` po
  slug (404 → komunikat z tematu 1 gdy `report` pusty), buduje formularz wg
  `poziom`, sprawdza `widoczny_dla` (inaczej `handle_no_permission`).
- `RaportGenerujView` —
  `…/nowe_raporty/<slug>/<obj_pk>/<od>/<do>/` (autor/jednostka/wydział) lub
  `…/nowe_raporty/<slug>/<od>/<do>/` (uczelnia, bez pk) — pobiera obiekt,
  woła `base_queryset` z rejestru, ustawia `report.set_base_queryset(...)`,
  renderuje (z eksportem docx/xlsx jak dziś).

Dotychczasowe URL-e per-poziom zastąpione; stare nazwy (`autor_form` itd.)
można zachować jako aliasy do nowych slugów dla kompatybilności linków
(do decyzji — patrz „Otwarte").

### Formularz: wybór obiektu + zakres lat + opcje zaawansowane

- **Wybór obiektu** wg poziomu (autocomplete jak dziś). **Gdy w systemie jest
  dokładnie jeden obiekt danego poziomu** (np. jedna uczelnia, jeden wydział,
  jedna jednostka) → ustawiony jako `initial` (domyślny). Autor zwykle wielu →
  bez domyślnego.
- **Zakres lat** (`od_roku`/`do_roku`) + **`_export`** jak dziś.
- **„Tylko prace afiliowane"** — zostaje (góra formularza).
- **Opcje zaawansowane** (Fieldset „Opcje zaawansowane", **collapsed na
  dzień dobry**) — propozycja, filtrują bazowy queryset `Rekord` (czyli cały
  raport, przed datasource'ami):
  1. **Zakres punktów MNiSW** (`punkty_kbn` od–do),
  2. **Zakres Impact Factor** (`impact_factor` od–do),
  3. **Zakres punktacji wewnętrznej** (`punktacja_wewnetrzna` od–do) —
     pokazywane tylko gdy `uczelnia.pokazuj_punktacje_wewnetrzna`,
  4. **„Tylko prace punktowane"** (`punkty_kbn > 0`) — checkbox.

  Filtry stosowane w `RaportGenerujView` do bazowego querysetu przed
  `set_base_queryset`. Zestaw pól zdefiniowany w kodzie (łatwo dołożyć kolejne);
  ewentualne włączanie per-definicja z admina — później.

## Menu (data-driven, płaskie)

`top_bar.html` dziś ma zahardkodowane `<li>` per raport bramkowane
`{% czy_pokazywac raport_X %}`. Zastępujemy **pętlą** po widocznych definicjach:

- Nowy context processor `raporty_menu(request)` (lub template tag) zwraca listę
  aktywnych `DefinicjaRaportu` **z cache** (globalny, jak `bpp_uczelnia`),
  filtrowaną per-request metodą `widoczny_dla` (filtr w Pythonie — tani, bez
  N zapytań, bo cache trzyma odchudzoną reprezentację: slug, nazwa, poziom,
  poziom_dostepu, id grup, id uczelni, kolejnosc).
- **Inwalidacja cache** na `post_save`/`m2m_changed` `DefinicjaRaportu` oraz na
  `post_save` `Uczelnia` (dziś już inwaliduje `bpp_uczelnia`).
- Szablon renderuje płaską listę `<li>` posortowaną wg `kolejnosc`.

## Migracja z `Uczelnia.pokazuj_raport_*`

1. **Data migration** (`nowe_raporty`): dla każdego z 4 istniejących
   `flexible_reports.Report` (po slugu) utwórz `DefinicjaRaportu`:
   - `poziom` z mapowania slug→poziom,
   - `report` = FK,
   - `nazwa`/`slug`/`kolejnosc` sensownie (np. nazwa = title raportu),
   - `poziom_dostepu` + `wymagane_grupy` z **mapowania** obecnej flagi
     `Uczelnia.pokazuj_raport_<x>`:
     - `always`    → `WSZYSCY`,
     - `logged-in` → `ZALOGOWANI` + grupa `GR_RAPORTY_WYSWIETLANIE`
       (zachowuje dzisiejsze zachowanie),
     - `staff`     → `STAFF`,
     - `never`     → `aktywny = False`,
   - `uczelnie` = puste (= wszędzie).
2. **Usunięcie pól** `pokazuj_raport_*` z `Uczelnia` (osobna migracja) +
   aktualizacja call-site'ów: `top_bar.html`, `czy_pokazywac`,
   `UczelniaSettingRequiredMixin`/`sprawdz_uprawnienie` (raporty przestają z nich
   korzystać; mixin zostaje dla innych stron, które używają innych flag).

## Reconciliation ze slice A (seed)

Slice A seeduje `flexible_reports.Report` (template/schemat). Slice B dokłada
`DefinicjaRaportu`. Aby goły serwer miał też **wpisy menu**:

- Rozszerzyć `seed_default_reports()` (slice A) o idempotentne tworzenie
  `DefinicjaRaportu` dla 4 domyślnych (po slug, create-if-absent, nie nadpisuje).
- Na świeżej bazie: `post_migrate` → seed tworzy `Report` + `DefinicjaRaportu`.
  Na istniejącej: data migration tworzy `DefinicjaRaportu` z mapowanymi
  uprawnieniami. Oba idempotentne, zbieżne (create-if-absent po slug).

## Testy (TDD, pytest, testcontainers)

- **Model `widoczny_dla`**: każdy poziom dostępu (anon/zalogowany/staff/
  superuser), grupy jako AND (brak grupy → ukryty; member jednej z → widoczny),
  superuser bypass, `aktywny=False` → ukryty, `uczelnie` (puste = wszędzie;
  ustawione = tylko te; obca uczelnia → ukryty także dla superusera).
- **Kilka raportów na poziom**: 2 definicje `autor` → obie w menu i routowalne.
- **Generyczny widok**: formularz wg poziomu; jedyny obiekt → domyślny;
  opcje zaawansowane filtrują queryset (np. `punkty_kbn` od–do zawęża wynik);
  render 200; eksport docx/xlsx.
- **Menu**: lista data-driven, filtrowana per-request; inwalidacja cache na
  zapis definicji.
- **Migracja**: 4 istniejące → `DefinicjaRaportu` z poprawnie zmapowanymi
  uprawnieniami; pola `pokazuj_raport_*` znikają z `Uczelnia`.
- **Integracja**: temat 1 (brak `report` → komunikat) nadal działa dla
  definicji bez wypełnionego `Report`.

## Poza zakresem

- Rozpoznawanie tenanta per-request (middleware/domena) — przyszłość.
- „Klonuj tabelę" (parking).
- Przeprojektowanie datasource'ów „karm przefiltrowaną listą" (parking).
- Bug 500 w eksporcie przy braku `Report` — można domknąć opcjonalnie przy
  okazji generycznego widoku (do decyzji).

## Otwarte do weryfikacji przez użytkownika

- **Zestaw opcji zaawansowanych** (4 powyższe) — czy pasują, czy coś dodać/ująć.
- **Mapowanie uprawnień przy migracji** (zwł. `logged-in` → `ZALOGOWANI` +
  grupa `GR_RAPORTY_WYSWIETLANIE`).
- **Stare URL-e** (`autor_form` itd.) — aliasować do nowych slugów czy zostawić
  tylko nowe `…/<slug>/`?
- **Usunięcie pól `pokazuj_raport_*`** z `Uczelnia` teraz, czy deprecate-then-
  remove w osobnym kroku.
