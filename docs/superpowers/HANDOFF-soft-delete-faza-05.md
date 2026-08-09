# Handoff: soft-delete, start fazy 05

> Po zamknięciu **fazy 04** (guardy PROTECT), 2026-08-09.
> Czytaj to zamiast odtwarzania historii z gita.

---

## 1. Gdzie jesteśmy

| | |
|---|---|
| Stan fazy 04 | gałąź `feat/soft-delete-04`, PR do `feat/soft-delete` |
| Punkt startowy fazy 05 | `feat/soft-delete` (fazy 01–04) |
| Migracje fazy 04 | `bpp/0501` (flip FK, **state-only**), `bpp/0502` (`Autor` → soft-delete + indeks częściowy) |
| Plan fazy 05 | wycofanie z PBN + nagrobki na zewnątrz (OAI-PMH / CERIF / REST) |

Faza 04 domknęła obie warstwy ochrony przed osieroceniem rekordów:

1. **FK `CASCADE` → `PROTECT`** na `Wydawnictwo_{Ciagle,Zwarte}_Autor.autor`,
   `Patent_Autor.autor`, `Praca_Doktorska.autor`,
   `Wydawnictwo_Zwarte.wydawnictwo_nadrzedne` — obrona przed kasowaniem
   TWARDYM.
2. **Guard aplikacyjny** w `Autor.delete()` i `Wydawnictwo_Zwarte.delete()`,
   liczący dzieci przez `global_objects` — obrona przed kasowaniem MIĘKKIM.

Warstwa 2 nie jest zdublowaniem warstwy 1: `on_delete` żyje wyłącznie
w kolektorze Django dla kasowania twardego. Miękkie `delete()` to `UPDATE`
na `deleted_at` i o `PROTECT` się nawet nie dowiaduje.

⚠️ **Baseline (`baseline-sql/`) jest NIEŚWIEŻY** — stoi na `bpp/0487`, gałąź na
`bpp/0502`. Zgodnie z CLAUDE.md odświeżenie robi się **raz, przy scalaniu**
całego `feat/soft-delete` do `dev`, a nie w równoległych feature-branchach.

⚠️ **CI NIE URUCHAMIA SIĘ na PR-ach do `feat/soft-delete`** — bez zmian
względem faz 02–03. Zielony check na takim PR-ze nie jest dowodem;
jedyną weryfikacją jest przebieg lokalny.

---

## 2. Co faza 04 zmieniła w kodzie

| Miejsce | Zmiana |
|---|---|
| `bpp/models/soft_delete.py` | `raise_if_has_protected_children(instance, relations, label)` + stała `LIMIT_PROBKI_CHRONIONYCH` |
| `bpp/models/abstract/authors.py` | `autor`: `CASCADE` → `PROTECT` (dziedziczą 3 modele `*_Autor`) |
| `bpp/models/praca_doktorska.py` | `autor`: `CASCADE` → `PROTECT` |
| `bpp/models/wydawnictwo_zwarte.py` | `wydawnictwo_nadrzedne`: `CASCADE` → `PROTECT`; własny `delete()` z guardem na rozdziały |
| `bpp/models/autor.py` | `Autor` → `SoftDeleteModel`; własne `delete()`/`restore()`; `AutorQuerySet` na `BppSoftDeleteQuerySet`; `AutorManager.get_queryset()` filtruje husk; `AutorGlobalManager`/`AutorDeletedManager`; indeks częściowy |
| `deduplikator_autorow/utils/merge.py` | `_odstaw_zdublowane_autorstwo()` — przepięcie wiersza kolizyjnego na autora głównego + własny `transaction_id` |
| `bpp/management/commands/wyczysc_publikacje_importu.py` | `_odepnij_rozdzialy()` — zerowanie self-FK przed kasowaniem |

### Odejścia od planu (świadome, uzasadnione)

