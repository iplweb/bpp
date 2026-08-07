# Faza 02 — inwentaryzacja wycieków ORM po dołączeniu publikacji

> Wynik rozszerzenia `RELACJE` w kanarku ORM
> (`src/bpp/tests/test_soft_delete/test_kanarek_orm.py`) o pięć modeli
> publikacji, 2026-08-07. Kanarek zgłosił **14 miejsc**; triage niżej.

---

## ⚠️ SELF-REVIEW (2026-08-07, po napisaniu reszty dokumentu)

**Ten audyt jest niekompletny i w jednym miejscu wprost nieprawdziwy.**
Zostawiam go w całości — poniższe zastrzeżenia są ważniejsze niż tabelka.

### 1. Premisa dokumentu jest FAŁSZYWA na obecnym stanie gałęzi

Sekcja niżej twierdzi, że „zapytania startujące OD publikacji są bezpieczne,
bo `objects` to `BppSoftDeleteManager`". Sprawdzone empirycznie:

| model | `objects` | widzi skasowane? |
|---|---|---|
| `Wydawnictwo_Ciagle` | `Wydawnictwo_Ciagle_Manager` | **TAK** |
| `Wydawnictwo_Zwarte` | `Wydawnictwo_Zwarte_Manager` | **TAK** |
| `Patent` | `BppSoftDeleteManager` | nie |
| `Praca_Doktorska` | `BppSoftDeleteManager` | nie |
| `Praca_Habilitacyjna` | `BppSoftDeleteManager` | nie |

Dwa najważniejsze modele mają wciąż menedżera z fazy 01 (mixin opłat +
`models.Manager`), bo **Task 4 — przeplecenie menedżerów — nie jest jeszcze
zrobiony**. Premisa stanie się prawdziwa dopiero po nim. Do tego czasu
KAŻDE `Wydawnictwo_Ciagle.objects...` w kodzie zwraca też rekordy z kosza.

### 2. Lista nazw relacji jest niekompletna → „14 miejsc" to DOLNA GRANICA

Audyt użył pięciu nazw modeli. Pominął co najmniej:

- **`rekord`** — nazwa FK z modeli-dzieci do publikacji
  (`*_Streszczenie`, `*_Dodatkowy_Tytul`, `*_Zewnetrzna_Baza_Danych`),
- **`wydawnictwo_nadrzedne`** — self-FK rozdział → książka-matka,
- `wydawnictwa_powiazane_set` — relacja odwrotna do powyższej (0 trafień).

Po dołożeniu tych nazw skan daje **120 znalezisk zamiast 14**. Zdanie
„lista jest gotowa, nikt nie musi jej odtwarzać" było więc nieuprawnione.

### 3. …ale te 120 to w większości FAŁSZYWE trafienia — i to jest wniosek o NARZĘDZIU

Nazwa `rekord` jest wieloznaczna i kanarek nie umie tych znaczeń rozróżnić:

1. `*_Autor.rekord` → publikacja (zakres fazy 01),
2. `*_Streszczenie.rekord` i pokrewne → publikacja (**realny zakres fazy 02**),
3. `Cache_Punktacja_Autora.rekord` → widok `Rekord`, **już przefiltrowany**
   migracją 0497 — czyli bezpieczne,
4. `request.GET.get("rekord__id__exact")`, `cleaned_data.get("rekord")` —
   parametry HTTP i formularzy, w ogóle nie ORM.

**Sedno:** kanarek ORM jest matcherem NAZW, a nie modeli. W fazie 01 działał
świetnie, bo nazwy były dystynktywne (`autorzy_set`, `wydawnictwo_ciagle_autor`
— nic innego się tak nie nazywa). W fazie 02 nazwy to zwykłe słowa (`patent`,
`rekord`, `wydawnictwo_ciagle`), więc precyzja narzędzia się załamuje. To nie
jest usterka do załatania listą wyjątków — to granica metody.

