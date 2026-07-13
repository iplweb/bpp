# Dopasowanie jednostek po skrótach słów — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import pracowników dopasowuje jednostkę, gdy nazwa w pliku Excel jest skrócona słowo-po-słowie (`Zakład Piel. Anestezjol. i Intens. Opieki Medycznej`), a w bazie zapisana pełna (`Zakład Pielęgniarstwa Anestezjologicznego i Intensywnej Opieki Medycznej`).

**Architecture:** Nowa czysta funkcja `dopasuj_po_skrocie` + helpery w `src/import_common/core/jednostka.py`, wpięta jako fallback w istniejące `sklasyfikuj_jednostke` (po nieudanym exact i słabym trigramie). Prefiksowe, dwukierunkowe wyrównanie słów (uporządkowany podciąg) przeciw polom `nazwa` i `skrot`; **guard pokrycia zawsze względem `nazwa`**; trafienie zawsze `zgadywanie`. Jeden dodatkowy prefiltr top-K trigramem, alignment w Pythonie.

**Tech Stack:** Python 3.10+, Django ORM, `django.contrib.postgres.search.TrigramSimilarity`, `unidecode` (już w deps), pytest + model_bakery + pytest-testcontainers-django.

**Uwaga o rewizji:** ten plan uwzględnia review Fable (2026-07-13) — patrz „Rewizja" w specu. Kluczowe: pokrycie liczone względem `nazwa`, równość dla numerałów rzymskich/cyfr, realny test negatywny.

## Global Constraints

- Max długość linii: **88 znaków** (ruff).
- Wszystkie komendy Pythona z prefiksem **`uv run`**.
- Testy: konwencje pytest (funkcje, bez `unittest.TestCase`), `@pytest.mark.django_db` dla DB, `model_bakery.baker.make` do obiektów.
- **Bez migracji** (czysta logika).
- Newsfragment obowiązkowy: `src/bpp/newsfragments/import-skroty-jednostek.bugfix.rst` (treść po polsku).
- Nie modyfikować twardej ścieżki `matchuj_jednostke`.
- Nie uruchamiać `ruff check --fix` / batch-fixów; poprawki ręcznie.

---

### Task 1: Czysty matcher po skrótach (`dopasuj_po_skrocie` + helpery)

Samodzielny algorytm bez DB — testowany na atrapach kandydatów (`SimpleNamespace` z `.nazwa/.skrot/.sim`).

**Files:**
- Modify: `src/import_common/core/jednostka.py` (dodać importy, stałe, 5 funkcji)
- Test: `src/import_common/tests/test_dopasuj_po_skrocie.py` (nowy)

**Interfaces:**
- Consumes: `ROMAN_NUMERAL_PATTERN` z `import_common.normalization` (istniejący, `normalization.py:44`).
- Produces:
  - `TRIGRAM_FLOOR = 0.25`, `TOP_K = 50`, `MIN_SLOW_PLIKU = 2`, `MIN_POKRYCIE = 0.6`
  - `_slowa(s: str) -> list[str]` — tokenizacja+normalizacja (usuwa `(...)`, unidecode, lower, obcina brzegową interpunkcję regexem).
  - `_jest_numeralem(t: str) -> bool` — token to numerał rzymski (I–XX) lub liczba.
  - `_para_prefiksowa(a: str, b: str) -> bool` — a==b lub prefiks dwukierunkowy; tokeny ≤2 znaki ORAZ numerały wymagają równości.
  - `_liczba_dopasowanych(slowa_pliku, slowa_pola) -> int | None` — greedy podciąg; liczba dopasowanych słów pliku lub `None`.
  - `dopasuj_po_skrocie(nazwa, kandydaci, *, min_slow=MIN_SLOW_PLIKU, min_pokrycie=MIN_POKRYCIE)` — najlepszy kandydat (instancja z `.nazwa/.skrot/.sim`) lub `None`. Pokrycie liczone względem `_slowa(kand.nazwa)`.

