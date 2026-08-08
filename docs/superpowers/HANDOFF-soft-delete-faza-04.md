# Handoff: soft-delete, start fazy 04

> Po zamknięciu **fazy 03** (audyt kategorii B), 2026-08-08.
> Czytaj to zamiast odtwarzania historii z gita.

---

## 1. Gdzie jesteśmy

| | |
|---|---|
| Gałąź | `feat/soft-delete-03`, worktree `~/Programowanie/bpp-soft-delete-03` |
| Baza | `feat/soft-delete` (zawiera fazy 01 i 02; PR #741 scalony) |
| Migracje fazy 03 | `pbn_integrator/0001` (nowy model rejestru) |

Faza 03 domknęła **blocker wydania**: re-import z PBN nie tworzy już
duplikatów rekordów skasowanych miękko.

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

## 3. Co faza 03 zmieniła w kodzie

| Miejsce | Zmiana |
|---|---|
| `pbn_api/models/publication.py` | `get_bpp_publication` / `rekord_w_bpp` matchują przez `global_objects` modeli źródłowych zamiast widoku `Rekord` |
| `import_common/core/publikacja.py` | helper `widzacy_manager()`; 6 lookupów matchingu widzi kosz |
| `pbn_integrator/importer/chapters.py` | `znajdz_ksiazke_nadrzedna()` — wydzielony, widzi kosz, wskrzesza |
| `pbn_import/utils/publication_import.py` | `global_objects` + `hard_delete()` przy czyszczeniu przed re-importem |
| `deduplikator_autorow/utils/merge.py` | `wiersze_do_transferu()` — transfer widzi kosz |

**ZOSTAWIONE świadomie na `objects`** (rejestr decyzji w
`src/bpp/tests/test_soft_delete/test_audyt_kategorii_b.py`): ewaluacja,
snapshot odpięć, komparator PBN, REST API, skanowanie do dedupu publikacji.

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
- **Soft-skasowana publikacja NADAL trzyma referencję O2O PROTECT do autora**
  — `Praca_Habilitacyjna.autor`. Dziś oznacza to `ProtectedError` przy próbie
  skasowania autora i jest to zachowanie poprawne (rekord istnieje, nie wolno
  go osierocić), ale faza 04 musi to obsłużyć w UI, a nie zostawić jako gołe
  500.
- **Odwrotne `OneToOne` omija soft-delete** (`autor.praca_habilitacyjna` idzie
  przez `_base_manager`). Naprawione punktowo w `RokHabilitacjiView`; faza 04
  dotyka tej samej relacji, więc trafi na to ponownie.

## 6. Dług nadal otwarty

| Sprawa | Stan |
|---|---|
| **Wycieki ORM (kanarek `xfail(strict=True)`)** | `test_kanarek_orm_join_po_publikacji_ma_predykat_deleted_at` dalej `xfail`. ⚠️ Tabelka 10 wycieków w `reviews/2026-08-07-faza-02-inwentaryzacja-orm.md` NIE jest listą zadań — patrz self-review w tym pliku. Potrzebne narzędzie model-aware (pytające `_meta`), nie rozszerzanie listy nazw |
| **PR upstream `django-easy-audit`** | gałąź gotowa w `~/Programowanie/django-easy-audit`, przetestowana na Django 5.2 i 6.1, **niewypchnięta** — czeka na decyzję o koncie/forku |
| **`bpp-deploy`** | kontrolka „kronika views: N” po `bpp.0499` wypisze 0 i może zmylić operatora |
| Pomiar `0492` i narzutu GiST | wciąż nikt nie zmierzył (dług fazy 01) |
| **Strategia wydania** | ⚠️ **ZMIENIONA 2026-08-08: bramka przesunięta z fazy 04 na fazę 07.** Uzasadnienie w sekcji 4b |

## 7. Proces — co znowu się sprawdziło

- **Mutacja jest jedynym dowodem, że test coś pilnuje.** W fazie 03 pierwsza
  czerwień testu rejestru była `ImportError` — a to nie dowodzi, że asercje
  działają. Dopiero wyłączenie warunku na `deleted_at` pokazało, że tak.
- **`ruff format` na całym katalogu znowu zagarnął cudzy plik.** Formatuj
  tylko własne; cofnięcie kosztowało osobny commit.
- **`make tests-without-playwright` zwraca EXIT 0 mimo porażek** (sprawdzone
  w fazie 02: 7 failed + 2 errors przy zerowym kodzie). Czytaj podsumowanie
  pytest, nie kod wyjścia.
