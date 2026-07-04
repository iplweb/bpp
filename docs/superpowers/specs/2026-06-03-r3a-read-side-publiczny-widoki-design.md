# R3a — read-side publiczny: widoki listujące Rekord/Sumy per-uczelnia

Spec. Gałąź `feature/multi-hosted-config`. Data 2026-06-03.
Powiązane: `docs/superpowers/2026-06-03-audyty-multihosted-4x.md` (Audyt 3/4b),
`docs/superpowers/specs/2026-06-03-per-uczelnia-sloty-read-side-design.md` (R1).
Para: R3b (publiczne autocomplety) — osobny spec.

## Problem

R1 zawęził po uczelni *cache slotów* (`Cache_Punktacja_*`). Publiczne widoki
czytające `Rekord`/`Sumy` **wprost** nadal agregują międzyuczelniano — na domenie
uczelni B użytkownik widzi rekordy/autorów uczelni A. Strona główna
(`get_uczelnia_context_data`, `bpp/views/browse.py:86`) JUŻ scopuje, ale pięć
innych publicznych ścieżek nie. To niespójność widoczna dla użytkownika.

## Reguła atrybucji (decyzja usera)

Dwie świadomie różne reguły — różne kategorie danych:

1. **Rekordy** (raport-uczelnia, browse, OAI): rekord należy do uczelni U jeśli
   którakolwiek z jednostek zapisanych na autorstwie należy do U:
   `Rekord …filter(autorzy__jednostka__uczelnia=U).distinct()`.
   **BEZ `skupia_pracownikow`** — identyczna z regułą strony głównej
   (`uczelnia.jednostka_set.all()` → `autorzy__jednostka__in`). Włącza obcą
   jednostkę uczelni. To „jedna z jednostek do których autor jest przypisany".
2. **Ranking** (`Sumy`): autor należy do rankingu uczelni U jeśli jest TAM
   **aktualnie zatrudniony**: `autor__aktualna_jednostka__uczelnia=U`. Ranking to
   lista obecnych pracowników, więc semantyka „aktualny pracownik", nie
   „kiedykolwiek związany".

## Helper współdzielony

Nowy moduł `src/bpp/util/uczelnia_scope.py` (lub `bpp/models/cache/` jeśli
import-cykl) — jedno źródło reguły rekordowej + guard single-install:

```python
def tylko_jedna_uczelnia() -> bool:
    # fast-track jak IPunktacjaCacher._uczelnie_do_przeliczenia
    return Uczelnia.objects.count() == 1

def scope_rekord_do_uczelni(qs, uczelnia):
    """Zawęź queryset Rekordów do uczelni oglądającego.

    No-op gdy brak uczelni (brak mapowania Site→Uczelnia) albo gdy w systemie
    jest dokładnie jedna uczelnia (wynik identyczny — pomijamy kosztowny JOIN
    przez M2M autorzy + DISTINCT).
    """
    if uczelnia is None or tylko_jedna_uczelnia():
        return qs
    return qs.filter(autorzy__jednostka__uczelnia=uczelnia).distinct()
```

**Wydajność (obawa usera):** na single-install filtr byłby no-op, ale JOIN+DISTINCT
na `Rekord` (100k+) kosztuje. `tylko_jedna_uczelnia()` short-circuituje → zero
narzutu, wynik identyczny. `count()` na małej tabeli `bpp_uczelnia` jest tani;
zcache'ować tylko jeśli profiling pokaże potrzebę.

Ranking nie używa tego helpera (inny model `Sumy`, lookup
`autor__aktualna_jednostka__uczelnia`), ale **używa tego samego guardu**
`tylko_jedna_uczelnia()` przed dołożeniem filtra.

## Zmiany w widokach

### 1. Raport „cała uczelnia" — `nowe_raporty/poziomy.py:_base_uczelnia`
Dziś `Rekord.objects.all()` / `.filter(autorzy__afiliuje=True)`, ignoruje
przekazany `obiekt` (=Uczelnia z `views.py:284`). Fix: `scope_rekord_do_uczelni(qs, obiekt)`
zachowując gałąź `afiliuje`. To najbardziej rażący przypadek (jawnie „raport TEJ
uczelni", a zwraca wszystkie).

### 2. Browse lata/rok — `bpp/views/browse.py` `LataView`, `RokView`
`LataView` (`:491-498,502`): lista lat (`values("rok").annotate(count)`) + `count()`.
`RokView` (`:526-556`): `filter(rok=year)` + nawigacja prev/next + `total_count`.
Owinąć **każde** zapytanie `Rekord` helperem (uczelnia z `get_for_request(request)`).
Count liczony na distinct rekordach.

### 3. OAI-PMH — `bpp/views/oai.py` `OAIView`
Bazowy `Rekord.objects.all().exclude(...)` (`:243-247`); `uczelnia` już rozwiązana
w `:187`. Zawęzić bazowy qs helperem PRZED przekazaniem do `BPPOAIDatabase`.
Harvester domeny A nie pobiera rekordów B.

### 4. Ranking autorów — `ranking_autorow/views.py` `_apply_location_filters`
Dziś filtr `jednostka__uczelnia` aplikowany TYLKO gdy user ręcznie wybierze
jednostkę/wydział (`:265-291`). Fix: **bezwarunkowo** (gdy `not tylko_jedna_uczelnia()`)
`qset.filter(autor__aktualna_jednostka__uczelnia=U)`. Istniejące zachowanie:
`exclude(autor__aktualna_jednostka=None)` (`:255`) zostaje; toggle
`tylko_afiliowane` (`jednostka__skupia_pracownikow=True, afiliuje=True`) bez zmian.

### 5. Multiwyszukiwarka — BEZ ZMIAN wyników (decyzja usera)
`mymultiseek.py` nie filtruje bazowego querysetu. Zawężenie realizują publiczne
autocomplety (spec R3b) — pickery jednostka/wydział/autor ograniczone do uczelni.
Świadomy kompromis: wyszukiwanie bez kryterium jednostki (tytuł/rok) zwróci
rekordy wszystkich uczelni. Multiseek zachowuje charakter „globalny".

## Niezmienniki i przypadki brzegowe

- **Single-install:** `tylko_jedna_uczelnia()` → wszystkie helpery no-op, wyniki
  i wydajność identyczne jak dziś. Testy regresyjne `<=` muszą przejść.
- **`uczelnia is None`** (brak mapowania Site→Uczelnia, np. CLI render): helper
  zwraca qs bez zmian — zachowuje obecne zachowanie, zero wyjątków.
- **`.distinct()`** obowiązkowy (JOIN przez `autorzy` mnoży wiersze).

## Testy

Per widok, 2 uczelnie (A, B) z rozłącznymi jednostkami/autorami/rekordami:
- raport-uczelnia: raport poziomu uczelnia A nie zawiera rekordów B.
- browse lata/rok: lista lat i prac na domenie A liczona tylko z rekordów A;
  count zgodny.
- OAI: feed domeny A nie zawiera identyfikatorów rekordów B.
- ranking: domena A listuje tylko autorów z `aktualna_jednostka` w A.
- **Invariant single-install:** przy 1 uczelni każdy widok zwraca to samo co
  przed zmianą (guard no-op) — test, że liczby/listy bez zmian.

## Poza zakresem
- Multiseek result-filter (świadomie wyłączony, patrz #5).
- Publiczne autocomplety (spec R3b).
- API REST `api_v1/viewsets/*` (maszynowe, osobny temat).
- Federacja optymalizacji (świadomie olana).
