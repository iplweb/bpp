# Handoff: soft-delete, start fazy 04

> Po zamknięciu **fazy 03** (audyt kategorii B), 2026-08-08.
> Czytaj to zamiast odtwarzania historii z gita.

---

## 1. Gdzie jesteśmy

| | |
|---|---|
| Gałąź | `feat/soft-delete-03`, worktree `~/Programowanie/bpp-soft-delete-03` |
| Baza | `feat/soft-delete` (zawiera fazy 01 i 02; PR #741 scalony) |
| Migracje fazy 03 | `pbn_integrator/0001` (rejestr wskrzeszeń), `bpp/0500` (warunkowy unique na habilitacji) |

Faza 03 domknęła **blocker wydania**: re-import z PBN publikacji, której rekord
BPP siedzi w koszu, nie wywala się już `IntegrityError`-em na unikalności
`pbn_uid` — rekord wraca z kosza, ze śladem w rejestrze. ⚠️ Zakres jest węższy,
niż brzmiała pierwotna obietnica „re-import nie tworzy duplikatów" — patrz
§3, „Czego faza 03 NIE naprawia".

⚠️ **Baseline (`baseline-sql/`) jest NIEŚWIEŻY** — stoi na `bpp/0487`, gałąź na
`bpp/0500`. Był taki już przed fazą 03 (fazy 01–02 dołożyły `0488`–`0499`).
Zgodnie z CLAUDE.md odświeżenie (`make baseline-update`) robi się **raz, przy
scalaniu**, a nie w równoległych feature-branchach.

---

## 2. NAJWAŻNIEJSZE: zmieniona decyzja o polityce kosza

Plan fazy 03 miał decyzję #14 „**POMIŃ + ZARAPORTUJ**”, argumentując, że
auto-restore pozwoliłby importowi wskrzeszać rzeczy skasowane celowo.

**Właściciel systemu zmienił ją 2026-08-08 na „PRZYWRÓĆ + ODNOTUJ”.**
Uzasadnienie: PBN jest źródłem prawdy dla tych publikacji — skoro rekord tam
jest, ma wrócić także do BPP.

Zastrzeżenie z pierwotnej decyzji nie zostało uznane za nieważne, tylko
przeniesione: z „nie róbmy tego” na „róbmy, ale zostawmy ślad”. Śladem jest
`pbn_integrator.RekordPrzywroconyPrzezImport` — rekord (generic FK), data,
publikacja PBN, ścieżka importu.

⚠️ Wpis powstaje **wyłącznie przy realnym wskrzeszeniu**. Zwykły re-import
żywego rekordu nie zostawia nic — inaczej rejestr zapełniłby się szumem
i przestałby cokolwiek znaczyć. Przypięte osobnym testem.

Punkt wejścia: `pbn_integrator.kosz.przywroc_jesli_w_koszu()`, wpięty
w `articles.py`, `books.py`, `chapters.py` (ta ostatnia w dwóch miejscach —
sam rozdział i jego książka-matka, rozróżnialne po `zrodlo_importu`).

---

## 2a. Druga zmiana kierunku: AKCESORY NIE ZAGLĄDAJĄ DO KOSZA

> Aktualizacja 2026-08-08, po self-review. Pierwsza implementacja fazy 03
> poszła **złą drogą** i została cofnięta (`eb046897a`).

Pierwotnie faza 03 kazała akcesorom (`rekord_w_bpp`, `get_bpp_publication`,
`matchuj_publikacje`) zaglądać do kosza i **zwracać rekordy skasowane**.
Właściciel rozstrzygnął inaczej:

> **Soft-delete znaczy, że rekordu NIE MA.** `Rekord` (widok `bpp_rekord_mat`)
> jest odfiltrowany po `deleted_at` i tak ma zostać. Akcesor zwraca `Rekord`
> albo `None` — nigdy rzeczy z kosza.
>
> Zaglądanie do kosza jest decyzją **IMPORTERA**, nie akcesora.

Dlaczego to ważne dla fazy 04: akcesory mają wołaczy, którzy zakładają KONKRETNY
typ zwracany. `PublicationAdmin` woła `.original` — atrybut istniejący
WYŁĄCZNIE na `Rekord`. Zwrócenie modelu konkretnego wywalało `AttributeError`
na całej changeliście, a w szablonie (`change_form.html`) to samo dawało pusty
`href` **bez żadnego wyjątku**. Pilnuje tego dziś
`src/pbn_api/tests/test_admin_rekord_w_bpp.py`.

---

## 3. Co faza 03 zmieniła w kodzie

| Miejsce | Zmiana |
|---|---|
| `pbn_integrator/kosz.py` | `przywroc_jesli_w_koszu()`, `wskrzes_z_kosza_po_pbn_uid()`, `znajdz_lub_wskrzes_rekord()` — całe zaglądanie do kosza w jednym module |
| `pbn_integrator/importer/{articles,books,chapters}.py` | wspólna preambuła `znajdz_lub_wskrzes_rekord()` w gałęzi `ret is None` |
| `pbn_integrator/importer/chapters.py` | `znajdz_ksiazke_nadrzedna()` — wydzielony, widzi kosz, wskrzesza |
| `pbn_import/utils/publication_import.py` | `global_objects` + `hard_delete()` przy czyszczeniu przed re-importem |
| `bpp/models/praca_habilitacyjna.py` | `autor`: `OneToOneField` → `ForeignKey` + warunkowy `phab_uniq_autor_zywy` (migracja `bpp/0500`) |
| `bpp/admin/praca_habilitacyjna.py` | `clean_autor()` — jawna walidacja „jeden autor, jedna żywa habilitacja" |
| `bpp/views/api/__init__.py` | `RokHabilitacjiView` pyta `Praca_Habilitacyjna.objects`, nie akcesor odwrotny |
| `bpp/templates/browse/autor.html` | pętla po `praca_habilitacyjna_set` (jak doktorat) |
| `deduplikator_autorow/utils/merge.py` | `wiersze_do_transferu()` widzi kosz; detekcja kolizji po `global_objects`; `KonfliktScalania`; guard `_w_koszu()` przed kolejką PBN |

**NIE zmienione (cofnięte świadomie):** `pbn_api/models/publication.py`
i `import_common/core/publikacja.py` — patrz §2a. Helper `widzacy_manager()`
został usunięty razem z testami, które pilnowały złego zachowania.

**ZOSTAWIONE świadomie na `objects`** (rejestr decyzji w
`src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py`): ewaluacja,
snapshot odpięć, komparator PBN, REST API, skanowanie do dedupu publikacji.

### Czego faza 03 NIE naprawia (świadomie)

**Ścieżka fuzzy tworzy duplikat.** Rekord BPP **bez** `pbn_uid` (praca
wprowadzona ręcznie), skasowany miękko, nie zostanie znaleziony przez
`matchuj_publikacje` — bo ten idzie po `Rekord`, a `Rekord` kosza nie widzi.
Import utworzy nowy rekord. Po decyzji z §2a to zachowanie **zamierzone**
(rekordu nie ma), ale nie należy go opisywać jako „duplikaty domknięte".

Domknięta jest ścieżka po `pbn_uid` — i tam problemem nie był cichy duplikat,
tylko **wywalenie importu**: `pbn_uid` to `OneToOneField(unique=True)` BEZ
warunku partial, więc rekord w koszu nadal trzyma to pole, a próba utworzenia
nowego kończyła się `IntegrityError`.

---

## 4. Fakty, które kosztowały rundę poprawek

- **`Patent` NIE ma pola `pbn_uid`.** Wpisanie go do listy modeli
  matchowanych po `pbn_uid` wywala `FieldError` przy pierwszym `.filter()`.
- **`get_bpp_publication` i `rekord_w_bpp` zachowują się RÓŻNIE**: przy wielu
  trafieniach pierwsza zwraca `None`, druga sklejone tytuły; przy braku
  trafień druga spada do fuzzy matchingu. Różnica jest historyczna i celowo
  zachowana — nie ujednolicaj jej „przy okazji”.
- **`rekord_w_bpp` bywa STRINGIEM.** Każdy helper na ścieżce importu musi to
  przyjąć bez wyjątku (`getattr`, nie `isinstance`), inaczej wywróci cały
  przebieg z powodu niezwiązanego z koszem.
- **`_try_match_pub_by_doi` mimo zawężenia po DOI przepuszcza kandydata przez
  próg podobieństwa tytułu (0.80).** Test z celowo innym tytułem padnie —
  i NIE będzie to dowód, że kod nie widzi kosza.
- **Linie cytowane w planie dla `merge.py` były nieaktualne** (plik
  zrefaktoryzowany). Szukaj lookupów na nowo, nie po numerach.
- **`GlobalManager` pakietu nie ma metod domenowych.** `wydawnictwa_
  nadrzedne_dla_innych()` zostaje na `objects` — świadomie.
- **Lista wołaczy ≠ lista założeń wołaczy.** Sprawdzenie, KTO woła akcesor,
  nie mówi nic o tym, CO robi z wynikiem. `PublicationAdmin` woła `.original`
  — atrybut istniejący wyłącznie na `Rekord`. To samo pominięcie w szablonie
  nie daje wyjątku, tylko pusty `href`.
- **`matchuj_publikacje` ma DWÓCH wołaczy o sprzecznych potrzebach**:
  `pbn_api` (przekazuje `Rekord`) i `deduplikator_publikacji`
  (`tasks.py:187`, przekazuje modele konkretne). Przełączenie go „na globalny
  menedżer" sprawiło, że dedup zaczął podsuwać kosz — wbrew decyzji z Taska 8.

---

## 4a. Mapa pozostałych faz — co dalej

Kolejność nie jest dowolna: każda kolejna konsumuje coś, co dostarcza poprzednia.

| Faza | Co robi | Zależy od |
|---|---|---|
| **04 — guardy PROTECT** | flip FK `CASCADE→PROTECT` na powiązaniach autora (`*_Autor.autor`, `Praca_Doktorska.autor`) i na self-FK rozdziałów (`Wydawnictwo_Zwarte.wydawnictwo_nadrzedne`) + guard aplikacyjny; `Autor` staje się `SoftDeleteModel` | — |
| **05 — wycofanie z PBN** | `pbn_export_queue` dostaje operację `WYCOFANIE` obok `WYSYLKA`; soft-delete publikacji asynchronicznie wycofuje oświadczenia dyscyplin z profilu instytucji w PBN | kolejka PBN |
| **06 — `SoftDeleteLog`** | model audytu (kto / kiedy / dlaczego / status PBN) zasilany receiverami `post_soft_delete` / `post_restore` / `post_hard_delete`; receiver DELETE kolejkuje wycofanie z fazy 05 | **05** |
| **07 — admin** | kosz w adminie dla 5 typów publikacji + `Autor`: „Usuń" = soft-delete z powodem, filtr „Pokaż skasowane", akcja „Przywróć", osobna „Usuń trwale" (superuser) | **06** (powód → log) |
| **08 — regresja E2E** | suita domykająca całość | wszystkie |

### Co fazy 01–03 już pod nie podłożyły

Trzy rzeczy są gotowe i kolejne fazy mają je po prostu skonsumować — nie
trzeba ich projektować od nowa:

- **Sygnatury `delete(user=..., reason=...)` / `restore(user=...)`** istnieją
  w mixinie publikacji od fazy 02 (puste, ale obecne — kontrakt PINNED).
  Faza 06 wpina w nie `SoftDeleteLog`, faza 07 wstrzykuje `request.user`.
  Sygnatur nie trzeba ruszać.
- **Sygnały `post_soft_delete` / `post_restore` są emitowane** i przypięte
  testem (faza 02). Faza 06 podpina receivery pod gotowy mechanizm.
- **Kontrakt `ostatnio_zmieniony`** — soft-delete bumpuje znacznik, więc
  nagrobki dla harvestu przyrostowego są odpytywalne przez
  `deleted_objects.filter(ostatnio_zmieniony__gte=X)` już teraz, bez czekania
  na `SoftDeleteLog` z fazy 06.

### Nagrobki na zewnątrz — WCIĄGNIĘTE DO FAZY 05 (decyzja 2026-08-08)

OAI-PMH `<header status="deleted">` w `src/cerif_export` (dziś **zero**
obsługi `deleted`), odpowiednik w CERIF, sposób odkrycia usuniętych
w `/api/v1/`. Fundament gotowy — soft-delete bumpuje `ostatnio_zmieniony`,
więc `Model.deleted_objects.filter(ostatnio_zmieniony__gte=X)` działa już
teraz. Brakuje wyłącznie ekspozycji.

**Dołączone do zakresu fazy 05**, bo to ten sam motyw co wycofanie oświadczeń
z PBN: *systemy zewnętrzne dowiadują się, że coś zniknęło* — inny odbiorca,
ta sama historia. Trzymane osobno przepadłyby między fazami, bo żaden plan
ich nie obejmował.

⚠️ Muszą być gotowe **przed fazą 07**, nie przed 04. Dopóki kasowanie jest
rzadkie, luka w OAI-PMH jest teoretyczna; faza 07 czyni kasowanie rutynowym
i dopiero wtedy zaczyna realnie boleć.

## 4b. Strategia wydania — bramka przesunięta na fazę 07

> 🔁 **DECYZJA 2026-08-08.** Poprzednia rekomendacja (fazy 01–03) brzmiała
> „wydać po fazie 04”. Zmieniona: **wydajemy dopiero po fazie 07**.

Powód nie jest bezpieczeństwem — guardy z fazy 04 domykają je w porządku.
Powodem jest **spójność dla operatora**.

Sprawdzone na kodzie (2026-08-08): `src/bpp/admin/` nie ma dziś ŻADNEGO
kosza — trafienia `deleted_at` to hydraulika (ukryte pole formularza dla
walidacji ograniczeń, filtry agregatów), a nie filtr „pokaż skasowane” ani
akcja „Przywróć”. Jednocześnie `SoftDeleteQuerySet.delete()` jest już miękki,
a `delete_selected` Django woła właśnie queryset.

Czyli wydanie po fazie 04 dałoby operatorowi:

- „Usuń” przestaje znaczyć „zniknęło” — rekord zostaje w bazie,
- **nie da się go przywrócić ani obejrzeć bez programisty**,
- nie da się go usunąć naprawdę.

Operator traci jedną zdolność i nie dostaje w zamian żadnej, bo kosz
z przywracaniem przychodzi dopiero w fazie 07. To regresja UX, nie funkcja.

**Fazy 01–06 scalamy dalej do `feat/soft-delete`, ale nie wydajemy.**

Świadomie ODRZUCONE: wydanie faz 01+02 z tymczasowym „Usuń = twardo”
w adminie. Oznaczałoby utrzymywanie dwóch semantyk kasowania równolegle
i wyrzucenie tego kodu w fazie 07 — koszt bez odbiorcy.

## 5. Co czeka fazę 04 (guardy PROTECT)

- **Nikt nie przeplata `AutorManager`** — po uczynieniu `Autor`
  `SoftDeleteModel` husk autora zostanie widoczny.
- **`Autor.restore()` musi nadpisać `strict=False`** (inwariant z docstringu
  `bpp/models/soft_delete.py`).
- **Soft-skasowana publikacja NADAL trzyma referencję PROTECT do autora**
  — `Praca_Habilitacyjna.autor`. Dziś oznacza to `ProtectedError` przy próbie
  skasowania autora i jest to zachowanie poprawne (rekord istnieje, nie wolno
  go osierocić), ale faza 04 musi to obsłużyć w UI, a nie zostawić jako gołe
  500.
- **`Praca_Habilitacyjna.autor` NIE jest już `OneToOneField`** (faza 03,
  migracja `bpp/0500`). Akcesor odwrotny to `autor.praca_habilitacyjna_set`.
  Ścieżka filtrowania w ORM/DjangoQL się nie zmieniła
  (`related_query_name` = nazwa modelu), ale każdy kod sięgający po
  `autor.praca_habilitacyjna` jako po OBIEKT jest zepsuty. Dwa znane miejsca
  są już naprawione (`RokHabilitacjiView`, `browse/autor.html`) i oba miały
  testy, które to złapały.
- ⚠️ **`scal_autora` polega dziś na TWARDEJ kaskadzie `autor_duplikat.delete()`.**
  Gdy autorstwo duplikatu koliduje z autorstwem głównego i OBA są w koszu,
  wiersz duplikatu zostaje przy duplikacie — i znika dopiero dlatego, że
  usunięcie autora kaskaduje po FK fizycznie. **Faza 04 zmienia kasowanie
  autora na miękkie, więc ten wiersz przetrwa** i zostanie sierotą wskazującą
  na autora w koszu; co gorsza będzie miał `transaction_id` publikacji, więc
  `publikacja.restore()` wskrzesi DWA wiersze `(rekord, glowny, typ)`
  i wywali się na `wc_autor_uniq_rekord_autor_typ`.
  Miejsce: gałąź `if existing:` w `_transfer_authorship_record`
  (`deduplikator_autorow/utils/merge.py`). Poprawka to prawdopodobnie
  przepięcie wiersza na głównego autora + nadanie mu WŁASNEGO
  `transaction_id` (odpięcie od grupy restore'u publikacji). Napisana raz
  i usunięta, bo mutacja pokazała, że dziś jest martwym kodem — patrz §7.

## 6. Dług nadal otwarty

| Sprawa | Stan |
|---|---|
| **Wycieki ORM (kanarek `xfail(strict=True)`)** | `test_kanarek_orm_join_po_publikacji_ma_predykat_deleted_at` dalej `xfail`. ⚠️ Tabelka 10 wycieków w `reviews/2026-08-07-faza-02-inwentaryzacja-orm.md` NIE jest listą zadań — patrz self-review w tym pliku. Potrzebne narzędzie model-aware (pytające `_meta`), nie rozszerzanie listy nazw |
| **PR upstream `django-easy-audit`** | **WYSTAWIONY 2026-08-08: [soynatan/django-easy-audit#348](https://github.com/soynatan/django-easy-audit/pull/348)** (fork `mpasternak`). Gdy zostanie scalony — skasować `src/bpp/easyaudit_shim.py`, wywołanie `zainstaluj()` w `BppConfig.ready()` i `test_easyaudit_shim.py`. Przypomni o tym test `test_upstream_nadal_ma_blad_czyli_shim_jest_potrzebny`, który wtedy zacznie padać |
| **`bpp-deploy`** | kontrolka „kronika views: N” po `bpp.0499` wypisze 0 i może zmylić operatora |
| Pomiar `0492` i narzutu GiST | wciąż nikt nie zmierzył (dług fazy 01) |
| **Rejestr wskrzeszeń niewidoczny w adminie** | `pbn_integrator/admin.py` to nadal `# Register your models here.`. Brak też indeksu `(content_type, object_id)` pod pytanie „czy TEN rekord wrócił?". Rejestr, do którego nie da się zajrzeć, nie spełnia swojej roli — a to ona uzasadniała zmianę decyzji #14 |
| **`force=True` omija wskrzeszenie** | Guard to `if not force`, więc `--force` idzie prosto do tworzenia nowego rekordu — i przy rekordzie w koszu wywali się na unikalności `pbn_uid` (tak samo jak przy rekordzie żywym; to nie jest regresja fazy 03). Niespójność: `znajdz_ksiazke_nadrzedna` leży ZA tym guardem, więc przy `force` książka-matka JEST wskrzeszana, a sam rozdział nie |
| **`Oswiadczenie_Instytucji.get_bpp_publication`** | `pbn_api/models/oswiadczenie_instytucji.py:51-74` iteruje po 4 modelach po `pbn_uid` przez `.objects`. Nie jest ani na liście zmienionych, ani „świadomie zostawionych" — po prostu nikt go nie rozpatrzył |
| **`hard_delete()` na querysecie nie emituje `post_hard_delete`** | Najbardziej destrukcyjna operacja przejdzie niezauważona przez `SoftDeleteLog` z fazy 06. Do handoffu fazy 06 |
| **Strategia wydania** | ⚠️ **ZMIENIONA 2026-08-08: bramka przesunięta z fazy 04 na fazę 07.** Uzasadnienie w sekcji 4b |

## 7. Proces — co znowu się sprawdziło

- **Mutacja, która PRZESZŁA, to informacja — nie powód, żeby dopisać asercję.**
  Przy pozycji 3.3 dodałem gałąź odpinającą `transaction_id` dla autorstwa
  już siedzącego w koszu. Mutacja (`pass`) przeszła. Zamiast wzmacniać test
  sprawdziłem DLACZEGO — i okazało się, że `autor_duplikat.delete()` kaskaduje
  twardo i fizycznie usuwa ten wiersz. Cała gałąź była martwym kodem opartym
  na moim wyobrażeniu, nie na tym, co robi baza. Reguła: mutacja, która
  przeszła, znaczy **albo słaby test, albo zbędny kod** — rozstrzygnij który,
  ZANIM cokolwiek dopiszesz. (Konsekwencja dla fazy 04: §5, ostatni punkt.)
- **Mutacja jest jedynym dowodem, że test coś pilnuje.** W fazie 03 pierwsza
  czerwień testu rejestru była `ImportError` — a to nie dowodzi, że asercje
  działają. Dopiero wyłączenie warunku na `deleted_at` pokazało, że tak.
- **Dane referencyjne z `baseline.sql` NIE są w testach gwarantowane.** Testy
  transakcyjne z tego samego przebiegu flushują bazę i przywracają tylko
  część danych — a przy `PYTEST_TESTCONTAINERS_REUSE=1` zanieczyszczenie
  przechodzi między przebiegami. Objaw: `Typ_Odpowiedzialnosci /
  Rodzaj_Zrodla / Jezyk DoesNotExist` w teście, który „przecież przechodził".
  Bierz słowniki z fixture'ów (`jezyki`, `charaktery_formalne`, `typy_kbn`,
  `statusy_korekt`, `typy_odpowiedzialnosci`), nie z baseline. Zanim uznasz
  taką porażkę za regresję — powtórz na świeżych kontenerach (bez `REUSE`).
- **`git checkout <plik>` cofa do HEAD, a nie do „stanu sprzed mutacji".**
  Przy mutacyjnym testowaniu NIEZACOMMITOWANEJ zmiany to kasuje całą
  implementację. Rób kopię pliku i przywracaj z niej.
- **Django ma DWA mechanizmy walidacji unikalności o różnej polityce
  milczenia.** `validate_unique()` (dla `unique=True`/`unique_together`)
  zgłasza błąd; `validate_constraints()` (dla `Meta.constraints`) **cicho
  pomija** ograniczenie, którego pole warunku jest wykluczone z walidacji —
  a `_get_validation_exclusions()` wyklucza wszystko spoza `Meta.fields`,
  które admin nadpisuje spłaszczonymi `fieldsets`. Zamiana `unique=True` na
  warunkowy `UniqueConstraint` po cichu zabiera walidację w formularzu.
- **`ruff format` na całym katalogu znowu zagarnął cudzy plik.** Formatuj
  tylko własne; cofnięcie kosztowało osobny commit.
- **`make tests-without-playwright` zwraca EXIT 0 mimo porażek** (sprawdzone
  w fazie 02: 7 failed + 2 errors przy zerowym kodzie). Czytaj podsumowanie
  pytest, nie kod wyjścia.
