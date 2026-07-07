# Specyfikacja: konsolidacja Wydział → Jednostka (jedno drzewo struktury)

**Data:** 2026-07-02 (przepisane na czysto 2026-07-04 po 3 rundach rewizji)
**Status:** finalny projekt — do wykonania wg planu
`docs/superpowers/plans/2026-07-04-konsolidacja-faza-B.md`
**Issue:** [#438](https://github.com/iplweb/bpp/issues/438)

> Ten dokument opisuje **projekt** (co i dlaczego). Dokładna kolejność kroków i
> migracji jest w PLANIE (link wyżej) — on jest autorytetem wykonania. Historia
> decyzji (v1 → 3 rundy) jest w changelogu na końcu.

## Cel

Zlikwidować podział na dwa osobne modele `Wydzial` i `Jednostka`. Docelowo jedna
drzewiasta struktura MPTT `Jednostka`: na górze `Uczelnia`, pod nią jednostki
dowolnie zagnieżdżone. **„Wydział" przestaje być osobnym bytem** — to po prostu
**jednostka na szczycie drzewa** (root, bez rodzica). Wydział z etykietą „Wydział
Lekarski" staje się jednostką-korzeniem, a jego dawne jednostki wiszą pod nią.

Nie jest to destrukcyjne usunięcie danych, lecz **konwersja**: każdy wiersz
`Wydzial` staje się jednostką-korzeniem, wszystko co wskazywało na `Wydzial`
zostaje przepięte. Model `Wydzial` usuwany dopiero na końcu (Faza C), gdy nic go
nie referuje.

## Zasady niepodważalne (ustalone z użytkownikiem)

1. **Historia temporalna zostaje w całości** — jednostki historyczne, przypisania
   `od`/`do`, brak nakładania zakresów.
2. **„Wydział" to jednostka top-level, nie osobna rola.** Instalacja bez wydziałów
   (`Uczelnia → Jednostka`) jest w pełni wspierana i różni się od „z wydziałami"
   tylko liczbą pięter drzewa. **Nie istnieje marker roli ani flaga «poziomu
   wydziałowego».** (Pole `Jednostka.wydzial` istnieje, ale to zdenormalizowany
   wskaźnik POZYCJI w drzewie — korzeń — a nie marker roli; patrz Sekcja 1.)
3. **Triggery bazodanowe znikają (jest ich TRZY).** `0056` instaluje, `0440`
   przepisuje na plpgsql trzy obiekty dotykające `wydzial`:
   `bpp_jednostka_ustaw_wydzial_aktualna` (derywacja `aktualna` — zastąpiony
   Pythonem), `bpp_jednostka_sprawdz_uczelnia_id` i
   `bpp_jednostka_wydzial_sprawdz_uczelnia_id` (walidacja uczelni — **USUWANE bez
   zamiennika**, federacja). DROP musi nastąpić PRZED konwersją historii.
4. **Federacja: uczelnia NIE jest granicą nieprzekraczalną.** Jednostka może w
   czasie przechodzić między uczelniami. **Brak constraintu „uczelnia rodzica ==
   uczelnia dziecka"** — ani trigger, ani CHECK, ani `clean()`.

---

## Sekcja 1 — Model danych

### Strategia scalenia

**Absorpcja in-place.** Zachowujemy tożsamość dzisiejszej `Jednostka` (jej PK-e i
wszystkie przychodzące FK-e nietknięte). Wiersze `Wydzial` wmigrowujemy jako nowe
jednostki-korzenie; repointujemy tylko ~5 konsumentów `Wydzial`, nie konsumentów
`Jednostka`. Nazwa modelu zostaje `Jednostka`.

### `Jednostka.wydzial` — zdenormalizowany wskaźnik KORZENIA (zostaje)

**Kluczowa decyzja (runda 3):** pole `wydzial` NIE jest usuwane. Zmienia
znaczenie: z „najbliższy wydział" (FK→`Wydzial`) na **„korzeń mojego drzewa"
(self-FK→`Jednostka`, NULL dla jednostek top-level)**.

```python
@denormalized(models.ForeignKey, "self", null=True, blank=True,
              on_delete=models.SET_NULL, related_name="+")
@depend_on_related("self", "parent", only=("wydzial_id",))
def wydzial(self):
    if self.parent_id is None:
        return None                            # top-level → NULL
    return self.parent.wydzial or self.parent  # korzeń drzewa
```

- Utrzymywane przez `django-denorm-iplweb` — kaskada tranzytywna: zmiana
  `parent`/`wydzial` u węzła przelicza dzieci → wnuki (jak
  `wydawnictwo_zwarte.opis_bibliograficzny_cache` z
  `@depend_on_related("self","wydawnictwo_nadrzedne")`). `deconstruct()` zamraża
  w migracji zwykły self-FK → kolumna jest queryowalna i `select_related`-owalna.
- **Dlaczego zostaje:** prawie cały kod czytający `jednostka.wydzial` działa dalej
  (teraz na końcu siedzi jednostka-korzeń zamiast `Wydzial`); zapytania
  `filter(jednostka__wydzial=root)`, `select_related("wydzial")`, `__str__`,
  bibtex, admin, cache — bez zmian. Znika `RemoveField`, znika N+1 (property by go
  miało), znika masowy refactor raportów na `get_descendants`.
- **Cena (zaakceptowana):** przy przesunięciu węzła w drzewie denorm przelicza
  korzeń dla poddrzewa — rzadka, O(poddrzewo) operacja piggybackująca na
  i-tak-O(poddrzewo) przesunięciu MPTT.
- **Rooty mają `wydzial=NULL`.** Konsekwencja dla zapytań: `filter(jednostka__wydzial=root)`
  NIE łapie prac przypiętych do samego korzenia → tam gdzie trzeba, dokładamy
  `| Q(jednostka=root)`.
- Kiedyś (osobno, YAGNI): rename `wydzial` → `jednostka_toplevel`.

### `RodzajJednostki` — słownik rodzajów + flagi behawioralne

Osobna, edytowalna w adminie tabela (per-tenant). **Zastępuje** dawny CharField
`Jednostka.rodzaj_jednostki` (`normalna`/`kolo_naukowe`). Dodana w Fazie A;
`Jednostka.rodzaj` (FK, PROTECT) już istnieje i jest zbackfillowany.

```
RodzajJednostki
  nazwa                        : CharField (unique)   # "Standard","Koło naukowe","Wydział",…
  skrot, kolejnosc
  wyklucz_z_rankingu_autorow   : Bool  # (Faza A) autorzy z jednostek tego rodzaju poza rankingiem
  pokazuj_jako_odrebna_sekcje  : Bool  # (Faza A) listuj osobno na stronie przeglądania
  pokazuj_strukture_podjednostek : Bool  # (DODAWANE w Fazie B) strona w stylu wydziału
```

**Uwaga:** flaga `pokazuj_strukture_podjednostek` **nie istnieje jeszcze w Fazie A**
(Faza A ma tylko dwie pierwsze flagi) — dodajemy ją w Fazie B (pierwsza migracja) i
zaznaczamy `True` na wierszu „Wydział". Skonwertowane wydziały **już mają
`rodzaj="Wydział"`** (ustawia komenda `konwertuj_wydzialy_na_jednostki` w Fazie A),
więc po dodaniu+zaznaczeniu flagi **każdy były wydział automatycznie renderuje
stronę w stylu strukturalnym** — bez ruszania pojedynczych jednostek.

- **Behawior wyłącznie we flagach, nie w nazwie.** Rozróżnianie „koło vs zwykła vs
  inna" idzie przez FK `rodzaj` + flagi. Kod pyta „czy rodzaj ma flagę X", nie
  „czy nazywa się koło". Dodanie nowego rodzaju („Instytut", „Dział specjalny") =
  nowy wiersz + flagi, zero zmian w kodzie.
- Seed: `normalna`→**Standard** (flagi False), `kolo_naukowe`→**Koło naukowe**
  (`wyklucz_z_rankingu_autorow=True`, `pokazuj_jako_odrebna_sekcje=True`),
  **Wydział** (`pokazuj_strukture_podjednostek=True`).
- Odmiana (gałąź `feat/odmiana-rodzaj-instytucji`): docelowo `nazwa` będzie źródłem
  lematu; ten branch tylko przygotowuje pole.

### Pozostałe zmiany w `Jednostka`

- `rodzaj_jednostki` (CharField) → **usuwane** (FK `rodzaj` z Fazy A zastępuje).
  Miejsca pytające o `rodzaj_jednostki=="kolo_naukowe"` przechodzą na flagi rodzaju.
- `wchodzi_do_raportow` → **RenameField `wchodzi_do_rankingu_autorow`.** To
  istniejące od `0001` pole per-jednostka: „czy prace jednostki WLICZAJĄ SIĘ do
  sum rankingu autorów". Zmiana nazwy + opisu w UI, DB rename kolumny (zależne
  widoki auto-śledzą po attnum). **To NIE jest żadne «pole sekcji»** — takiego
  pojęcia nie ma.