- [ ] **Step 1: Napisz failujące testy jednostkowe**

Utwórz `src/import_common/tests/test_dopasuj_po_skrocie.py`:

```python
"""Testy czystego matchera jednostek po skrótach słów (bez DB)."""

from types import SimpleNamespace

from import_common.core.jednostka import (
    _jest_numeralem,
    _liczba_dopasowanych,
    _para_prefiksowa,
    _slowa,
    dopasuj_po_skrocie,
)


def _kand(nazwa, skrot, sim=0.5):
    return SimpleNamespace(nazwa=nazwa, skrot=skrot, sim=sim)


# --- _slowa --------------------------------------------------------------------


def test_slowa_normalizuje_i_obcina_kropki():
    assert _slowa("Zakład Piel. Anestezjol.") == ["zaklad", "piel", "anestezjol"]


def test_slowa_usuwa_nawiasowy_skrot_wydzialu():
    # '(WNoZ)' to skrót wydziału — ma zniknąć, nie stać się tokenem 'wnoz'
    assert _slowa("Zakład Pielęgniarstwa (WNoZ)") == ["zaklad", "pielegniarstwa"]


def test_slowa_obcina_transliterowane_cudzyslowy():
    # unidecode('„')==',,' , unidecode('»')=='>>' — brzegi mają zniknąć
    assert _slowa("„FizjoPasjonaci” »SKN«") == ["fizjopasjonaci", "skn"]


def test_slowa_pusty():
    assert _slowa("") == []
    assert _slowa("   ") == []


# --- _jest_numeralem -----------------------------------------------------------


def test_jest_numeralem():
    assert _jest_numeralem("vii") is True
    assert _jest_numeralem("VIII") is True
    assert _jest_numeralem("iii") is True
    assert _jest_numeralem("12") is True
    assert _jest_numeralem("med") is False
    assert _jest_numeralem("lic") is False  # L/I/C, ale nie poprawny numerał


# --- _para_prefiksowa ----------------------------------------------------------


def test_para_prefiksowa_dwukierunkowa():
    assert _para_prefiksowa("piel", "pielegniarstwa") is True
    assert _para_prefiksowa("pielegniarstwa", "piel") is True
    assert _para_prefiksowa("med", "medycznej") is True


def test_para_prefiksowa_krotkie_wymagaja_rownosci():
    # 'i' (≤2) nie może być prefiksem 'intensywnej'
    assert _para_prefiksowa("i", "intensywnej") is False
    assert _para_prefiksowa("i", "i") is True
    assert _para_prefiksowa("ii", "ii") is True


def test_para_prefiksowa_numeraly_wymagaja_rownosci():
    # VII nie może być prefiksem VIII (numerowane kliniki)
    assert _para_prefiksowa("vii", "viii") is False
    assert _para_prefiksowa("xii", "xiii") is False
    assert _para_prefiksowa("vii", "vii") is True


def test_para_prefiksowa_rozne():
    assert _para_prefiksowa("chirurgii", "biologii") is False


# --- _liczba_dopasowanych ------------------------------------------------------


def test_liczba_dopasowanych_pelne_wyrownanie():
    plik = ["zaklad", "piel", "anestezjol", "i", "intens", "opieki", "medycznej"]
    pole = [
        "zaklad", "pielegniarstwa", "anestezjologicznego",
        "i", "intensywnej", "opieki", "medycznej",
    ]
    assert _liczba_dopasowanych(plik, pole) == 7


def test_liczba_dopasowanych_podciag_z_pominietymi_slowami_pola():
    # plik bez 'i' — pole ma 'i'; podciąg nadal się domyka
    plik = ["kat", "zakl", "zdr", "publ"]
    pole = ["katedra", "i", "zaklad", "zdrowia", "publicznego"]
    assert _liczba_dopasowanych(plik, pole) == 4


def test_liczba_dopasowanych_nieznane_slowo_pliku_none():
    assert _liczba_dopasowanych(["zaklad", "chirurgii"], ["zaklad", "biologii"]) is None


def test_liczba_dopasowanych_plik_dluzszy_niz_pole_none():
    plik = ["zaklad", "piel", "anestezjol", "i", "intens", "opieki", "medycznej"]
    assert _liczba_dopasowanych(plik, ["zaklad", "opieki"]) is None


# --- dopasuj_po_skrocie --------------------------------------------------------


def test_dopasuj_zgloszony_przypadek():
    kand = _kand(
        "Zakład Pielęgniarstwa Anestezjologicznego i Intensywnej Opieki Medycznej",
        "Zakł. Piel. Anestezj.",
        sim=0.629,
    )
    wynik = dopasuj_po_skrocie(
        "Zakład Piel. Anestezjol. i Intens. Opieki Medycznej", [kand]
    )
    assert wynik is kand


def test_dopasuj_dwukierunkowo_plik_pelny_pole_skrocone():
    # plik pełny; dopasowanie przez skrócone słowa w NAZWIE kandydata,
    # pokrycie liczone względem nazwy (5 słów) = 5/5
    kand = _kand("Kat. i Zakł. Zdr. Publ.", "KZP", sim=0.4)
    wynik = dopasuj_po_skrocie("Katedra i Zakład Zdrowia Publicznego", [kand])
    assert wynik is kand


def test_dopasuj_min_slow_jedno_slowo_none():
    kand = _kand("Zakład Pielęgniarstwa Opieki", "ZPO", sim=0.5)
    assert dopasuj_po_skrocie("Piel.", [kand]) is None


def test_dopasuj_guard_pokrycia_fragment_none():
    # 3 słowa pliku vs 7 słów NAZWY → pokrycie 3/7=0.43 < 0.6 → odrzucony,
    # nawet gdy skrót kandydata jest krótki (guard liczy się względem nazwy)
    kand = _kand(
        "Zakład Pielęgniarstwa Anestezjologicznego i Intensywnej Opieki Medycznej",
        "Zakł. Piel. Anestezj.",
        sim=0.4,
    )
    assert dopasuj_po_skrocie("Zakład Opieki Medycznej", [kand]) is None


def test_dopasuj_krotki_skrot_nie_omija_guardu():
    # regres na finding #1: 2-słowny generyk vs krótki skrot NIE może przejść
    kand = _kand(
        "Zakład Chorób Wewnętrznych i Metabolicznych", "Zakł. Chor. Wewn.", sim=0.4
    )
    # pokrycie względem nazwy: 2/5 = 0.4 < 0.6 (a NIE 2/3 względem skrotu)
    assert dopasuj_po_skrocie("Zakład Chorób", [kand]) is None


def test_dopasuj_dopisek_w_pliku_none():
    # all-or-nothing na słowach pliku: dopisek 'UM' bez pary → None (znany limit v1)
    kand = _kand("Zakład Transfuzjologii", "ZT", sim=0.5)
    assert dopasuj_po_skrocie("Zakład Transfuzjologii UM", [kand]) is None


def test_dopasuj_wybiera_najlepsze_pokrycie_potem_sim():
    # słaby: 4 słowa nazwy → pokrycie 3/4=0.75; mocny: 3 słowa → 3/3=1.0
    slaby = _kand("Zakład Opieki Zdrowotnej Medycznej", "ZOZM", sim=0.9)
    mocny = _kand("Zakład Opieki Medycznej", "ZOM", sim=0.3)
    wynik = dopasuj_po_skrocie("Zakład Opieki Medycznej", [slaby, mocny])
    assert wynik is mocny


def test_dopasuj_brak_kandydatow_none():
    assert dopasuj_po_skrocie("Zakład Czegokolwiek", []) is None
```