- **`Autor.delete()` NIE woła `super().delete()`.** Plan tak kazał, ale
  `SoftDeleteModel.delete()` pakietu przechodzi po WSZYSTKICH relacjach
  odwrotnych i dla dziecka z `CASCADE` spoza soft-delete woła zwykłe
  `delete()` — czyli kasuje TWARDO. `Autor` ma **27** takich dzieci, m.in.
  `Autor_Jednostka`, `Autor_Dyscyplina`, `Autor_Absencja`. Mutacja pokazała
  dodatkowo, że samo przejście po relacjach `Autora` wywala się
  `ProgrammingError`-em na nieistniejącej tabeli
  (`raport_slotow_raportzerowyentry`). Plan sam deklarował „override nie
  kaskaduje" (spec §1, §10.1) — poprawiony został mechanizm, nie intencja.
  Faza 02 rozstrzygnęła to samo identycznie dla publikacji.
- **`Projekt_Autor` dołączony do listy relacji chronionych.** Ma `PROTECT`
  od dawna, więc twarde `autor.delete()` na uczestniku projektu już wcześniej
  było odmawiane; pominięcie zamieniłoby istniejącą gwarancję w ciche
  powodzenie. Konsekwencja: helper musi znosić modele bez `global_objects`
  (fallback na `objects`).
- **Helper nie materializuje wszystkich dzieci.** Plan robił
  `protected.extend(qs)`. Liczba idzie z `count()`, do `ProtectedError`
  trafia próbka ograniczona do 20.
- **§4c/R1 uderzyło przy Zadaniu 2, nie 3.** Kolektor Django czyta wiersze
  `*_Autor` bazowym menedżerem, który NIE filtruje kosza — sam flip FK
  wystarczył, żeby zepsuć scalanie. Poprawka poszła w tym samym commicie.

---

## 3. ⚠️ ZNALEZISKO DO ROZSTRZYGNIĘCIA: `Autor.aktualna_jednostka`

To najważniejsza pozycja tego handoffu.

`Autor.aktualna_jednostka` i `Autor.aktualna_funkcja` mają `on_delete=CASCADE`.
Oba pola są **denormalizowane** — liczy je trigger
`bpp_autor_jednostka_aktualna_jednostka()` (migracja `0046`) z wpisów
`Autor_Jednostka`. Efekt kaskady jest taki:

```
Jednostka.delete()
  → Jednostka.parent            CASCADE   (jednostki podrzędne)
  → Autor.aktualna_jednostka    CASCADE   (autorzy tej jednostki!)
  → Wydawnictwo_*_Autor.autor   (dawniej CASCADE — ich autorstwa)
```

Czyli **do fazy 04 skasowanie wydziału po cichu kasowało autorów wraz z ich
dorobkiem.** Trzy testy asertowały ten skutek jako poprawny
(`autorzy.count() == 0`).

Archeologia: migracja `0153_django21` (2018) miała `aktualna_jednostka`,
`aktualna_funkcja` **i** `wydawnictwo_nadrzedne` jako `PROTECT`. Hurtowa
`0155_CASCADE` (2019-03-03) przestawiła je wszystkie jednym pociągnięciem.
Faza 04 odkręciła z tego wyłącznie `wydawnictwo_nadrzedne`.

**Decyzja właściciela (2026-08-09): faza 04 NIE rusza tych dwóch pól.**
Uzasadnienie: pola są liczone triggerem, więc nie powinny wymagać ręcznej
polityki kasowania.

⚠️ **Zastrzeżenie do tej decyzji, do rozważenia w fazie 05 lub 07:** trigger
nie zatrzyma kolektora Django. Trigger odpala się na zmianach
`Autor_Jednostka` w bazie; `on_delete` żyje w Pythonie i wykonuje się
*zanim* baza cokolwiek zobaczy — `jednostka.delete()` wprost wystawia
`DELETE FROM bpp_autor`. Stan po fazie 04 jest więc taki:

