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

1. **Multi-tenant: jedyny kontrakt to `Uczelnia.objects.get_for_request(request)`.**
   Budujemy M2M `raport ↔ uczelnia` + poziom dostępu + grupy. „Bieżącą uczelnię"
   bierzemy **wyłącznie** z `Uczelnia.objects.get_for_request(request)` i wg tego
   obiektu filtrujemy/sprawdzamy widoczność. **Jak `get_for_request` rozwiązuje
   tenanta (Site, domena, cokolwiek) — NIE jest przedmiotem tej zmiany.** Nie
   ruszamy `SITE_ID`, `Site.objects`, cache'a uczelni ani niczego z tym
   związanego. Traktujemy `get_for_request` jak czarną skrzynkę zwracającą
   `Uczelnia` (lub `None`).
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
  renderuje (z eksportem docx/xlsx jak dziś). **Domyka zaległy bug 500**: gdy
  `report` jest pusty/None, `?_export=docx|xlsx` nie woła `as_*_response(None)`
  tylko zwraca komunikat (jak temat 1), zamiast 500.

Dotychczasowe URL-e per-poziom zastąpione, ale **stare nazwy URL** (`autor_form`,
`jednostka_form`, `wydzial_form`, `uczelnia_form` + `*_generuj`) **zostają jako
aliasy** kierujące na nowe trasy `…/<slug>/…` dla 4 domyślnych raportów —
kompatybilność istniejących linków/zakładek (zatwierdzone).

### Integracja z `django-formdefaults` (kluczowe)

Obecne formularze raportów używają `FormDefaultsMixin` i mają być nadal na
formdefaults. **Pułapka:** formdefaults kluczuje zapisane domyślne wartości po
`FormRepresentation.full_name = "{module}.{ClassName}"` (primary key, **bez
hooka do override**). Jeden wspólny generyczny form class → wszystkie definicje
**współdzieliłyby jeden rekord defaultów** (kolizja).

Rozwiązanie: **dynamiczna klasa formularza per definicja** — fabryka
`form_class_dla(definicja)` zwraca podklasę bazowego formularza ze **stabilnym**
`__name__`/`__module__` wyprowadzonym ze sluga (np. `RaportForm_<slug>` w
`nowe_raporty.forms_dynamiczne`), więc `full_name` jest unikalny i deterministyczny
per definicja → **osobne defaulty per raport**. Generyczny `RaportFormView`
buduje tę klasę dla danego sluga, a `post_migrate` hook (`apps.create_entries`)
**iteruje po `DefinicjaRaportu`** i rejestruje `FormRepresentation` dla każdej
(zamiast dzisiejszej pętli po 4 zahardkodowanych view-ach). Kolejność na
`post_migrate`: seed tworzy `DefinicjaRaportu` (i `Report`) → potem rejestracja
formdefaults per definicja.

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
  aktywnych `DefinicjaRaportu`, filtrowaną per-request metodą `widoczny_dla`
  (która woła `get_for_request(request)` — czarna skrzynka).
- **Własny** cache listy definicji (odrębny klucz, NIE `bpp_uczelnia`) trzyma
  odchudzoną reprezentację (slug, nazwa, poziom, poziom_dostepu, id grup, id
  uczelni, kolejnosc) — by filtr `widoczny_dla` leciał w Pythonie bez N zapytań.
  Lista zależy tylko od `DefinicjaRaportu`, więc **inwalidacja na
  `post_save`/`m2m_changed` `DefinicjaRaportu`** (cache'a `bpp_uczelnia` nie
  ruszamy).
- Szablon renderuje płaską listę `<li>` posortowaną wg `kolejnosc`.

## Migracja z `Uczelnia.pokazuj_raport_*` — PŁYNNE PRZEJŚCIE (twardy wymóg)

Wymóg: **żadnego okna ze zmienioną/zepsutą widocznością raportów.** Po
deployu istniejące raporty mają być widoczne dla dokładnie tych samych
użytkowników co przed. Realizujemy to uporządkowaną sekwencją migracji w
**jednym** PR:

1. **Migracja schematu A** — dodaj model `DefinicjaRaportu` (+ M2M). Pola
   `Uczelnia.pokazuj_raport_*` jeszcze **istnieją**.
2. **Data migration B** — dla każdego z 4 istniejących `flexible_reports.Report`
   (po slugu) utwórz `DefinicjaRaportu` przepisując uprawnienia 1:1 z
   `Uczelnia.pokazuj_raport_<x>`:
   - `always`    → `poziom_dostepu = WSZYSCY`,
   - `logged-in` → `ZALOGOWANI` + `wymagane_grupy = {GR_RAPORTY_WYSWIETLANIE}`
     (dokładnie dzisiejsza semantyka `_sprawdz_uprawnienie_zalogowany`),
   - `staff`     → `STAFF`,
   - `never`     → `aktywny = False`,
   - `uczelnie` = puste (= wszędzie); `poziom`/`nazwa`/`slug` z mapowania.
   Wartości czyta z **pierwszej/jedynej** uczelni (`get_default`) — tak jak dziś
   działa widoczność.