- [ ] **Step 2: Uruchom testy — sprawdź, że failują**

Run: `uv run pytest src/import_common/tests/test_dopasuj_po_skrocie.py -q`
Expected: FAIL — `ImportError: cannot import name ...` (funkcje jeszcze nie istnieją; CPython raportuje pierwszą brakującą nazwę z listy importu).
(Uwaga: pierwszy run może wolno startować testcontainery — mimo braku `@django_db` plugin stawia PG dla sesji. Ponów jeśli cold start timeoutuje.)

- [ ] **Step 3: Dodaj importy na górze `jednostka.py`**

W `src/import_common/core/jednostka.py`:

- w grupie stdlib (na górze) dodaj `import re`;
- z third-party dodaj `from unidecode import unidecode`;
- rozszerz istniejący import z normalization:

```python
from ..normalization import ROMAN_NUMERAL_PATTERN, normalize_nazwa_jednostki
```

(Obecnie jest `from ..normalization import normalize_nazwa_jednostki` — dopisz `ROMAN_NUMERAL_PATTERN`.)

- [ ] **Step 4: Dodaj stałe obok `PROG_ZGADYWANIA_JEDNOSTKI`**

Zaraz pod `PROG_ZGADYWANIA_JEDNOSTKI = 0.7` (linia ~14) dopisz:

