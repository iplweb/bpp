# Spec: API zakresów wyszukiwania autorów (`AutorQuerySet`)

- Data: 2026-07-02
- Gałąź: `feature/multi-hosted-config`
- Status: projekt do akceptacji

## 1. Problem

Kod ma różne potrzeby przy wyszukiwaniu autorów i dziś realizuje je trzema
niespójnie nazwanymi, rozproszonymi mechanizmami:

- `AutorAktualnieZatrudnionyNaUczelni` (autocomplete) — filtr
  `aktualna_jednostka__uczelnia`,
- `PublicAutorAutocomplete` + `globalne_wyszukiwanie_autora(uczelnia=…)` —
  reguła „obecnie LUB historycznie związany z uczelnią" (w kodzie opisana jako
  „R3a/R3b" — żargon, którego autor projektu nie rozpoznaje i który ma zniknąć),
- staffowy `AutorAutocomplete` — bez zawężenia.

Semantyki są poprawne i sprawdzone, ale porozrzucane po mixinie
(`UczelniaScopedAutocompleteMixin`), funkcji serwisowej
(`search_services.globalne_wyszukiwanie_autora`) i trzech klasach widoków.
To rozproszenie było źródłem niejasności przy audycie izolacji single-host
(znaleziska #4/#5 — „czy to zamierzone zawężenie, czy regresja").

## 2. Cel

Jedno, samoopisowe źródło prawdy dla trzech zakresów wyszukiwania autora,
konsumowane przez nasz własny kod (autocomplete, global-search, przyszłe
widoki). NIE publiczne REST API.

Trzy zakresy:

1. **AKTUALNI** — autorzy aktualnie zatrudnieni w danej uczelni.
2. **KIEDYKOLWIEK** — autorzy związani z uczelnią obecnie LUB historycznie.
3. **WSZYSCY** — wszyscy autorzy w systemie, bez zawężenia.

## 3. Kluczowe rozróżnienie pojęciowe

Projekt rozdziela dwa pojęcia, które dziś są zlepione pod „per-uczelnia":

- **Izolacja multi-host** — separacja danych między najemcami. W single-host
  MUSI być no-op (helpery `scope_rekord_do_uczelni` / `tylko_jedna_uczelnia`
  z `bpp/util/uczelnia_scope.py`). Dotyczy przeglądania rekordów/jednostek.
- **Wybór kategorii autora** — świadoma decyzja produktowa „których autorów
  zaoferować". Obowiązuje TAK SAMO w single- i multi-host (AKTUALNI ≠ WSZYSCY
  nawet przy jednej uczelni).

Trzy zakresy z tego spec-u to **wybór kategorii autora**. Dlatego NIE
przechodzą przez guard `tylko_jedna_uczelnia()` — to celowe filtry semantyczne,
nie izolacja. To formalizuje wcześniejszą decyzję „zostaw #4/#5".

## 4. Projekt

### 4.1. `AutorQuerySet`