- `aktualna` (dziś derywowana triggerem) → **domyślnie derywowana** w Pythonie z
  dat historii (`Jednostka_Rodzic.do`): jest zamknięty wpis (`do` w przeszłości) →
  `False`; jest bieżący wpis lub brak wpisów → `True`. **Plus ręczny override
  (decyzja usera 2026-07-04):** operator może nadpisać wartość — dokładamy pole
  `aktualna_override` (nullable Bool): `NULL` = licz z historii; ustawione =
  trzymaj wybór operatora (sygnały/`przelicz_aktualna` NIE ruszają, gdy override
  ≠ NULL). Efektywne `aktualna` = override, a jak NULL — derywacja.
  TRZY OSOBNE osie: `aktualna` (derywowana + opcjonalny override) / `widoczna`
  (ręczna publikacja) / `wchodzi_do_rankingu_autorow` (ręczne wykluczenie z sum).
- Pola per-węzeł z `Wydzial` (już dodane w Fazie A): `zezwalaj_na_ranking_autorow`
  (default True, per-węzeł — ≠ per-rodzaj `wyklucz_z_rankingu_autorow`),
  `poprzednie_nazwy`, `skrot_nazwy`. `otwarcie`/`zamkniecie` → historia od/do.
- `legacy_wydzial_id` (Fazy A, nullable, indeks) — trwałe mapowanie `Wydzial.id →
  Jednostka.id`, klucz idempotencji i migracji wartości. Drop w Fazie C.

