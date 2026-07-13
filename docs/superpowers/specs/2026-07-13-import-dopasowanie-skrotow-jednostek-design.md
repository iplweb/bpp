# Import pracowników: dopasowanie jednostek po skrótach słów

Data: 2026-07-13
Status: zatwierdzony (do implementacji)
Branch: `feat/import-skroty-jednostek`

## Problem

Import pracowników nie dopasowuje jednostek, gdy w pliku Excel nazwa jest
**skrócona słowo-po-słowie** (skróty z kropką), a w bazie zapisana pełna nazwa.

Przykład zgłoszony przez użytkownika:

| pole | wartość |
|---|---|
| baza `nazwa` | `Zakład Pielęgniarstwa Anestezjologicznego i Intensywnej Opieki Medycznej` |
| baza `skrot` | `Zakł. Piel. Anestezj.` |
| Excel | `Zakład Piel. Anestezjol. i Intens. Opieki Medycznej` |

Zmierzone podobieństwo trigramowe (`pg_trgm.similarity`) formy z Excela:

- do `nazwa` → **0.629**
- do `skrot` → **0.347**

Próg auto-dopasowania `PROG_ZGADYWANIA_JEDNOSTKI = 0.7` — oba poniżej, więc
jednostka wpada w status `brak` (nie dopasowuje się).

## Diagnoza

1. **Rozwodnienie długością.** Skrócone słowa (`Piel.` = `Pielęgniarstwa`,
   `Anestezjol.` = `Anestezjologicznego`, `Intens.` = `Intensywnej`) mają
   znacznie mniej trigramów niż pełne słowa, co obniża całościowe podobieństwo.
2. **`skrot` bywa jeszcze krótszy.** Pole `Jednostka.skrot` to również skrócona
   forma nazwy z kropkami (np. `Zakł. Chemii Prod. Poch. Natural.`), ale bywa
   **agresywniej** skrócona niż forma z pliku (tu: 3 słowa vs 7). Dlatego trigram
   do `skrot` jest *gorszy*, nie lepszy — matchowanie po samym `skrot` nie
   rozwiązuje problemu.
3. **`(WNoZ)` to skrót WYDZIAŁU**, nie jednostki. W UI jednostka renderuje się
   jako `nazwa (skrót wydziału)`; `WNoZ` = `Wydział Nauk o Zdrowiu`. W bazie pole
   `nazwa` **nie** zawiera tego nawiasu (potwierdzone: tylko 1 jednostka w bazie
   ma `(` w nazwie). Plik z Excela też nie zawiera nawiasu. Nawias jest więc
   artefaktem displayu — matcher zdejmuje go defensywnie, ale nie jest źródłem
   problemu.

Kluczowa obserwacja: **prefiksowe wyrównanie słów do `nazwa` jest idealne** —
`piel`⊂`pielęgniarstwa`, `anestezjol`⊂`anestezjologicznego`,
`intens`⊂`intensywnej`, pozostałe słowa równe; 7/7 słów pliku, kolejność
zachowana, ta sama liczba słów.

## Cel

Dopasować jednostkę z pliku do rekordu w bazie także wtedy, gdy słowa są
skrócone — bez słownika skrótów i bez psucia dotychczasowych dopasowań.

### Non-goals

- Brak słownika ekspansji skrótów (`Piel.`→`Pielęgniarstwa`) — polska fleksja
  jest zbyt bogata, słownik byłby brittle.
- Brak globalnego obniżenia progu trigramowego — generuje fałszywe auto-sugestie
  na innych jednostkach.
- Brak zmian w twardej ścieżce (`matchuj_jednostke`) i w modelu danych (bez
  migracji).
- Poza zakresem: naprawa `wytnij_skrot`, które traktuje dowolny nawias w *danych
  wejściowych* jako skrót jednostki (istotne dopiero gdyby pliki zawierały
  `(skrót wydziału)` — dziś nie zawierają).

## Decyzje projektowe (zatwierdzone z użytkownikiem)

1. **Status trafienia = `zgadywanie`** (auto-wybór, ale zawsze do weryfikacji na
   ekranie). Skrót jest z natury niejednoznaczny — nigdy `twardy`. Spójne z
   obecną filozofią (trigram/fragment → zawsze `zgadywanie`).
2. **Ścisłość = elastyczny podciąg + guard pokrycia.** Słowa z pliku muszą być
   uporządkowanym podciągiem słów pola (każde jako prefiks), z guardem pokrycia
   ≥60% słów pola (krótki skrót nie matchuje długiej obcej nazwy).
3. **Porównanie do OBU pól** `nazwa` i `skrot`, prefiks **dwukierunkowy** (skrót
   może być po dowolnej stronie).

## Projekt

### Umiejscowienie

Plik `src/import_common/core/jednostka.py`. Nowa funkcja `dopasuj_po_skrocie`,
wpięta jako **fallback** w istniejące `sklasyfikuj_jednostke`, z której korzysta
też ścieżka „niepełna nazwa" (`sklasyfikuj_jednostke_niepelna`). Twarda ścieżka
`matchuj_jednostke` bez zmian.