```python
# Fallback „po skrócie" (prefiksowe wyrównanie słów) — stałe strojone tu.
# Kalibracja TRIGRAM_FLOOR na realnej jednostce: forma z Excela ma trigram 0.629,
# agresywny pełnowymiarowy skrót 0.417 (wchodzi), 3-słowny 0.186 (odrzuca guard).
TRIGRAM_FLOOR = 0.25  # dolny próg kandydatów do prefiltru top-K (perf + odsiew)
TOP_K = 50  # ilu kandydatów materializujemy do wyrównania w Pythonie
MIN_SLOW_PLIKU = 2  # <2 słowa → za dwuznaczne na dopasowanie po skrócie
MIN_POKRYCIE = 0.6  # min. udział słów pliku w słowach NAZWY kandydata
```

- [ ] **Step 5: Zaimplementuj helpery + `dopasuj_po_skrocie`**

Wstaw PRZED `def sklasyfikuj_jednostke(` (tuż po `_pula_afiliacyjna`):

```python
_NAWIAS = re.compile(r"\([^)]*\)")
# Obcięcie brzegowej interpunkcji PO unidecode+lower (token jest już ASCII);
# zbiór musi pokrywać transliteracje unidecode (np. '«'->'<<'), nie znaki źródłowe.
_OBETNIJ_BRZEGI = re.compile(r"^[^a-z0-9]+|[^a-z0-9]+$")
_NUMERAL = re.compile(rf"(?:{ROMAN_NUMERAL_PATTERN}|[0-9]+)", re.IGNORECASE)


def _slowa(s):
    """Nazwa/skrot → lista znormalizowanych słów.

    Usuwa nawiasowe grupy (np. „(WNoZ)" — skrót wydziału z displayu), łamie na
    słowa, każde: unidecode (zdejmuje ogonki ł→l, ż→z), lower, obcięcie brzegowej
    interpunkcji. Puste tokeny pominięte.
    """
    s = _NAWIAS.sub(" ", s or "")
    out = []
    for w in s.split():
        w = _OBETNIJ_BRZEGI.sub("", unidecode(w).lower())
        if w:
            out.append(w)
    return out


def _jest_numeralem(t):
    """True gdy token to numerał rzymski (I–XX) albo liczba arabska."""
    return _NUMERAL.fullmatch(t) is not None


def _para_prefiksowa(a, b):
    """True gdy a==b albo jedno jest prefiksem drugiego (dwukierunkowo).

    Tokeny ≤2 znaki (np. „i", „ii", „im") ORAZ numerały (rzymskie/cyfry) wymagają
    RÓWNOŚCI, nie prefiksu — inaczej „i" połknęłoby „intensywnej", a „VII"
    dopasowałoby się do „VIII" (numerowane kliniki). „III" (3 znaki) obsługuje
    reguła numerałów.
    """
    if len(a) <= 2 or len(b) <= 2:
        return a == b
    if _jest_numeralem(a) or _jest_numeralem(b):
        return a == b
    return a.startswith(b) or b.startswith(a)


def _liczba_dopasowanych(slowa_pliku, slowa_pola):
    """Greedy: słowa_pliku jako uporządkowany podciąg słów_pola z relacją
    prefiksową. Zwraca liczbę dopasowanych słów (== len(slowa_pliku)) albo None,
    gdy któreś słowo pliku nie znalazło pary. Greedy earliest-match jest
    dowodliwie optymalny dla testu istnienia podciągu."""
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
    """Najlepszy kandydat wg prefiksowego wyrównania słów, albo None.

    Wyrównanie próbowane na `nazwa` LUB `skrot` kandydata (istnienie podciągu),
    ale POKRYCIE liczone ZAWSZE względem słów `nazwa` (kanoniczna długość
    jednostki) — inaczej krótki `skrot` omijałby guard. `kandydaci` — instancje
    z adnotacją `.sim` (trigram). Ranking: (pokrycie, trigram); remis → wyższy
    trigram, przy równym pierwszy napotkany (wynik i tak jest `zgadywanie`,
    weryfikowany przez użytkownika).

    Znane ograniczenia v1: (1) reguła ≤2 znaki wyklucza 2-znakowe skróty słów
    (`Kl.`, `Ch.`); (2) all-or-nothing na słowach pliku — dopisek bez pary
    (`UM`, `CM`) daje None.
    """
    slowa_pliku = _slowa(nazwa)
    if len(slowa_pliku) < min_slow:
        return None
    najlepszy = None
    najlepszy_klucz = None
    for kand in kandydaci:
        slowa_nazwa = _slowa(kand.nazwa or "")
        if not slowa_nazwa:
            continue
        dopasowany = False
        for slowa_pola in (slowa_nazwa, _slowa(kand.skrot or "")):
            if slowa_pola and _liczba_dopasowanych(slowa_pliku, slowa_pola) is not None:
                dopasowany = True
                break
        if not dopasowany:
            continue
        pokrycie = len(slowa_pliku) / len(slowa_nazwa)
        if pokrycie < min_pokrycie:
            continue
        klucz = (pokrycie, float(kand.sim or 0.0))
        if najlepszy_klucz is None or klucz > najlepszy_klucz:
            najlepszy = kand
            najlepszy_klucz = klucz
    return najlepszy
```