### Historia temporalna — `Jednostka_Rodzic` (dawniej `Jednostka_Wydzial`)

```
Jednostka_Rodzic
  jednostka : FK(Jednostka, CASCADE)
  parent    : FK(Jednostka, CASCADE, null=True)  # dawniej: wydzial (NOT NULL)
  od, do    : DateField (null, blank)
```

- `parent` nullable — legalny stan „jednostka wisiała bezpośrednio pod uczelnią".
- Manager rozcinający zakresy dat przenosi się 1:1. Constrainty GiST
  (`unikalny_zakres_dat_dla_jednostki`) + CHECK (`bez_dat_do_w_przyszlosci`)
  zostają (przeżywają RenameModel — patrz Pułapki w planie: clamp `do`).
- **Sprawdzanie uczelni USUWANE, NIE odtwarzane** (federacja) — także z `clean()`.
- **Inwariant:** bieżący wpis (`do IS NULL`).parent == żywy MPTT parent.
- Konwersja historii sub-jednostek: przepisujemy na krawędź faktycznego rodzica z
  zachowaniem `od`/`do` (nie kasujemy, nie zostawiamy na wydziale) — szczegóły w planie.

### Utrzymanie spójności (zamiast triggerów)

- **`aktualna`:** sygnały `post_save`/`post_delete` na `Jednostka_Rodzic` derywują
  `aktualna` dziecka z bieżącego wpisu. Cichy drift (`bulk_*`/`loaddata`) łapie
  komenda `przelicz_aktualna` (idempotentny recompute) + test-inwariant w CI.