### Kolejność w `sklasyfikuj_jednostke`

1. exact (`matchuj_jednostke`) → `twardy` *(bez zmian)*
2. **jedno** zapytanie SQL: top-K jednostek z puli afiliacyjnej wg
   `Greatest(TrigramSimilarity("nazwa"), TrigramSimilarity("skrot"))`, z dolnym
   progiem `TRIGRAM_FLOOR` i limitem `TOP_K`
3. jeśli najlepszy trigram ≥ `prog` (0.7) → `zgadywanie` *(zachowanie dzisiejsze)*
4. **NOWE:** `dopasuj_po_skrocie(nazwa_norm, kandydaci)` na tych K kandydatach →
   jeśli trafi → `zgadywanie`
5. wpp → `brak`

Cały fallback (kroki 2–4) to **jedno** zapytanie do bazy; alignment liczony w
Pythonie na maks. `TOP_K` wierszach. Uruchamia się tylko dla wierszy, które nie
trafiły twardo.

### Stałe (strojone w jednym miejscu)

```python
TRIGRAM_FLOOR = 0.25   # dolny próg kandydatów do prefiltru (perf + odsiew szumu)
TOP_K = 50             # ilu kandydatów materializujemy do alignmentu w Pythonie
MIN_SLOW_PLIKU = 2     # <2 słowa → za dwuznaczne na dopasowanie po skrócie
MIN_POKRYCIE = 0.6     # min. udział dopasowanych słów pola
```

### Szkic `sklasyfikuj_jednostke` (po zmianie)

```python
def sklasyfikuj_jednostke(nazwa, wydzial=None, *, prog=PROG_ZGADYWANIA_JEDNOSTKI):
    if not nazwa:
        return None, STATUS_JEDNOSTKA_BRAK, None
    nazwa_norm = normalize_nazwa_jednostki(nazwa)
    if not nazwa_norm:
        return None, STATUS_JEDNOSTKA_BRAK, None

    try:
        j = matchuj_jednostke(nazwa, wydzial=wydzial)
        if j is not None:
            return j, STATUS_JEDNOSTKA_TWARDY, None
    except (Jednostka.DoesNotExist, Jednostka.MultipleObjectsReturned):
        pass

    kandydaci = list(
        _pula_afiliacyjna()
        .annotate(
            sim=Greatest(
                TrigramSimilarity("nazwa", nazwa_norm),
                TrigramSimilarity("skrot", nazwa_norm),
            )
        )
        .filter(sim__gte=TRIGRAM_FLOOR)
        .order_by("-sim")[:TOP_K]
    )

    if kandydaci and kandydaci[0].sim is not None and kandydaci[0].sim >= prog:
        best = kandydaci[0]
        return best, STATUS_JEDNOSTKA_ZGADYWANIE, float(best.sim)

    trafienie = dopasuj_po_skrocie(nazwa_norm, kandydaci)
    if trafienie is not None:
        return (
            trafienie,
            STATUS_JEDNOSTKA_ZGADYWANIE,
            float(trafienie.sim) if trafienie.sim is not None else None,
        )
    return None, STATUS_JEDNOSTKA_BRAK, None
```

> Uwaga na zgodność: dawniej trigram brał globalny `.first()` bez dolnego progu.
> Po zmianie top-K z `TRIGRAM_FLOOR` w praktyce zachowuje ścieżkę ≥`prog`
> (0.7 ≥ 0.25, więc najlepszy zawsze przechodzi filtr i jest `[0]`). Ścieżka
> `brak` różni się tylko tym, że może zostać *podniesiona* do `zgadywanie` przez
> nowy alignment.

### Algorytm wyrównania