- skasowanie jednostki/uczelni, w której autorzy mają prace →
  `ProtectedError` (w adminie: gołe 500),
- skasowanie jednostki, w której autorzy prac NIE mają → nadal **twardo
  kasuje tych autorów**.

To drugie jest cichą utratą danych, której guardy fazy 04 nie obejmują.
Naturalne domknięcie to `SET_NULL` na obu polach (migracja state-only, pola
są już `null=True, blank=True`, denorm i tak jest przeliczalny) — ale to
decyzja właściciela, nie zadanie techniczne.

---

## 4. Fakty, które kosztowały rundę poprawek

- **Wstawienie `class` w środku ciała klasy Pythona jest CICHE.** Dopisując
  `AutorGlobalManager`/`AutorDeletedManager` tuż za `get_queryset()`
  przeniosłem `create_from_string` i `fulltext_annotate` na
  `AutorDeletedManager`. Import przechodził, `type(Autor.objects)` nadal
  zwracało `AutorManager` — objaw wyszedł dopiero w autocomplete
  (`AttributeError`). Pilnuje tego dziś
  `test_menedzer_autora_nie_zgubil_wlasnych_metod`.
- **Kolektor Django widzi kosz.** `related_objects()` używa
  `_base_manager`, a ten (bez `base_manager_name`) jest zwykłym,
  NIEFILTRUJĄCYM menedżerem. Autorstwo w koszu blokuje więc `PROTECT` tak
  samo jak żywe. To dlatego §4c/R1 uderzyło wcześniej, niż przewidywał plan.
- **`Autor._base_manager` ma ZOSTAĆ niefiltrujący.** Przez niego rozwiązują
  się deskryptory FK — `autorstwo.autor` ma zwracać husk, a nie
  `DoesNotExist`. Nie ustawiaj `Meta.base_manager_name`.
- **Teardown testów spoza transakcji kasuje MIĘKKO.** Od fazy 02
  `publikacja.delete()` zostawia wiersze `*_Autor` w koszu; te chronią
  autora i wywracają sprzątanie jednostki. Testy Playwright potrzebowały
  `hard_delete()`.
- **`PYTEST_TESTCONTAINERS_REUSE=1` produkuje fałszywe regresje.** Pięć
  z dziesięciu porażek pierwszego przebiegu (`test_seed_instytucji`,
  `test_views_sql_publikacje`) znikło na świeżych kontenerach. Zanim
  uznasz porażkę za swoją — powtórz bez `REUSE`, a potem porównaj
  z `git stash`.
- **Migracja `AlterField` samego `on_delete` NIE jest darmowa.** Django nie
  wie, że `on_delete` nie istnieje w bazie, i wygeneruje
  DROP + ADD CONSTRAINT. Na `bpp_wydawnictwo_ciagle_autor` to `ACCESS
  EXCLUSIVE` na czas walidacji FK. Stąd `SeparateDatabaseAndState`.

---

## 5. Co czeka fazę 05

Zakres wg mapy z handoffu fazy 04 (§4a):

- `pbn_export_queue` dostaje operację `WYCOFANIE` obok `WYSYLKA`;
  soft-delete publikacji asynchronicznie wycofuje oświadczenia dyscyplin
  z profilu instytucji w PBN,
- **nagrobki na zewnątrz** (wciągnięte do fazy 05 decyzją z 2026-08-08):
  OAI-PMH `<header status="deleted">` w `src/cerif_export` (dziś **zero**
  obsługi `deleted`), odpowiednik w CERIF, sposób odkrycia usuniętych
  w `/api/v1/`.

Fundament jest gotowy: soft-delete bumpuje `ostatnio_zmieniony` — także dla
`Autor` (faza 04 wpięła `dopisz_znacznik_zmiany` w `Autor.save()`) — więc
`Model.deleted_objects.filter(ostatnio_zmieniony__gte=X)` działa już teraz.