- **`wydzial` (korzeń):** utrzymywany denorm-kaskadą (wyżej) + test-inwariant „po
  re-parencie każdy potomek ma `wydzial == get_root()`".

### Usuwane / przepinane modele

- `Wydzial` — usuwany w **Fazie C** (po konwersji i przepięciu FK; musi pozostać
  importowalny do tego czasu — ~68 historycznych migracji go referuje).
- **5 FK** dziś → `Wydzial`, po migracji → `Jednostka` (three-step: →Integer,
  remap przez `legacy_wydzial_id`, →FK): `Kierunek_Studiow.wydzial` (PROTECT),
  `Patent.wydzial` (SET_NULL), `Opi_2012.wydzial` (CASCADE),
  `import_dyscyplin…wydzial` (SET_NULL), `Obslugujacy_Zgloszenia_Wydzialow.wydzial`
  (CASCADE). (`Zgloszenie.wydzial` NIE ISTNIEJE — zgłoszenia sięgają wydziału tylko
  przez `jednostka.wydzial`.)

---

## Sekcja 2 — Konsumenci: raporty / UI / API / importy

### Raporty — działają przez denorm-korzeń (bez `get_descendants`)

Ponieważ `jednostka.wydzial` = korzeń, „szukaj po wydziale" to po prostu
`filter(autorzy__jednostka__wydzial=root)` — jeden indeksowany FK-equality daje
całe poddrzewo (dołóż `| Q(autorzy__jednostka=root)` dla prac samego korzenia).
Zmiany są głównie w UI, nie w mechanice zapytań:

- **Picker „wydziału" → jednostki top-level** (rooty uczelni, `parent__isnull=True`,
  `widoczne()`) — nowy autocomplete zamiast osobnego `Wydzial.objects`.
- **„Rozbij na wydziały" → rooty uczelni** (`Uczelnia` NIE jest węzłem MPTT →
  `filter(uczelnia=U, parent__isnull=True)`); grupowanie po `jednostka.wydzial`.
- **Wykluczenie kół z rankingu** → `rodzaj__wyklucz_z_rankingu_autorow=True` (flaga
  rodzaju), NIE string `rodzaj_jednostki`. `zezwalaj_na_ranking_autorow` (per-węzeł)
  zostaje osobno.
- **Widoki sum** (`bpp_nowe_sumy_*`, karmią ranking autorów — jedyny konsument):
  zdejmujemy JOIN `bpp_wydzial` (kolumna `wydzial_id` teraz to Jednostka-korzeń);
  reguła członkostwa = `WHERE wchodzi_do_rankingu_autorow = true` (sumuj każdą
  jednostkę potomną, chyba że odznaczona). Sieroty liczą się jeśli nie odznaczone
  (Kryterium #3 rozluźnione świadomie). `Nowe_Sumy_View.wydzial` → FK→Jednostka
  (to model na widoku, nie self-FK).
- Podsystemy: `nowe_raporty` (POZIOM_WYDZIAL → picker top-level, `prace_wydzialu(root)`
  prawie bez zmian), `ranking_autorow`, `raport_slotow` (dzieli już po jednostce;
  wydział = kolumna), `ewaluacja_metryki` (filtr/kolumna XLSX). Cache
  `Rekord.prace_wydzialu` zostaje (parametr to teraz root-Jednostka).

### Multiseek / DjangoQL

- **`WydzialQueryObject`/`PierwszyWydzialQueryObject` ZOSTAJĄ osobne** (nie zwijają
  się do `JednostkaQueryObject`). Picker = jednostki top-level; `real_query` =
  `Q(autorzy__jednostka__wydzial=value) | Q(autorzy__jednostka=value)` (denorm!);
  operatory męskie zostają; `PierwszyWydzial` +`autorzy__kolejnosc=0`.
- `RodzajJednostkiQueryObject` → lista dynamiczna z `RodzajJednostki.objects.all()`,
  zapytanie `autorzy__jednostka__rodzaj=<row>`.
- **Zapisane wyszukiwania:** migracja WARTOŚCI (`multiseek_searchform.data`, JSON) —
  dla „Wydział"/„Pierwszy wydział" remap PK (stary Wydzial pk → korzeń przez
  `legacy_wydzial_id`); dla „Rodzaj jednostki" remap LABELA (stary CharField label
  → `RodzajJednostki.nazwa`). BEZ relabel pola, BEZ remapu operatorów (QueryObjecty
  żyją). DjangoQL: ścieżka `autorzy__jednostka__wydzial` przeżywa (pole zostaje);
  `rodzaj_jednostki`→`rodzaj`.