- [ ] **Step 6: Uruchom testy — sprawdź, że przechodzą**

Run: `uv run pytest src/import_common/tests/test_dopasuj_po_skrocie.py -q`
Expected: PASS (21 testów).

- [ ] **Step 7: Ruff format + check na zmienionych plikach**

Run:
```bash
uv run ruff format src/import_common/core/jednostka.py src/import_common/tests/test_dopasuj_po_skrocie.py
uv run ruff check src/import_common/core/jednostka.py src/import_common/tests/test_dopasuj_po_skrocie.py
```
Expected: brak błędów (linie ≤88).

- [ ] **Step 8: Commit**

```bash
git add src/import_common/core/jednostka.py src/import_common/tests/test_dopasuj_po_skrocie.py
git commit -m "feat(import): czysty matcher jednostek po skrótach słów

dopasuj_po_skrocie + helpery: prefiksowe dwukierunkowe wyrównanie słów
(uporządkowany podciąg) do nazwa/skrot; pokrycie względem nazwy; równość
dla numerałów rzymskich/cyfr; guard min. liczby słów.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Wpięcie fallbacku w `sklasyfikuj_jednostke` + newsfragment

Podmiana finalnego kroku `sklasyfikuj_jednostke` (dziś: pojedynczy trigram `.first()`) na top-K + fallback po skrócie. Trafienie po skrócie = `zgadywanie`.

**Files:**
- Modify: `src/import_common/core/jednostka.py` (ciało + docstring `sklasyfikuj_jednostke`, linie ~117-156)
- Test: `src/import_common/tests/test_jednostka_klasyfikacja.py` (dopisać testy integracyjne)
- Create: `src/bpp/newsfragments/import-skroty-jednostek.bugfix.rst`

**Interfaces:**
- Consumes: `dopasuj_po_skrocie`, `TRIGRAM_FLOOR`, `TOP_K` (Task 1); `_pula_afiliacyjna`, `TrigramSimilarity`, `Greatest`, `STATUS_JEDNOSTKA_*` (istniejące).
- Produces: `sklasyfikuj_jednostke(nazwa, wydzial=None, *, prog=...) -> (Jednostka|None, status, sim|None)` — sygnatura bez zmian; nowe zachowanie: skrócona nazwa → `(j, "zgadywanie", sim)`.

- [ ] **Step 1: Napisz failujące testy integracyjne**

Dopisz na końcu `src/import_common/tests/test_jednostka_klasyfikacja.py`:

```python
# --- fallback po skrócie słów (sklasyfikuj_jednostke) ---------------------------