Metody kategorii żyją na querysecie `Autora` (idiomatyczny Django: wiedza „jak
wyszukać autorów" należy do `Autor.objects`, jest odkrywalna i łańcuchowalna).

```python
class AutorQuerySet(models.QuerySet):
    def aktualnie_zatrudnieni(self, uczelnia):      # zakres 1
        if uczelnia is None:
            return self.none()
        return self.filter(
            aktualna_jednostka__uczelnia=uczelnia,
            aktualna_jednostka__skupia_pracownikow=True,
        )

    def kiedykolwiek_zwiazani(self, uczelnia):      # zakres 2
        if uczelnia is None:
            return self.none()
        return self.filter(
            Q(aktualna_jednostka__uczelnia=uczelnia)
            | Q(autor_jednostka__jednostka__uczelnia=uczelnia)
        ).distinct()

    # zakres 3 (WSZYSCY) = zwykłe Autor.objects.all() — bez metody
```

Uzasadnienie reguł (oparte o istniejące pola modelu):

- **AKTUALNI**: `aktualna_jednostka__uczelnia=U` **oraz**
  `aktualna_jednostka__skupia_pracownikow=True`. `skupia_pracownikow` to
  istniejący wyróżnik „realnej" jednostki (użyty już w `uczelnia.py:876`),
  wyklucza jednostkę obcą (`Uczelnia.obca_jednostka`, z definicji
  `skupia_pracownikow=False`) i inne techniczne.
- **KIEDYKOLWIEK**: `aktualna_jednostka__uczelnia=U` LUB
  `autor_jednostka__jednostka__uczelnia=U` (historyczne wpisy
  `Autor_Jednostka`), z `.distinct()`. To reguła, którą dziś realizują
  `PublicAutorAutocomplete` i `globalne_wyszukiwanie_autora`.
- **WSZYSCY**: `Autor.objects.all()` — brak zawężenia, bez osobnej metody
  (YAGNI).

### 4.2. Podpięcie managera

```python
class AutorManager(
    FulltextSearchMixin, models.Manager.from_queryset(AutorQuerySet)
):
    ...
```

`from_queryset` kopiuje metody querysetu na manager, zachowując dziś istniejący
`FulltextSearchMixin`. `fulltext_filter` (orm.py:81) robi `self.filter(...)` i
zwraca queryset — po podpięciu `from_queryset` będzie to `AutorQuerySet`, więc
kategorie **łańcuchują się po fulltekście**:

Refactor MUSI zachować dzisiejsze składniki `AutorManager` (ciało `...` powyżej):
`create_from_string`, override `fulltext_annotate` oraz atrybut
`fts_enable_websearch_on_minus_or_quote = False` (autor.py:58, 85-86). MRO:
`AutorManager → FulltextSearchMixin → (Manager z AutorQuerySet) → Manager` —
`FulltextSearchMixin` nie definiuje `get_queryset`, `AutorQuerySet` nie ma
`fulltext_filter`, więc kolizji brak.

```python
Autor.objects.aktualnie_zatrudnieni(u)                      # zakres 1
Autor.objects.fulltext_filter(q).kiedykolwiek_zwiazani(u)   # zakres 2 + szukanie
Autor.objects.all()                                         # zakres 3
```

Kierunek łańcucha: kategoria PO fulltekście (`fulltext_filter(q).kiedykolwiek…`).
Kierunek odwrotny (`fulltext_filter` po kategorii) nie jest wymagany — konsumenci
najpierw szukają, potem zawężają.

### 4.3. Cienki refactor konsumentów

Delegują do metod managera. Zakres 2 (KIEDYKOLWIEK) i zakres 3 (WSZYSCY) — bez
zmiany semantyki. Zakres 1 (AKTUALNI) **zaostrza** dzisiejsze zawężenie
`AutorAktualnieZatrudnionyNaUczelni` (#5) o `skupia_pracownikow=True`: autorzy,
których aktualna jednostka jest obca/techniczna, przestają być zwracani. To
świadoma korekta (nazwa ma znaczyć „faktycznie zatrudnieni"), zaakceptowana —
NIE no-op.

| Konsument | Zakres |
|---|---|
| `AutorAktualnieZatrudnionyNaUczelni.get_queryset` | 1 AKTUALNI |
| `PublicAutorAutocomplete.get_queryset` | 2 KIEDYKOLWIEK |
| `globalne_wyszukiwanie_autora(uczelnia=U)` | 2 KIEDYKOLWIEK |
| staffowy `AutorAutocomplete` | 3 WSZYSCY |

`UczelniaScopedAutocompleteMixin`/`uczelnia_lookups` i lokalne reguły w tych
widokach są zastępowane wywołaniem metody zakresu. Krypticzne „R3a/R3b" usuwane.

## 5. Decyzje

- **Zakres 3 (WSZYSCY) i izolacja multi-host.** WSZYSCY oznacza cross-tenant
  (wszyscy autorzy wszystkich uczelni). W multi-host dostępne WYŁĄCZNIE dla
  zalogowanego personelu — staffowy `AutorAutocomplete` już jest za
  `GroupRequiredMixin`, więc mapowanie to spełnia. Publiczne powierzchnie w
  multi-host używają najwyżej zakresu 2. Zakres 3 nie może zasilać żadnego
  publicznego endpointu multi-host.
- **`uczelnia=None` w zakresach 1/2 → fail-closed** (`self.none()`). To ZMIANA
  względem dzisiejszego zachowania OBU konsumentów zakresowych:
  `PublicAutorAutocomplete` (authors.py:231) i `AutorAktualnieZatrudnionyNaUczelni`
  (authors.py:271-273) przy braku uczelni robią dziś fail-open (pokaż wszystko).
  Świadomie wybieramy fail-closed dla czystego, bezpiecznego API — brak ustalonej
  uczelni nie może „przeciekać" pełną listą.
- **Bez guardu `tylko_jedna_uczelnia()`** — patrz §3. Zakresy działają
  identycznie w single- i multi-host.
- **Zachowanie #4/#5 bez zmian** — dostają odpowiednio zakres 2/1; to
  wcześniejsza decyzja „zostaw".

## 6. Testy (TDD)

- `aktualnie_zatrudnieni(u)`: zwraca autora z `aktualna_jednostka` w U i
  `skupia_pracownikow=True`; NIE zwraca autora z aktualną jednostką obcą
  (`skupia_pracownikow=False`); NIE zwraca autora tylko historycznie związanego.
- `kiedykolwiek_zwiazani(u)`: zwraca autora historycznie związanego (wpis
  `Autor_Jednostka`) mimo braku `aktualna_jednostka`; zwraca też aktualnie
  zatrudnionego; brak duplikatów (`.distinct()`).
- `uczelnia=None` → obie metody zwracają pusty queryset (fail-closed).
- Łańcuch `fulltext_filter(q).kiedykolwiek_zwiazani(u)` zawęża i po tekście, i
  po zakresie.
- Multi-host: `aktualnie_zatrudnieni(U1)` nie zwraca autora zatrudnionego w U2.
- Refactor konsumentów: istniejące testy autocomplete (w tym
  `test_single_host_parity`, `test_isolation`) pozostają zielone. Zachowanie #4
  (zakres 2) niezmienione. Zachowanie #5 (zakres 1) **zaostrzone** o
  `skupia_pracownikow=True` — jeśli istnieje test asertujący, że autor z aktualną
  jednostką obcą pojawia się w #5, wymaga aktualizacji (należy zweryfikować przy
  implementacji; prawdopodobnie brak takiego testu).

## 7. Poza zakresem

- Publiczne REST API (`api_v1`) — nie w tym spec-ie.
- Zmiana zachowania #4/#5 — świadomie zostawione.
- Walidacja dat zatrudnienia (od/do) w zakresie 1 — obecnie „aktualnie
  zatrudniony" opiera się o `aktualna_jednostka` + `skupia_pracownikow`, bez
  osobnej walidacji dat.
- Refactor `uczelnia_scope.py` / izolacji rekordów — osobne pojęcie (§3).
- `Uczelnia.autorzy_z_uczelni()` (uczelnia.py:870-878) — czwarty wariant o
  zbliżonej semantyce (zakres 2, ale z `skupia_pracownikow=True` i BEZ gałęzi
  `aktualna_jednostka`). Świadomie POZA tą unifikacją w tej iteracji: ma inne
  zastosowanie i inną regułę. Kandydat do objęcia w kolejnym kroku, gdy zakresy
  się ustabilizują — odnotowane, by „jedno źródło prawdy" nie było fałszywą
  obietnicą.

## 8. Ryzyka

- Refactor `AutorManager` na `from_queryset`: sprawdzić MRO managera i że żaden
  kod nie polega na dzisiejszym typie/klasie managera. Standardowy wzorzec
  Django, ryzyko niskie.
- `autor_jednostka` w zakresie 2 to potencjalnie duży JOIN — `.distinct()`
  wymagane; sprawdzić liczbę zapytań w testach autocomplete (istnieją asercje
  query-count w `test_browse`).
