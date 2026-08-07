# Faza 02 — inwentaryzacja wycieków ORM po dołączeniu publikacji

> Wynik rozszerzenia `RELACJE` w kanarku ORM
> (`src/bpp/tests/test_soft_delete/test_kanarek_orm.py`) o pięć modeli
> publikacji, 2026-08-07. Kanarek zgłosił **14 miejsc**; triage niżej.

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