@pytest.mark.django_db
def test_sklasyfikuj_skrocona_nazwa_zgadywanie(uczelnia):
    j = baker.make(
        Jednostka,
        nazwa=(
            "Zakład Pielęgniarstwa Anestezjologicznego "
            "i Intensywnej Opieki Medycznej"
        ),
        skrot="Zakł. Piel. Anestezj.",
        uczelnia=uczelnia,
    )
    jednostka, status, sim = sklasyfikuj_jednostke(
        "Zakład Piel. Anestezjol. i Intens. Opieki Medycznej"
    )
    assert jednostka == j
    assert status == STATUS_ZGADYWANIE
    assert sim is not None  # trigram kandydata (poniżej progu, ale nie None)


@pytest.mark.django_db
def test_sklasyfikuj_skrot_agresywny_pelnowymiarowy_zgadywanie(uczelnia):
    # forma agresywniej skrócona (trigram 0.417) — musi wejść do puli (floor 0.25)
    # i wyrównać się 7/7 do nazwy
    j = baker.make(
        Jednostka,
        nazwa=(
            "Zakład Pielęgniarstwa Anestezjologicznego "
            "i Intensywnej Opieki Medycznej"
        ),
        skrot="Zakł. Piel. Anestezj.",
        uczelnia=uczelnia,
    )
    jednostka, status, sim = sklasyfikuj_jednostke(
        "Zakł. Pielęg. Anest. i Inten. Opieki Med."
    )
    assert jednostka == j
    assert status == STATUS_ZGADYWANIE


@pytest.mark.django_db
def test_sklasyfikuj_fragment_w_puli_ale_ponizej_pokrycia_brak(uczelnia):
    # finding #3: input DZIELI słowa z nazwą (trigram 0.313 ≥ floor → wchodzi do
    # puli, więc guard SIĘ WYKONUJE), ale pokrycie 2/7 < 0.6 → BRAK.
    # NIE 'Zakład Pielęgniarstwa' (to złapałby matchuj_jednostke istartswith).
    baker.make(
        Jednostka,
        nazwa=(
            "Zakład Pielęgniarstwa Anestezjologicznego "
            "i Intensywnej Opieki Medycznej"
        ),
        skrot="Zakł. Piel. Anestezj.",
        uczelnia=uczelnia,
    )
    jednostka, status, sim = sklasyfikuj_jednostke("Pielęgniarstwa Opieki")
    assert jednostka is None
    assert status == STATUS_BRAK