```python
from unidecode import unidecode

def _slowa(s):
    """Nazwa/skrot → lista znormalizowanych słów: bez nawiasowego skrótu
    wydziału, lower, bez ogonków (unidecode), bez końcowej kropki i brzegowej
    interpunkcji; puste tokeny pominięte."""
    baza, _ = wytnij_skrot(s or "")          # zdejmij '(...)' jeśli jest
    out = []
    for w in baza.split():
        w = unidecode(w).lower().strip(".,;:„”\"'()-")
        if w:
            out.append(w)
    return out

def _para_prefiksowa(a, b):
    """True gdy a==b lub jedno jest prefiksem drugiego (dwukierunkowo).
    Tokeny ≤2 znaki (np. 'i', 'ii', 'im') wymagają RÓWNOŚCI, nie prefiksu —
    inaczej 'i' połyka 'intensywnej'."""
    if len(a) <= 2 or len(b) <= 2:
        return a == b
    return a.startswith(b) or b.startswith(a)

def _liczba_dopasowanych(slowa_pliku, slowa_pola):
    """Greedy: słowa_pliku jako uporządkowany podciąg słów_pola z relacją
    prefiksową. Zwraca liczbę dopasowanych pozycji pola (== len(slowa_pliku)),
    albo None gdy któreś słowo pliku nie znalazło pary."""
    i = 0
    for wp in slowa_pliku:
        while i < len(slowa_pola) and not _para_prefiksowa(wp, slowa_pola[i]):
            i += 1
        if i >= len(slowa_pola):
            return None
        i += 1
    return len(slowa_pliku)

def dopasuj_po_skrocie(
    nazwa, kandydaci, *, min_slow=MIN_SLOW_PLIKU, min_pokrycie=MIN_POKRYCIE
):
    """Najlepszy kandydat wg prefiksowego wyrównania słów do `nazwa`/`skrot`,
    albo None. Kandydaci to instancje Jednostka z adnotacją `.sim` (trigram)."""
    slowa_pliku = _slowa(nazwa)
    if len(slowa_pliku) < min_slow:
        return None
    najlepszy, najlepszy_klucz = None, None
    for kand in kandydaci:
        for pole in (kand.nazwa, kand.skrot):
            slowa_pola = _slowa(pole or "")
            if not slowa_pola:
                continue
            dop = _liczba_dopasowanych(slowa_pliku, slowa_pola)
            if dop is None:
                continue
            pokrycie = dop / len(slowa_pola)
            if pokrycie < min_pokrycie:
                continue
            klucz = (pokrycie, float(kand.sim or 0.0))
            if najlepszy_klucz is None or klucz > najlepszy_klucz:
                najlepszy, najlepszy_klucz = kand, klucz
    return najlepszy
```

### Konsekwencje reguł (weryfikacja na danych)

- **Zgłoszony przypadek:** Excel(7 słów) vs `nazwa`(7 słów) → wszystkie słowa
  pliku dopasowane, pokrycie 7/7 = 1.0 ≥ 0.6 → `zgadywanie`. ✅
- **Agresywny skrót w pliku** (`Zakł. Piel. Anestezj.`, 3 słowa) vs `nazwa`(7) →
  pokrycie 3/7 = 0.43 < 0.6 → odrzucony przez `nazwa`, ale trafia w `skrot`
  (`Zakł. Piel. Anestezj.` → nawet exact/`matchuj_jednostke`). ✅
- **Plik dłuższy niż pole** → podciąg się nie domknie (`None`). ✅
- **Fragment nazwy** (`Zakład Opieki Medycznej` vs 7-słowna nazwa) → pokrycie
  0.43 < 0.6 → odrzucony (za dwuznaczny). ✅
- **Krótki skrót vs długa obca nazwa** → pokrycie < 0.6 → odrzucony. ✅

## Testy

Plik `src/import_common/tests/test_jednostka_klasyfikacja.py` (istniejące fixture
`uczelnia`) + ewentualnie nowe `test_dopasuj_po_skrocie.py`.

TDD — testy najpierw:

1. **Jednostkowe `dopasuj_po_skrocie` / `_liczba_dopasowanych` / `_para_prefiksowa`**
   (czyste, bez DB, na atrapach obiektów z `.nazwa/.skrot/.sim`):
   - zgłoszony przypadek `Zakład Piel. Anestezjol. i Intens. Opieki Medycznej`
     → trafia w jednostkę z pełną nazwą;
   - `i`/`II` nie „połykają" długiego słowa (reguła ≤2 znaki);
   - guard `min_pokrycie`: fragment nazwy → None;
   - `min_slow`: 1 słowo → None;
   - plik dłuższy niż pole → None;
   - dwukierunkowość: plik pełny vs pole-skrót i odwrotnie.
2. **Integracyjne `sklasyfikuj_jednostke` (`@pytest.mark.django_db`)**:
   - baker: jednostka afiliująca z pełną `nazwa`; wejście = forma skrócona →
     `(jednostka, "zgadywanie", sim)`;
   - twarda ścieżka nadal `twardy` (regres — istniejące testy zielone);
   - `brak` gdy nic nie pasuje;
   - obca jednostka (poza pulą afiliacyjną) nie jest zwracana.
3. **Regresja:** cały moduł `import_common` + `import_pracownikow` zielony.

## Wdrożenie

- **Bez migracji** (czysta logika).
- Newsfragment `src/bpp/newsfragments/<slug>.bugfix.rst`: „Import pracowników
  dopasowuje jednostki także gdy nazwa w pliku jest skrócona słowo-po-słowie
  (np. `Zakład Piel. Anestezjol.…`)."
- Ruff/format, `make tests-without-playwright` (moduł) + pełny run lokalnie.

## Ryzyka / do rozważenia w planie

- `TRIGRAM_FLOOR`: zbyt wysoki mógłby wyciąć poprawną, bardzo skróconą nazwę z
  top-K. 0.25 jest bezpieczne dla zgłoszonego przypadku (0.629), ale strojone.
- Greedy alignment jest wystarczający dla niemal-równoległych skrótów; gdyby
  realne dane wymagały, można podnieść do DP (LCS) — na razie YAGNI.
- Wydajność: fallback tylko dla wierszy bez twardego trafienia, jedno zapytanie +
  ≤`TOP_K` tanich wyrównań w Pythonie. Akceptowalne dla typowych importów.