Uczciwe narzędzie dla fazy 02 musiałoby rozwiązywać ścieżkę lookupu wobec
metadanych Django (`_meta`) i pytać, czy faktycznie dochodzi do tabeli objętej
soft-delete — czyli działać tak, jak kanarek KATALOGOWY działa na `pg_depend`.
To jest osobne narzędzie, nie parametr istniejącego.

### 4. Błąd w tabeli: pozycja #1 ma odwróconą wymowę

Wpis dla `usun_zrodla_bez_publikacji` jest zatytułowany **„KASUJE ŹRÓDŁA"**,
co sugeruje utratę danych. Faktyczny kierunek jest odwrotny i łagodny:
`filter(wydawnictwo_ciagle__isnull=True)` **nie znajdzie** źródła, którego
publikacje są w koszu, więc takie źródło NIE zostanie skasowane. Skutek to
zalegające śmieci, nie utrata danych.

### Co z tego wynika dla decyzji o fazie 03

Sam podział (faza 02 = warstwa bazodanowa, faza 03 = wywołania ORM) uważam
nadal za słuszny, a `xfail(strict=True)` spełnia swoją rolę. Ale faza 03 NIE
powinna traktować tabelki niżej jako gotowej listy zadań — powinna zacząć od
zbudowania narzędzia model-aware, bo inaczej utonie w fałszywych trafieniach.

---

## Dlaczego to nie jest to samo ryzyko, co w fazie 01

Dla publikacji zagrożenie jest skierowane **odwrotnie** niż dla autorstw.
Zapytania startujące OD publikacji są bezpieczne — `Wydawnictwo_Ciagle.objects`
to `BppSoftDeleteManager`, który sam dokłada `deleted_at__isnull=True`.
Przecieka dołączenie **DO** publikacji od strony słownika lub relacji
(`Zrodlo`, `Charakter_Formalny`, `Wydawca`…), bo tam żaden nasz manager się
nie włącza — liczy się surowa tabela.

## Prawdziwe wycieki (10)

Wszystkie to `Count()`/`filter()` po odwrotnej relacji do publikacji, bez
predykatu `deleted_at`.

| # | Miejsce | Co robi | Skutek wycieku |
|---|---|---|---|
| 1 | `bpp/management/commands/usun_zrodla_bez_publikacji.py:23` | `Zrodlo.objects.filter(wydawnictwo_ciagle__isnull=True)` | **KASUJE ŹRÓDŁA.** Źródło, którego wszystkie publikacje są w koszu, nie wygląda na puste → NIE zostanie skasowane. Odwrotnie niż groźnie, ale wynik i tak niezgodny z intencją |
| 2 | `bpp/admin/zrodlo.py:188` | to samo, akcja adminowa „usuń źródła bez prac" | jw. — decyzja o kasowaniu na podstawie zawyżonego licznika |
| 3 | `bpp/admin/zrodlo.py:217` | `Count("wydawnictwo_ciagle", distinct=True)` — kolumna „liczba prac" | operator widzi zawyżoną liczbę |
| 4 | `bpp/admin/filters.py:270` | `Count("wydawnictwo_ciagle")` — filtr „ma prace / nie ma prac" | źródło z samymi skasowanymi pracami trafia do „ma prace" |
| 5 | `admin_dashboard/views/charakter_stats.py:68` | `Count("wydawnictwo_ciagle")` + `Count("wydawnictwo_zwarte")` | statystyki charakterów zawyżone |
| 6 | `deduplikator_zrodel/operations.py:65` | `Count("wydawnictwo_ciagle")` — dobór kandydatów | do deduplikacji wchodzą źródła bez żywych prac |
| 7 | `deduplikator_zrodel/utils.py:72` | jw. | jw. |
| 8 | `deduplikator_zrodel/views.py:83` | `Count("main_zrodlo__wydawnictwo_ciagle")` do pól `_main_live_pub` / `_dup_live_pub` | **nazwa pola mówi `live`, a liczy też skasowane** |
| 9 | `komparator_pbn/views.py:163` | `Count("wydawnictwo_ciagle")` przy źródłach `DELETED` w PBN | zawyżony raport |
| 10 | `przemapuj_zrodla_pbn/views.py:409` | `Count("wydawnictwo_ciagle")` → `liczba_rekordow` | jw. |