```

- [ ] **Step 2: Uruchom nowe testy — sprawdź, że failują**

Run:
```bash
uv run pytest "src/import_common/tests/test_jednostka_klasyfikacja.py::test_sklasyfikuj_skrocona_nazwa_zgadywanie" -q
```
Expected: FAIL — obecne `sklasyfikuj_jednostke` zwróci `STATUS_BRAK` (trigram 0.629 < 0.7), więc `jednostka == j` nie przejdzie.

- [ ] **Step 3: Podmień ciało + docstring `sklasyfikuj_jednostke`**

W `src/import_common/core/jednostka.py`:

3a. Zaktualizuj docstring (dopisz o fallbacku). Zamień akapit opisujący zwracane wartości na:

```python
    """Klasyfikuje nazwę jednostki z pliku BEZ rzucania wyjątków.

    Zwraca ``(jednostka|None, status, similarity|None)``:
    - dokładne dopasowanie (``matchuj_jednostke``) → ``(j, "twardy", None)``;
    - najbliższa trigramowo ≥ ``prog`` (z puli afiliacyjnej) →
      ``(best, "zgadywanie", sim)``;
    - inaczej fallback ``dopasuj_po_skrocie`` (prefiksowe wyrównanie słów do
      nazwa/skrot, np. skrócone „Zakład Piel. Anestezjol.…") →
      ``(best, "zgadywanie", sim)`` — auto-wybór do weryfikacji;
    - w przeciwnym razie (pusta nazwa, brak podobnej) → ``(None, "brak", None)``.

    ``matchuj_jednostke`` rzuca ``DoesNotExist``/``MultipleObjectsReturned`` —
    oba łapiemy i spadamy do trigramu/fallbacku, więc funkcja nigdy nie wywali
    analizy.
    """