3. **Przełączenie call-site'ów** — menu (`top_bar.html`) i dispatch widoków
   przechodzą na `DefinicjaRaportu.widoczny_dla`. Dopiero teraz przestają
   zależeć od `pokazuj_raport_*`.
4. **Migracja schematu C** — usuń 4 pola `pokazuj_raport_*` z `Uczelnia`.
   `czy_pokazywac` / `UczelniaSettingRequiredMixin` / inne flagi `pokazuj_*`
   (ranking, raport slotów itd.) **zostają** — usuwamy tylko 4 flagi raportów.

**Test parytetu** (gwarancja płynności): dla każdej wartości
`OpcjaWyswietlaniaField` × (anon / zalogowany-bez-grupy / zalogowany-w-grupie /
staff / superuser) — `DefinicjaRaportu.widoczny_dla` po migracji daje **ten sam**
wynik co dawne `Uczelnia.sprawdz_uprawnienie` przed migracją.

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

- **Rozpoznawanie tenanta** (jak `get_for_request` mapuje request→`Uczelnia`,
  Site/domena itd.) — załatwia samo `get_for_request`; my tylko je wołamy.
- „Klonuj tabelę" (parking).
- Przeprojektowanie datasource'ów „karm przefiltrowaną listą" (parking).

## Decyzje zatwierdzone (były „otwarte")

- Opcje zaawansowane (4 powyższe) — **OK**.
- Mapowanie uprawnień przy migracji — **OK**.
- Stare URL-e — **aliasować** do nowych `…/<slug>/`.
- Pola `pokazuj_raport_*` — usunąć, ale z **gwarancją płynnego przejścia**
  (sekwencja migracji + test parytetu powyżej).
- **Bug 500 w eksporcie** (zaległość tematu 1) — **domknąć** w nowym
  `RaportGenerujView`.
- **Dostarczenie:** jeden PR, 5 commitów (etap = commit).
- **Domyślna kolejność menu** 4 raportów: uczelnia → wydział → jednostka →
  autor (`kolejnosc` 0/1/2/3), jak w dzisiejszym `top_bar.html`.

## Etapowanie implementacji (TDD, przyrostowo na tej gałęzi)

Slice B+C jest duży — proponuję 5 etapów, każdy z testami i osobnym commitem:

1. **Model + `widoczny_dla`** (`DefinicjaRaportu`, migracja schematu A) + testy
   uprawnień (poziomy, grupy AND, superuser, aktywny, M2M uczelnie).
2. **Płynne przejście**: data migration B (mapowanie z `pokazuj_raport_*`) +
   **test parytetu** + przełączenie call-site'ów + migracja C (usunięcie pól).
3. **Generyczne widoki/formularz/URL** + rejestr `POZIOMY` + opcje zaawansowane
   + **formdefaults per-definicja** (dynamiczne klasy) + aliasy starych URL.
4. **Data-driven płaskie menu** + własny cache + inwalidacja.
5. **Reconciliation ze slice A**: rozszerzenie `seed_default_reports()` o
   `DefinicjaRaportu` + `post_migrate` rejestracja formdefaults per definicja.

## Ryzyka / uwagi (self-review)

- **Płynne przejście to najczulszy punkt.** Mitygacja: kolejność migracji A→B→
  przełączenie→C w jednym PR + test parytetu. Połowiczny deploy (np. B bez C)
  nie psuje widoczności, bo do kroku 3 menu nadal czyta stare flagi.
- **`get_for_request` jako czarna skrzynka.** Dopóki nie jest „host-aware",
  scoping `uczelnie` M2M działa efektywnie single-tenant (jedna uczelnia z
  `get_default`). To OK i zgodne z założeniem — nic po naszej stronie.
- **formdefaults wymaga dynamicznych klas** (`type()` ze stabilnym `__name__`
  ze sluga) — jedyna droga, bo formdefaults kluczuje po `full_name` bez hooka.
  Ryzyko: slug ze znakami spoza identyfikatora → sanityzować do `[A-Za-z0-9_]`.
- **`get_for_request` jest wołane szeroko** w całym bpp — sama nasza zmiana go
  nie modyfikuje, ale pełny suite (nie tylko `nowe_raporty`) trzeba przepuścić.
- **`report` FK = `PROTECT`** — usunięcie `flexible_reports.Report` używanego
  przez definicję jest blokowane (świadome).
- **Rozmiar PR.** Decyzja: jeden PR, 5 commitów (etap = commit) — spójność
  płynnego przejścia trzymana w jednym miejscu. Review przyrostowo per commit.
- **Usunięcie pól `pokazuj_raport_*`** z `Uczelnia` teraz, czy deprecate-then-
  remove w osobnym kroku.