### Admin / Browse / API / Routing

- **Admin:** `JednostkaAdmin` — filtr po `parent` (autocomplete-backed); kolumny/
  filtry `wydzial` (czytają korzeń — zostają); `rodzaj_jednostki`→`rodzaj` FK.
  `WydzialAdmin`/`WydzialInline` usuwane (zarządzanie węzłami przez draggable-MPTT).
- **Browse:** znika osobny `WydzialView`; `JednostkaView` renderuje węzeł w jednym
  z dwóch stylów wg `object.rodzaj.pokazuj_strukture_podjednostek` — True: strona
  strukturalna (podjednostki/koła/historyczne, metody przeniesione na `Jednostka`);
  False: strona z pracami. Stary URL `browse_wydzial/<slug>` → **301** (lookup
  `Wydzial` po slug — model żyje → `Jednostka(legacy_wydzial_id)` → slug węzła).
  `WydzialSitemap` scalony/usunięty.
- **API (deprecation, nie usunięcie):** `Wydzial` model żyje do Fazy C →
  `/api/v1/wydzial/` (`WydzialViewSet`/`WydzialSerializer`) **nietknięte w Fazie B**.
  `JednostkaSerializer.wydzial` (czytał usuwany FK→Wydzial) → wskazuje zasób
  Jednostki-korzenia (lub oznaczony deprecated). bibtex `school` = korzeń.
- **Routing zgłoszeń:** zachować selekcję „pierwsza jednostka autora z
  `skupia_pracownikow=True`"; `emaile_dla_wydzialu(jednostka.wydzial)` →
  `emaile_dla_obslugujacego(jednostka.get_root())`; FK
  `Obslugujacy_Zgloszenia_Wydzialow.wydzial` → Jednostka (root).

### Flaga `uzywaj_wydzialow` — ZOSTAJE w Fazie B

**Decyzja usera (runda 3+4):** flaga ZOSTAJE, ale **konsolidujemy ją na modelu
`Uczelnia` jako jedyne źródło prawdy** (per-uczelnia, konfigurowalna w adminie —
wymóg multi-hosted). Dziś jest w DWÓCH miejscach i kod czyta niespójnie:
- **globalny env** `DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW` (czytają: multiseek
  `fields/__init__.py:134,158`, `browse.py:709`, `menu.py:257`, `__str__`
  `jednostka.py:207`) — **ZŁY w multi-hosted** (nie da się różnicować per uczelnia);
- **pole modelu** `Uczelnia.uzywaj_wydzialow` (`uczelnia.py:631`, już istnieje;
  czytają: `ranking_autorow`, `context_processors/constance_config.py:45`).