```

3b. Zamień blok od `best = (` do końcowego `return None, STATUS_JEDNOSTKA_BRAK, None` na:

```python
    kandydaci = list(
        _pula_afiliacyjna()
        .annotate(
            sim=Greatest(
                TrigramSimilarity("nazwa", nazwa_norm),
                TrigramSimilarity("skrot", nazwa_norm),
            )
        )
        .filter(sim__gte=min(TRIGRAM_FLOOR, prog))
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

(Zostaw nietknięty wcześniejszy fragment: `if not nazwa`, `normalize_nazwa_jednostki`, blok `try: matchuj_jednostke`.)

- [ ] **Step 4: Uruchom nowe testy integracyjne — sprawdź, że przechodzą**

Run:
```bash
uv run pytest src/import_common/tests/test_jednostka_klasyfikacja.py -k "skrocona or agresywny or fragment_w_puli" -q
```
Expected: PASS (3).

- [ ] **Step 5: Regresja — cały plik klasyfikacji + niepełna nazwa**

Run:
```bash
uv run pytest src/import_common/tests/test_jednostka_klasyfikacja.py \
  src/import_common/tests/test_core_jednostka_niepelna.py -q
```
Expected: PASS (wszystkie). Kluczowe kontrolne:
- `test_sklasyfikuj_podobne_zgadywanie` (trigram ~0.85 ≥ prog) — bez zmian;
- `test_sklasyfikuj_brak_dopasowania` („Instytut Fizyki Jądrowej" vs „Zakład
  Transfuzjologii" — zero wspólnych słów → alignment None → BRAK);
- `test_sklasyfikuj_pula_wyklucza_obce_jednostki` (obca poza pulą → nie w
  kandydatach → BRAK);
- `test_sklasyfikuj_remis_prefiksowy_nie_rzuca` (asercja `status in (ZGADYWANIE,
  BRAK)` — po zmianie może dać ZGADYWANIE, nadal w dozwolonym zbiorze).

- [ ] **Step 6: Dodaj newsfragment**

Utwórz `src/bpp/newsfragments/import-skroty-jednostek.bugfix.rst`:

```rst
Import pracowników dopasowuje jednostki także wtedy, gdy nazwa w pliku jest
skrócona słowo-po-słowie (np. „Zakład Piel. Anestezjol. i Intens. Opieki
Medycznej" → „Zakład Pielęgniarstwa Anestezjologicznego i Intensywnej Opieki
Medycznej"). Dopasowanie po skrócie trafia zawsze do weryfikacji.
```

- [ ] **Step 7: Ruff + commit**

Run:
```bash
uv run ruff format src/import_common/core/jednostka.py src/import_common/tests/test_jednostka_klasyfikacja.py
uv run ruff check src/import_common/core/jednostka.py src/import_common/tests/test_jednostka_klasyfikacja.py
```
Expected: brak błędów.

```bash
git add src/import_common/core/jednostka.py \
  src/import_common/tests/test_jednostka_klasyfikacja.py \
  src/bpp/newsfragments/import-skroty-jednostek.bugfix.rst
git commit -m "feat(import): fallback dopasowania jednostek po skrócie w sklasyfikuj_jednostke

Top-K trigram (jedno zapytanie, floor min(0.25,prog)) → gdy <prog, prefiksowe
wyrównanie słów dopasuj_po_skrocie; skrócona nazwa z pliku → zgadywanie.
Docstring zaktualizowany. Bez migracji.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Regresja modułowa (weryfikacja)

Potwierdzenie zerowej regresji na modułach dotkniętych zmianą.

**Files:** brak zmian (tylko uruchomienie).

- [ ] **Step 1: Testy modułu import_common + import_pracownikow równolegle**

Run:
```bash
uv run pytest -n auto src/import_common/ src/import_pracownikow/ -q \
  2>&1 | tee /tmp/skroty_regresja.log; echo "EXIT=${PIPESTATUS[0]}"
```
Expected: `EXIT=0`, brak faili/errorów. (Timeout ≤600000ms. Grepuj `/tmp/skroty_regresja.log` po „failed"/„error" jeśli output ucięty.)

- [ ] **Step 2: Jeśli zielono — zaraportuj i czekaj na decyzję o PR**

Zaraportuj wynik (liczba passed, EXIT=0). Nie merguj bez zgody użytkownika (reguła: pytaj o merge vs rebase; baseline nie odświeżać — brak migracji).

---

## Self-Review

**1. Spec coverage:**
- Prefiksowe dwukierunkowe wyrównanie → Task 1 (`_para_prefiksowa`, `_liczba_dopasowanych`). ✅
- Porównanie do `nazwa` i `skrot`, pokrycie względem nazwy (rewizja #1) → Task 1 (`dopasuj_po_skrocie`). ✅
- Równość dla numerałów (rewizja #2) → Task 1 (`_jest_numeralem` + `_para_prefiksowa`). ✅
- Realny test negatywny (rewizja #3) → Task 2 (`test_sklasyfikuj_fragment_w_puli_ale_ponizej_pokrycia_brak`). ✅
- Guard pokrycia ≥0.6, min. 2 słowa → Task 1. ✅
- Usunięcie nawiasowego skrótu wydziału + regex-strip brzegów → Task 1 (`_slowa`). ✅
- Status `zgadywanie` → Task 2. ✅
- Jedno zapytanie top-K, floor `min(TRIGRAM_FLOOR, prog)` → Task 2. ✅
- Docstring `sklasyfikuj_jednostke` zaktualizowany → Task 2 Step 3a. ✅
- Kalibracja floor testem agresywnym → Task 2 (`test_sklasyfikuj_skrot_agresywny_pelnowymiarowy_zgadywanie`). ✅
- Bez migracji, newsfragment → Task 2/Global. ✅
- Regresja modułu → Task 3. ✅

**2. Placeholder scan:** Brak „TBD/TODO"; każdy krok kodu ma pełny listing. ✅

**3. Type consistency:** `dopasuj_po_skrocie(nazwa, kandydaci)` zwraca instancję z `.sim` (Task 2: `trafienie.sim`); `_liczba_dopasowanych -> int|None` (`is None`); `_jest_numeralem -> bool`; stałe `TRIGRAM_FLOOR/TOP_K` z Task 1 użyte w Task 2. Liczba testów: Task 1 = 21 (4 `_slowa` + 1 `_jest_numeralem` + 4 `_para_prefiksowa` + 4 `_liczba_dopasowanych` + 8 `dopasuj_po_skrocie`), zgodna z listingiem. ✅