⚠️ Nagrobki muszą być gotowe **przed fazą 07**, nie przed 05. Dopóki
kasowanie jest rzadkie, luka w OAI-PMH jest teoretyczna; faza 07 czyni
kasowanie rutynowym.

### Czego faza 04 NIE domyka (świadomie)

- **Brak UI dla `ProtectedError`.** Guard rzuca wyjątek; w adminie to gołe
  500. Zamiana na czytelny komunikat należy do fazy 07 (kosz w adminie).
  Komunikat wyjątku jest już po polsku i zawiera liczbę powiązań —
  wystarczy go pokazać.
- **`Autor` nie ma kosza w adminie.** Husk znika z `objects`, ale operator
  nie ma jak go zobaczyć ani przywrócić. Faza 07.
- **`Autor.hard_delete()` nie emituje `post_hard_delete`** — ten sam dług,
  co dla querysetów publikacji (do fazy 06).
- **Kaskada `Jednostka` → `Autor`** — patrz §3.

---

## 6. Dług nadal otwarty (z faz 01–03, stan bez zmian)

| Sprawa | Stan |
|---|---|
| **Wycieki ORM (kanarek `xfail(strict=True)`)** | bez zmian — potrzebne narzędzie model-aware (pytające `_meta`), nie rozszerzanie listy nazw |
| **PR upstream `django-easy-audit`** | [soynatan/django-easy-audit#348](https://github.com/soynatan/django-easy-audit/pull/348) — po scaleniu skasować `src/bpp/easyaudit_shim.py` |
| **`bpp-deploy`** | kontrolka „kronika views: N” po `bpp.0499` wypisze 0 |
| Pomiar `0492` i narzutu GiST | wciąż nikt nie zmierzył (dług fazy 01) |
| **Rejestr wskrzeszeń niewidoczny w adminie** | `pbn_integrator/admin.py` to nadal `# Register your models here.` |
| **`force=True` omija wskrzeszenie** | niespójność: `znajdz_ksiazke_nadrzedna` leży ZA guardem |
| **`Oswiadczenie_Instytucji.get_bpp_publication`** | iteruje po 4 modelach po `pbn_uid` przez `.objects` — nadal nikt nie rozpatrzył |
| **`hard_delete()` na querysecie nie emituje `post_hard_delete`** | do handoffu fazy 06 |
| **Strategia wydania** | bramka na fazie 07 (decyzja 2026-08-08, §4b handoffu fazy 04) |

---

## 7. Proces — co się sprawdziło w fazie 04

- **Mutacja, która PRZESZŁA, to informacja.** Dwa razy: (1) liczba
  w komunikacie `ProtectedError` — test nie rozróżniał `count()` od długości
  próbki, bo przy 3 dzieciach i limicie 20 dają to samo; wzmocniony
  `monkeypatch`-em limitu. (2) przekazanie `user`/`reason` do `super()` —
  dziś nieobserwowalne, bo mixin nic z nimi nie robi; zamiast wzmacniać test
  dopisałem do jego docstringu, czego NIE pilnuje.
- **Regresję odróżniaj od zanieczyszczenia przez `git stash`, nie przez
  intuicję.** Trzy z pięciu „podejrzanych" porażek okazały się moje, dwie —
  cudze; bez porównania z czystym drzewem zgadywałbym.
- **Uruchamiaj szeroką regresję ZARAZ po zmianie ryzykownej**, nie na końcu
  fazy. Flip FK złapał 5 realnych regresji w 4 różnych obszarach; gdyby
  doszły do tego zmiany Zadania 3, diagnoza byłaby dwa razy droższa.
- **Czerwień z `ImportError` nadal nie liczy się jako dowód** — ale czerwień
  z `ProtectedError` w cudzym teście (`deduplikator_autorow`) liczy się
  bardzo: to ona pokazała, że §4c/R1 jest realne i wcześniejsze, niż plan
  zakładał.