Wzorzec naprawy jest jednolity i znany z fazy 01:

```python
Count("wydawnictwo_ciagle", filter=Q(wydawnictwo_ciagle__deleted_at__isnull=True))
```

⚠️ Dla wariantu `filter(wydawnictwo_ciagle__isnull=True)` (#1, #2) `Count(...)
FILTER` nie wystarcza — trzeba przejść na `annotate(...)` + `filter(licznik=0)`,
inaczej warunek na odwrotnej relacji zawęzi zbiór źródeł zamiast policzyć zero.

## Fałszywe trafienia (4) — do wpisu w `DOZWOLONE` albo do zawężenia matchera

Powstały dlatego, że nazwy relacji fazy 02 są **zwykłymi słowami** (`patent`,
`wydawnictwo_ciagle`), a nie dystynktywnymi jak `autorzy_set` czy
`wydawnictwo_ciagle_autor` z fazy 01.

| Miejsce | Dlaczego fałszywe |
|---|---|
| `django_bpp/sitemaps.py:110` | pętla po liście etykiet URL-i; literał `"patent"` trafia w gałąź „pętla po nazwach relacji" |
| `ewaluacja_optymalizacja/utils.py:183` | `dict(wydawnictwo_ciagle=isinstance(...), …)` — słownik flag, nie lookup ORM (`dict` jest w `WYWOLANIA_ORM`) |
| `pbn_api/…/pbn_test_wysylka_interaktywna.py:122` | `options.get("wydawnictwo_zwarte")` — opcja CLI (`get` jest w `WYWOLANIA_ORM`) |
| `pbn_api/…/pbn_test_wysylka_interaktywna.py:123` | jw., `wydawnictwo_ciagle` |

## Rozstrzygnięcie zakresu

Plan fazy 02 obejmuje warstwę **bazodanową** (modele, widoki, triggery,
ograniczenia, menedżery). Audyt wywołań ORM w imporcie/dedup/PBN jest w
podsumowaniu planu przypisany **fazie 03** („audyt `global_objects`
w imporcie/dedup/PBN → faza 03”), a handoff §7 wymienia dla fazy 03 dług
dotyczący `deduplikator_autorow`.

Rozwiązanie: kanarek ORM ma teraz **dwa** testy zamiast jednego.

| Test | Relacje | Stan |
|---|---|---|
| `test_kanarek_orm_join_po_autorstwie_ma_predykat_deleted_at` | faza 01 (`autorzy_set`, `*_autor`) | ZIELONY — ochrona nienaruszona |
| `test_kanarek_orm_join_po_publikacji_ma_predykat_deleted_at` | faza 02 (5 modeli publikacji) | `xfail(strict=True)` — dług fazy 03 |

Podział jest istotny: wrzucenie wszystkiego do jednego `xfail`-a wyłączyłoby
także ochronę wywalczoną w fazie 01.

`strict=True` jest tu mechanizmem wymuszającym, nie ozdobą: gdy faza 03
naprawi te miejsca, test zacznie padać jako XPASS i zmusi do zdjęcia
markera. Bez `strict` naprawa przeszłaby niezauważona, a kanarek zostałby
wyłączony na zawsze — dokładnie ta pułapka („pusty wynik ≠ potwierdzenie”)
jest opisana w handoffie fazy 01. Ten sam wzorzec faza 01 zastosowała wobec
fazy 02 w `test_cache/test_soft_delete_preconditions.py`.

Kanarek **katalogowy** (widoki) został rozszerzony i jest w pełni ZIELONY —
to zakres fazy 02 i został domknięty.