**Faza B:** wszystkie czytniki env → przełączyć na `uczelnia.uzywaj_wydzialow`
(przez `Uczelnia.objects.get_for_request` / `self.uczelnia` w `__str__`); **env
usunąć** (domyślność = `default=True` na polu). Bramkowane gałęzie adaptujemy do
top-level jednostek zamiast `Wydzial.objects`.

**Semantyka:** `True` → „wydziały = jednostki top-level (parent IS NULL)", UI
pokazuje opcje wydziałowe; `False` → wszystko jest jednostką, UI **nie oferuje
rozbicia «na wydziały»** (user wybiera jednostkę). Dlatego problem „prace korzenia
w NULL-owej kupie przy grupowaniu po wydziale" **nie istnieje** — płaska instalacja
nigdy nie grupuje po wydziale, a sumy punktów liczą się poprawnie niezależnie od
wydziału. Żaden `COALESCE`/marker nie jest potrzebny. (Konfigurowalny LABEL poziomu
top-level — „Wydział"/„Dział"/„Dywizja" — osobny przyszły temat.)
Pełne usunięcie flagi + konfigurowalny label poziomu top-level („Wydział"/„Dział"/
„Dywizja", żeby uczelnia mogła nazwać swój szczyt inaczej) = **osobny audit
później**. `__str__` dokleja skrót korzenia (`self.wydzial.skrot` — root ma
`wydzial=NULL`, więc dla korzeni nic nie dokleja), gated
`uzywaj_wydzialow` + `SKROT_WYDZIALU_W_NAZWIE`.

### Uprawnienia (`system.py`)

Grupy uprawnień: usuń `Wydzial`/`Jednostka_Wydzial`, dodaj `Jednostka_Rodzic`;
`Obslugujacy_Zgloszenia_Wydzialow` zostaje. Czyszczenie osieroconych
`ContentType`/`Permission` po `Wydzial` → **Faza C** (po drop modelu).

---

## Fazy wdrożenia (szczegóły + kolejność w PLANIE)

- **Faza A (zrobiona, w `dev`):** addytywna — `RodzajJednostki`+seed,
  `Jednostka.rodzaj` FK+backfill, pola per-węzeł, `legacy_wydzial_id`, konwersja do
  UKRYTYCH węzłów, fix wycieków `widoczna=False` (API/sitemap/autocomplete).
- **Faza B (ten plan):** atomowy release kod+schemat — DROP triggerów + konwersja
  historii, `Jednostka_Rodzic`+re-parent, **retarget `wydzial` na denorm-korzeń**,
  repoint 5 FK, redefinicja widoków sum, RenameField `wchodzi_do_rankingu_autorow`,
  usunięcie `rodzaj_jednostki`, przepięcie konsumentów, recompute `aktualna` +
  odkrycie (`widoczna=True`) skonwertowanych w Fazie A ukrytych węzłów, migracja
  wartości multiseek.
- **Faza C (później):** drop `Wydzial`, drop `legacy_wydzial_id` (po końcu
  deprecation API), usunięcie `uzywaj_wydzialow` + audit labela top-level, rename
  `wydzial`→`jednostka_toplevel`, czyszczenie ContentType/Permission, rebuild
  cache, `baseline-update`.

---

## Kryteria sukcesu

1. Jedno drzewo `Uczelnia → (Jednostka*)`; „wydział" = jednostka top-level; brak
   markera roli. Instalacja płaska i „z wydziałami" różnią się liczbą pięter.
2. Pełna historia temporalna zachowana i widoczna.
3. Raporty na tych samych danych dają **spójne** wyniki (z jednym świadomym
   rozluźnieniem: sieroty bez wydziału liczą się teraz w rankingu, chyba że mają
   `wchodzi_do_rankingu_autorow=False` — dawny INNER JOIN je wykluczał).
4. „Rozbij na wydziały" = rozbicie po jednostkach top-level (rootach uczelni);
   `filter(jednostka__wydzial=root)` działa przez denorm.
5. Admin: filtr po jednostce nadrzędnej (`parent`, autocomplete).
6. Stare URL-e wydziałów → 301 (brak martwych linków, brak kolizji slug).
7. `/api/v1/wydzial/` działa (Wydzial żyje do Fazy C).
8. Multiseek/DjangoQL: `WydzialQueryObject` zostaje; zapisane wyszukiwania
   zmigrowane (PK wydziału → korzeń; label rodzaju → nowy); nic się nie sypie.
9. `RodzajJednostki` edytowalny per-tenant; rozróżnianie rodzajów przez FK+flagi
   (koło = rodzaj z `wyklucz_z_rankingu_autorow`).
10. Trzy triggery zdjęte przed konwersją; walidacja uczelni NIE odtwarzana
    (federacja); `aktualna` + `wydzial`(korzeń) utrzymywane w Pythonie/denorm +
    testy-inwarianty łapią drift.
11. Byłe wydziały (rooty) widoczne w `publiczne()`/formularzu zgłoszeń/publicznym
    autocomplete (`aktualna=True` przy braku historii).
12. `zezwalaj_na_ranking_autorow` per-węzeł zachowany (osobno od per-rodzaj flagi).
13. `Jednostka.wydzial` = poprawny korzeń dla całego drzewa (test-inwariant).
14. `wchodzi_do_raportow` → `wchodzi_do_rankingu_autorow`; sumy filtrują nowe pole.
15. `uzywaj_wydzialow` DZIAŁA (zostaje w Fazie B); nawigacja renderuje drzewo.
16. Cała suita testów zielona; baseline odświeżony (przy scalaniu).
17. Migracja idempotentna (`legacy_wydzial_id`) i przetestowana na ≥1 realnym
    dumpie multi-tenant.

## Świadomie odłożone (YAGNI / Faza C)

- Rename `Jednostka.wydzial` → `jednostka_toplevel` (kosmetyka nazwy).
- Konfigurowalny label poziomu top-level (audit).
- Twarde usunięcie `/api/v1/wydzial/` (po deprecation).
- Usunięcie flagi `uzywaj_wydzialow`.
- Rename modelu `Jednostka` → `JednostkaOrganizacyjna`.

---

## Changelog decyzji (skąd się wziął finalny projekt)

- **v1 (2026-07-02):** absorpcja `Wydzial` w `Jednostka`; `Jednostka.wydzial` jako
  zdenormalizowany „najbliższy wydział" (self-FK); `pelni_role_wydzialu` na rodzaju.
- **Rewizja 1 (2026-07-04) — „zabicie pojęcia wydziału":** brak markera roli;
  usunięcie `Jednostka.wydzial` self-FK; raporty na `get_descendants`;
  `RodzajJednostki` czysto opisowy z flagami.
- **Runda 2 (2026-07-04) — adwersaryjny review kolejności migracji (fable):**
  9 correctness-fixów DB (3 triggery, three-step FK, historical models w migracji,
  clamp constraintów, nested-set w Pythonie, DROP VIEW, catalog-driven denorm drop,
  usunięcie `clean()` uczelni). Odrzucenie pomysłu „pola sekcji" — `wchodzi_do_raportow`
  to istniejące pole sum → RenameField `wchodzi_do_rankingu_autorow`; brak pojęcia
  „sekcji raportu"; „rozbij na wydziały" = rooty top-level.
- **Runda 3 (2026-07-04) — decyzje usera:** **`Jednostka.wydzial` ZOSTAJE** jako
  denorm self-FK do KORZENIA (nie usuwane, nie property) — odczyty i zapytania
  działają, znika RemoveField-atomowość i refactor na `get_descendants`;
  utrzymanie przez `@depend_on_related("self","parent")`. Flaga
  `RodzajJednostki.pokazuj_strukture_podjednostek` dla stylu strony browse.
  `uzywaj_wydzialow` ZOSTAJE (audit później). `WydzialQueryObject` zostaje osobny.
