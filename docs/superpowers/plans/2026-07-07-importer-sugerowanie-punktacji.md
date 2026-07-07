# Sugerowanie punktacji w importerze — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodać w importerze publikacji jawny krok „Punktacja" sugerujący punkty
MNiSW (ciągłe: z `Punktacja_Zrodla`; zwarte: z poziomu wydawcy + realnych ról
autorów), oraz wybór typu autora (autor/redaktor) w kroku autorów.

**Architecture:** Czysta funkcja sugestii (`bpp/punktacja_sugestia.py`) współdzielona
przez nowy krok wizarda i komendę `ustaw_zwrotnie_punkty_zwartych` (jedno źródło
prawdy progów). Nowy krok HTMX między Authors a Review; wartość w
`session.matched_data`. Typ autora jako `typ_ogolny` na `ImportedAuthor`,
respektowany przez `_add_authors_to_record`.

**Tech Stack:** Django, HTMX, pytest + model_bakery + testcontainers.

## Global Constraints

- Python `uv run` prefix dla WSZYSTKICH komend Pythona; nigdy `python` wprost.
- Max długość linii 88 znaków (ruff).
- NIE edytować istniejących migracji — tylko nowe.
- Testy: pytest (funkcje, bez klas), `@pytest.mark.django_db`, `baker.make`.
- Bez `except: pass` — logować/re-raise/zwracać sensowny błąd.
- Po migracji schematu: `make baseline-update` (raz, na końcu).
- Stałe: `const.TO_AUTOR = 0`, `const.TO_REDAKTOR = 1`,
  `const.CHARAKTER_SLOTY_KSIAZKA = 1`, `const.CHARAKTER_SLOTY_ROZDZIAL = 2`.
- Kanoniczne wiersze `Typ_Odpowiedzialnosci`: `skrot="aut."` (TO_AUTOR),
  `skrot="red."` (TO_REDAKTOR).
- Progi zwartych (indeks = poziom 0/1/2): `KS 20/80/200`, `RED 5/20/100`,
  `ROZ 5/20/50`.

---

### Task 1: Czysta funkcja sugestii dla zwartych + typy `SugestiaPunktacji`

**Files:**
- Create: `src/bpp/punktacja_sugestia.py`
- Test: `src/bpp/tests/test_punktacja_sugestia.py`

**Interfaces:**
- Produces: `RodzajBraku` (enum), `SugestiaPunktacji` (dataclass: `punkty: Decimal|None`,
  `podstawa: str`, `rodzaj_braku: RodzajBraku|None`, `powod_braku: str|None`),
  `PROGI_ZWARTE` (list[dict]), `zaproponuj_punkty_zwarte(*, poziom, ksiazka, rozdzial, autorstwo, redakcja) -> SugestiaPunktacji`.

- [ ] **Step 1: Write the failing test**

```python
# src/bpp/tests/test_punktacja_sugestia.py
from decimal import Decimal

from bpp.punktacja_sugestia import (
    RodzajBraku,
    zaproponuj_punkty_zwarte,
)


def test_zwarte_monografia_autorska_poziom_II():
    s = zaproponuj_punkty_zwarte(
        poziom=2, ksiazka=True, rozdzial=False, autorstwo=True, redakcja=False
    )
    assert s.punkty == Decimal(200)
    assert s.rodzaj_braku is None


def test_zwarte_monografia_redagowana_poziom_II():
    s = zaproponuj_punkty_zwarte(
        poziom=2, ksiazka=True, rozdzial=False, autorstwo=False, redakcja=True
    )
    assert s.punkty == Decimal(100)


def test_zwarte_rozdzial_poziom_I():
    s = zaproponuj_punkty_zwarte(
        poziom=1, ksiazka=False, rozdzial=True, autorstwo=True, redakcja=False
    )
    assert s.punkty == Decimal(20)


def test_zwarte_poziom_brak_traktowany_jako_zero():
    for poziom in (-1, None):
        s = zaproponuj_punkty_zwarte(
            poziom=poziom, ksiazka=True, rozdzial=False, autorstwo=True, redakcja=False
        )
        assert s.punkty == Decimal(20)


def test_zwarte_brak_autorstwa():
    s = zaproponuj_punkty_zwarte(
        poziom=2, ksiazka=True, rozdzial=False, autorstwo=False, redakcja=False
    )
    assert s.punkty is None
    assert s.rodzaj_braku == RodzajBraku.BRAK_AUTORSTWA


def test_zwarte_nieobsluzona_kombinacja():
    s = zaproponuj_punkty_zwarte(
        poziom=2, ksiazka=True, rozdzial=True, autorstwo=True, redakcja=False
    )
    assert s.punkty is None
    assert s.rodzaj_braku == RodzajBraku.NIEOBSLUZONA_KOMBINACJA
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mpasternak/Programowanie/bpp-384-sugeruj-punktacje-importer && uv run pytest src/bpp/tests/test_punktacja_sugestia.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bpp.punktacja_sugestia'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/bpp/punktacja_sugestia.py
"""Sugerowanie punktacji ministerialnej (punkty_kbn).

Jedno źródło prawdy o progach zwartych — współdzielone przez importer
publikacji (nowy krok „Punktacja") i komendę ``ustaw_zwrotnie_punkty_zwartych``.
"""

import enum
from dataclasses import dataclass
from decimal import Decimal


class RodzajBraku(enum.Enum):
    """Dlaczego nie da się zaproponować punktów.

    Rozróżnia anomalię DANYCH (brak wydawcy/roku/autorstwa/punktacji źródła) od
    luki w logice (nieobsłużona kombinacja typu) — komenda mapuje to na
    skip+raport vs twardy ``NotImplementedError``.
    """

    BRAK_DANYCH_ZRODLA = "brak_danych_zrodla"
    BRAK_ROKU = "brak_roku"
    BRAK_WYDAWCY = "brak_wydawcy"
    BRAK_AUTORSTWA = "brak_autorstwa"
    NIEOBSLUZONA_KOMBINACJA = "nieobsluzona_kombinacja"


@dataclass
class SugestiaPunktacji:
    punkty: Decimal | None
    podstawa: str = ""
    rodzaj_braku: RodzajBraku | None = None
    powod_braku: str | None = None


# PROGI_ZWARTE[poziom] — poziom 0 (spoza wykazu) / I / II.
PROGI_ZWARTE = [
    {"KS": Decimal(20), "RED": Decimal(5), "ROZ": Decimal(5)},
    {"KS": Decimal(80), "RED": Decimal(20), "ROZ": Decimal(20)},
    {"KS": Decimal(200), "RED": Decimal(100), "ROZ": Decimal(50)},
]

_OPIS_POZIOMU = {0: "spoza wykazu", 1: "I", 2: "II"}


def zaproponuj_punkty_zwarte(*, poziom, ksiazka, rozdzial, autorstwo, redakcja):
    """Zaproponuj punkty_kbn dla wydawnictwa zwartego na bazie prymitywów.

    ``poziom`` = wynik ``Wydawca.get_tier(rok)`` (-1/None → 0 „spoza wykazu").
    ``ksiazka``/``rozdzial`` z ``charakter_sloty``; ``autorstwo``/``redakcja`` z
    ról autorów. Nie dotyka bazy, nie rzuca — braki zwraca w ``rodzaj_braku``.
    """
    if poziom in (-1, None):
        poziom = 0
    progi = PROGI_ZWARTE[poziom]
    opis = _OPIS_POZIOMU[poziom]

    if not autorstwo and not redakcja:
        return SugestiaPunktacji(
            punkty=None,
            rodzaj_braku=RodzajBraku.BRAK_AUTORSTWA,
            powod_braku="Brak punktowalnego autorstwa/redakcji",
        )
    if ksiazka and rozdzial:
        return SugestiaPunktacji(
            punkty=None,
            rodzaj_braku=RodzajBraku.NIEOBSLUZONA_KOMBINACJA,
            powod_braku="Rekord jest jednocześnie książką i rozdziałem",
        )
    if ksiazka and autorstwo:
        return SugestiaPunktacji(progi["KS"], f"Wydawca poziom {opis} — monografia")
    if ksiazka and redakcja:
        return SugestiaPunktacji(progi["RED"], f"Wydawca poziom {opis} — redakcja")
    if rozdzial and autorstwo:
        return SugestiaPunktacji(progi["ROZ"], f"Wydawca poziom {opis} — rozdział")
    return SugestiaPunktacji(
        punkty=None,
        rodzaj_braku=RodzajBraku.NIEOBSLUZONA_KOMBINACJA,
        powod_braku=(
            f"Nieobsłużona kombinacja: ksiazka={ksiazka} rozdzial={rozdzial} "
            f"autorstwo={autorstwo} redakcja={redakcja}"
        ),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_punktacja_sugestia.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/punktacja_sugestia.py src/bpp/tests/test_punktacja_sugestia.py
git commit -m "feat(punktacja): czysta funkcja sugestii dla zwartych (#384)"
```

---

### Task 2: Czysta funkcja sugestii dla ciągłych

**Files:**
- Modify: `src/bpp/punktacja_sugestia.py`
- Test: `src/bpp/tests/test_punktacja_sugestia.py`

**Interfaces:**
- Consumes: `Punktacja_Zrodla` (`bpp/models/zrodlo.py`).
- Produces: `zaproponuj_punkty_ciagle(zrodlo, rok) -> SugestiaPunktacji`.

- [ ] **Step 1: Write the failing test**

```python
# dopisz do src/bpp/tests/test_punktacja_sugestia.py
import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_ciagle_jest_punktacja_zrodla():
    from bpp.models import Punktacja_Zrodla, Zrodlo
    from bpp.punktacja_sugestia import zaproponuj_punkty_ciagle

    zrodlo = baker.make(Zrodlo)
    baker.make(Punktacja_Zrodla, zrodlo=zrodlo, rok=2024, punkty_kbn=Decimal(140))
    s = zaproponuj_punkty_ciagle(zrodlo, 2024)
    assert s.punkty == Decimal(140)
    assert s.rodzaj_braku is None


@pytest.mark.django_db
def test_ciagle_brak_punktacji_zrodla_bez_fallbacku():
    from bpp.models import Zrodlo
    from bpp.punktacja_sugestia import RodzajBraku, zaproponuj_punkty_ciagle

    zrodlo = baker.make(Zrodlo)
    s = zaproponuj_punkty_ciagle(zrodlo, 2024)
    assert s.punkty is None  # NIE 5 pkt (to polityka komendy PBN, nie importera)
    assert s.rodzaj_braku == RodzajBraku.BRAK_DANYCH_ZRODLA


@pytest.mark.django_db
def test_ciagle_brak_roku():
    from bpp.models import Zrodlo
    from bpp.punktacja_sugestia import RodzajBraku, zaproponuj_punkty_ciagle

    s = zaproponuj_punkty_ciagle(baker.make(Zrodlo), None)
    assert s.punkty is None
    assert s.rodzaj_braku == RodzajBraku.BRAK_ROKU
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_punktacja_sugestia.py -k ciagle -v`
Expected: FAIL — `ImportError: cannot import name 'zaproponuj_punkty_ciagle'`.

- [ ] **Step 3: Write minimal implementation**

```python
# dopisz do src/bpp/punktacja_sugestia.py
def zaproponuj_punkty_ciagle(zrodlo, rok):
    """Zaproponuj punkty_kbn dla wydawnictwa ciągłego z Punktacja_Zrodla.

    Bez PBN-owego fallbacku „5 pkt" — importer pokazuje uczciwe „brak danych".
    """
    from bpp.models import Punktacja_Zrodla

    if not rok:
        return SugestiaPunktacji(
            punkty=None,
            rodzaj_braku=RodzajBraku.BRAK_ROKU,
            powod_braku="Brak roku publikacji — nie można dobrać punktacji źródła",
        )
    try:
        pz = Punktacja_Zrodla.objects.get(zrodlo=zrodlo, rok=rok)
    except Punktacja_Zrodla.DoesNotExist:
        return SugestiaPunktacji(
            punkty=None,
            rodzaj_braku=RodzajBraku.BRAK_DANYCH_ZRODLA,
            powod_braku=f"Brak punktacji źródła „{zrodlo}” za {rok}",
        )
    return SugestiaPunktacji(pz.punkty_kbn, f"Punktacja źródła {rok}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_punktacja_sugestia.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/punktacja_sugestia.py src/bpp/tests/test_punktacja_sugestia.py
git commit -m "feat(punktacja): czysta funkcja sugestii dla ciaglych (#384)"
```

---

### Task 3: Refaktor `ustaw_zwrotnie_punkty_zwartych` na współdzieloną funkcję

**Files:**
- Modify: `src/pbn_api/management/commands/ustaw_zwrotnie_punkty_zwartych.py`
- Test: `src/pbn_api/tests/test_ustaw_zwrotnie_punkty_zwartych_refactor.py`

**Interfaces:**
- Consumes: `zaproponuj_punkty_zwarte`, `RodzajBraku` (Task 1).

- [ ] **Step 1: Write the failing regression test**

```python
# src/pbn_api/tests/test_ustaw_zwrotnie_punkty_zwartych_refactor.py
from decimal import Decimal

import pytest
from model_bakery import baker

from bpp import const


@pytest.fixture
def wydawca_poziom_II(db):
    from bpp.models import Poziom_Wydawcy, Wydawca

    w = baker.make(Wydawca)
    baker.make(Poziom_Wydawcy, wydawca=w, rok=2023, poziom=2)
    return w


def _zwarte_ksiazka_autorska(wydawca, typy_odpowiedzialnosci, charaktery_formalne):
    from bpp.models import Charakter_Formalny, Wydawnictwo_Zwarte

    cf = Charakter_Formalny.objects.filter(
        charakter_sloty=const.CHARAKTER_SLOTY_KSIAZKA
    ).first()
    rekord = baker.make(
        Wydawnictwo_Zwarte, wydawca=wydawca, rok=2023, charakter_formalny=cf,
        punkty_kbn=Decimal(0),
    )
    rekord.dodaj_autora(
        autor=baker.make("bpp.Autor"), jednostka=baker.make("bpp.Jednostka"),
        typ_odpowiedzialnosci_skrot="aut.",
    )
    return rekord


@pytest.mark.django_db
def test_komenda_ustawia_200_dla_monografii_poziom_II(
    wydawca_poziom_II, typy_odpowiedzialnosci, charaktery_formalne
):
    from django.core.management import call_command

    rekord = _zwarte_ksiazka_autorska(
        wydawca_poziom_II, typy_odpowiedzialnosci, charaktery_formalne
    )
    call_command("ustaw_zwrotnie_punkty_zwartych", min_rok=2023)
    rekord.refresh_from_db()
    assert rekord.punkty_kbn == Decimal(200)
```

- [ ] **Step 2: Run test to verify it passes on the OLD code (baseline)**

Run: `uv run pytest src/pbn_api/tests/test_ustaw_zwrotnie_punkty_zwartych_refactor.py -v`
Expected: PASS (potwierdza zachowanie PRZED refaktorem — to test regresyjny; ma
przejść i przed, i po zmianie implementacji).

- [ ] **Step 3: Refaktor implementacji `_przetworz`/`handle`**

Zastąp `handle` i `_przetworz` (linie 51-134) w
`src/pbn_api/management/commands/ustaw_zwrotnie_punkty_zwartych.py`:

```python
    def handle(self, min_rok, overwrite=False, ignore_errors=False, *args, **kw):
        queryset = Wydawnictwo_Zwarte.objects.filter(rok__gte=min_rok)
        if not overwrite:
            queryset = queryset.exclude(punkty_kbn__gt=0)

        for elem in tqdm(queryset, disable=None):
            try:
                self._przetworz(elem)
            except (RekordBezPunktowalnegoAutorstwa, RekordBezWydawcy) as exc:
                tqdm.write(f"POMINIĘTO pk={elem.pk} ({elem}): {komunikat_bledu(exc)}")
            except Exception as exc:
                if not ignore_errors:
                    raise
                tqdm.write(f"POMINIĘTO pk={elem.pk} ({elem}): {komunikat_bledu(exc)}")

    def _przetworz(self, elem):
        if elem.wydawca is None:
            raise RekordBezWydawcy(
                f"rekord zwarty bez wydawcy — brak podstawy do tieru "
                f"punktacji (rok={elem.rok})",
                elem,
            )

        sugestia = zaproponuj_punkty_zwarte(
            poziom=elem.wydawca.get_tier(elem.rok),
            ksiazka=bool(elem.warunek_ksiazka()),
            rozdzial=bool(elem.warunek_rozdzial()),
            autorstwo=elem.warunek_autorstwo(),
            redakcja=elem.warunek_redakcja(),
        )

        if sugestia.punkty is not None:
            elem.punkty_kbn = sugestia.punkty
            elem.save()
            return

        if sugestia.rodzaj_braku == RodzajBraku.BRAK_AUTORSTWA:
            raise RekordBezPunktowalnegoAutorstwa(
                sugestia.powod_braku, elem, elem.autorzy_set.all()
            )

        raise NotImplementedError(
            sugestia.powod_braku, elem, elem.autorzy_set.all()
        )
```

Dodaj import na górze pliku (po linii 4):

```python
from bpp.punktacja_sugestia import RodzajBraku, zaproponuj_punkty_zwarte
```

- [ ] **Step 4: Run tests (regresja + istniejące testy komendy)**

Run: `uv run pytest src/pbn_api/tests/test_ustaw_zwrotnie_punkty_zwartych_refactor.py src/pbn_api/tests/test_ustaw_zwrotnie_punkty_ignore_errors.py -v`
Expected: PASS (regresja + istniejące testy ignore-errors nadal zielone; twardy
`NotImplementedError` bez `--ignore-errors` zachowany).

- [ ] **Step 5: Commit**

```bash
git add src/pbn_api/management/commands/ustaw_zwrotnie_punkty_zwartych.py src/pbn_api/tests/test_ustaw_zwrotnie_punkty_zwartych_refactor.py
git commit -m "refactor(pbn): ustaw_zwrotnie_punkty_zwartych uzywa wspolnej funkcji (#384)"
```

---

### Task 4: Pole `typ_ogolny` na `ImportedAuthor` + migracja

**Files:**
- Modify: `src/importer_publikacji/models.py:265` (klasa `ImportedAuthor`)
- Create: `src/importer_publikacji/migrations/0014_importedauthor_typ_ogolny.py` (wygenerowana)
- Test: `src/importer_publikacji/tests/test_models.py`

**Interfaces:**
- Produces: `ImportedAuthor.typ_ogolny` (SmallInteger, `const.TO_AUTOR`/`TO_REDAKTOR`, default `TO_AUTOR`).

- [ ] **Step 1: Write the failing test**

```python
# dopisz do src/importer_publikacji/tests/test_models.py
import pytest
from model_bakery import baker

from bpp import const


@pytest.mark.django_db
def test_imported_author_domyslnie_autor():
    from importer_publikacji.models import ImportedAuthor, ImportSession

    session = baker.make(ImportSession)
    autor = baker.make(ImportedAuthor, session=session, order=0)
    assert autor.typ_ogolny == const.TO_AUTOR
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/importer_publikacji/tests/test_models.py::test_imported_author_domyslnie_autor -v`
Expected: FAIL — `AttributeError: 'ImportedAuthor' object has no attribute 'typ_ogolny'`.

- [ ] **Step 3: Dodaj pole + migracja**

W `src/importer_publikacji/models.py` upewnij się o imporcie (góra pliku):

```python
from bpp import const
```

Po polu `matched_dyscyplina` (kończy się na `verbose_name="dyscyplina",\n    )`),
przed `dyscyplina_source`, dodaj:

```python
    typ_ogolny = models.SmallIntegerField(
        "typ autora",
        choices=[
            (const.TO_AUTOR, "autor"),
            (const.TO_REDAKTOR, "redaktor"),
        ],
        default=const.TO_AUTOR,
    )
```

Wygeneruj migrację:

```bash
DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations importer_publikacji
```

Oczekiwane: nowa migracja `0014_importedauthor_typ_ogolny.py` (AddField, default).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/importer_publikacji/tests/test_models.py::test_imported_author_domyslnie_autor -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/models.py src/importer_publikacji/migrations/0014_*.py src/importer_publikacji/tests/test_models.py
git commit -m "feat(importer): pole typ_ogolny (autor/redaktor) na ImportedAuthor (#384)"
```

---

### Task 5: `AuthorMatchForm.typ` + zapis w `AuthorMatchView`

**Files:**
- Modify: `src/importer_publikacji/forms.py:155` (`AuthorMatchForm`)
- Modify: `src/importer_publikacji/views/wizard.py:344` (`AuthorMatchView.post`)
- Test: `src/importer_publikacji/tests/test_auto_match_authors.py`

**Interfaces:**
- Consumes: `ImportedAuthor.typ_ogolny` (Task 4).

- [ ] **Step 1: Write the failing test**

```python
# dopisz do src/importer_publikacji/tests/test_auto_match_authors.py
def test_author_match_view_zapisuje_typ_redaktor(session, importer_client):
    from django.urls import reverse

    from bpp import const
    from bpp.models import Autor
    from importer_publikacji.models import ImportedAuthor

    autor = baker.make(Autor)
    imp = baker.make(ImportedAuthor, session=session, order=0)
    url = reverse("importer_publikacji:author-match", args=[session.pk, imp.pk])
    response = importer_client.post(
        url, {"autor": autor.pk, "typ": const.TO_REDAKTOR}
    )
    assert response.status_code == 200
    imp.refresh_from_db()
    assert imp.typ_ogolny == const.TO_REDAKTOR
```

(Fixtura `session` istnieje w tym pliku: `baker.make(ImportSession)`. `baker` i
`Autor` już importowane.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/importer_publikacji/tests/test_auto_match_authors.py::test_author_match_view_zapisuje_typ_redaktor -v`
Expected: FAIL — `imp.typ_ogolny == 0` (POST-owany `typ` ignorowany).

- [ ] **Step 3: Dodaj pole do formularza i zapis w widoku**

W `src/importer_publikacji/forms.py` w `AuthorMatchForm` (po polu `zapisany_jako`)
dodaj (import `from bpp import const` na górze pliku, jeśli brak):

```python
    typ = forms.TypedChoiceField(
        label="Typ autora",
        choices=[
            (const.TO_AUTOR, "autor"),
            (const.TO_REDAKTOR, "redaktor"),
        ],
        coerce=int,
        empty_value=None,
        required=False,
    )
```

W `src/importer_publikacji/views/wizard.py` w `AuthorMatchView.post`, zaraz po
bloku zapisującym `zapisany_jako` (po `imported_author.zapisany_jako = zj`),
dodaj (niezależnie od stanu dopasowania — redaktor też bywa niedopasowany):

```python
        typ = form.cleaned_data.get("typ")
        if typ is not None:
            imported_author.typ_ogolny = typ
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/importer_publikacji/tests/test_auto_match_authors.py -v`
Expected: PASS (nowy test + istniejące, w tym `test_author_match_view_zapisuje_zapisany_jako`).

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/forms.py src/importer_publikacji/views/wizard.py src/importer_publikacji/tests/test_auto_match_authors.py
git commit -m "feat(importer): wybor typu autora w modalu edycji (#384)"
```

---

### Task 6: `_add_authors_to_record` respektuje rolę

**Files:**
- Modify: `src/importer_publikacji/views/publikacja.py:109-149`
- Test: `src/importer_publikacji/tests/test_add_authors_typ.py`

**Interfaces:**
- Consumes: `ImportedAuthor.typ_ogolny` (Task 4).

- [ ] **Step 1: Write the failing test**

```python
# src/importer_publikacji/tests/test_add_authors_typ.py
import pytest
from model_bakery import baker

from bpp import const


@pytest.mark.django_db
def test_add_authors_tworzy_redaktora(typy_odpowiedzialnosci):
    from bpp.models import Autor, Jednostka, Wydawnictwo_Zwarte
    from importer_publikacji.models import ImportedAuthor, ImportSession
    from importer_publikacji.views.publikacja import _add_authors_to_record

    session = baker.make(ImportSession)
    baker.make(
        ImportedAuthor,
        session=session,
        order=0,
        match_status=ImportedAuthor.MatchStatus.MANUAL,
        matched_autor=baker.make(Autor),
        matched_jednostka=baker.make(Jednostka),
        typ_ogolny=const.TO_REDAKTOR,
    )
    rekord = baker.make(Wydawnictwo_Zwarte)
    _add_authors_to_record(session, rekord)

    wiersz = rekord.autorzy_set.get()
    assert wiersz.typ_odpowiedzialnosci.typ_ogolny == const.TO_REDAKTOR
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/importer_publikacji/tests/test_add_authors_typ.py -v`
Expected: FAIL — utworzony wiersz ma `typ_ogolny == TO_AUTOR` (twardo „aut.").

- [ ] **Step 3: Zmień mapowanie roli**

W `src/importer_publikacji/views/publikacja.py`:

1. Import na górze (po istniejącym `from bpp.models import (...)`):

```python
from bpp import const
```

2. Usuń linię `typ_aut = Typ_Odpowiedzialnosci.objects.get(skrot="aut.")` i dodaj
   przed pętlą stałą mapowania:

```python
    SKROT_DLA_TYPU = {const.TO_AUTOR: "aut.", const.TO_REDAKTOR: "red."}
```

3. W wywołaniu `record.dodaj_autora(...)` zamień
   `typ_odpowiedzialnosci_skrot=typ_aut.skrot,` na:

```python
            typ_odpowiedzialnosci_skrot=SKROT_DLA_TYPU.get(
                imported_author.typ_ogolny, "aut."
            ),
```

(Import `Typ_Odpowiedzialnosci` może zostać — jest używany gdzie indziej; jeśli
ruff zgłosi nieużywany, usuń go z `from bpp.models import (...)`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/importer_publikacji/tests/test_add_authors_typ.py src/importer_publikacji/tests/test_views_create_publication.py -v`
Expected: PASS (nowy test + brak regresji tworzenia publikacji).

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/views/publikacja.py src/importer_publikacji/tests/test_add_authors_typ.py
git commit -m "feat(importer): _add_authors_to_record respektuje typ autora (#384)"
```

---

### Task 7: UI kolumny „Typ" w kroku autorów (szablony + JS)

**Files:**
- Modify: `src/importer_publikacji/templates/importer_publikacji/partials/author_row.html`
- Modify: `src/importer_publikacji/templates/importer_publikacji/partials/step_authors.html`

**Interfaces:** UI only — czyta `author.typ_ogolny`, POST-uje `typ` (Task 5).

**Uwaga o indeksach DataTables:** nową kolumnę „Typ" wstawiamy **przed** „Akcje"
(ostatnią). Kolumny filtrowane `selectCols = [3, 5, 6, 7]` i `textCols=[{idx:1}]`
(`step_authors.html:362-367`) się NIE przesuwają (Typ = idx 8, Akcje → idx 9);
indeksów NIE zmieniamy.

- [ ] **Step 1: Nagłówek tabeli** — w `step_authors.html:149-168` dodaj `<th>` przed „Akcje":

```django
                <th>Źródło dyscypliny</th>
                <th>Typ</th>
                <th>Akcje</th>
```

- [ ] **Step 2: Komórka + `data-typ` w wierszu** — w `author_row.html`:

W otwarciu `<tr ...>` (po `data-zapisany-jako=...`) dodaj:

```django
    data-typ="{{ author.typ_ogolny }}"
```

Przed `<td>` z „Akcje" (blok od `:73`) dodaj komórkę:

```django
        <td>{% if author.typ_ogolny == 1 %}redaktor{% else %}autor{% endif %}</td>
```

- [ ] **Step 3: Pole `<select>` w modalu** — w `step_authors.html` w formularzu
  `#modal-author-form` (po grupie `zapisany_jako`, ~`:301`) dodaj:

```django
                <div class="field-group">
                    <label class="field-label" for="modal-typ-select">Typ autora</label>
                    <div class="field-input">
                        <select id="modal-typ-select" name="typ">
                            <option value="0">autor</option>
                            <option value="1">redaktor</option>
                        </select>
                    </div>
                </div>
```

- [ ] **Step 4: Prefill + submit** — w `step_authors.html`:

W `openAuthorModal($row)` (~`:807`) dodaj odczyt i ustawienie wartości:

```javascript
        $('#modal-typ-select').val(String($row.data('typ') || '0'));
```

W obiekcie `values: {...}` submitu modala (~`:952`) dodaj klucz:

```javascript
                    dyscyplina: $('#modal-dyscyplina-select').val() || '',
                    typ: $('#modal-typ-select').val() || '0'
```

- [ ] **Step 5: Weryfikacja assetów + commit**

Run: `cd /Users/mpasternak/Programowanie/bpp-384-sugeruj-punktacje-importer && make tests-without-playwright 2>&1 | tail -5` — sanity (żaden test szablonowy się nie wywala). Ręczna weryfikacja UI nastąpi w Task 12 przez `run-site`.

```bash
git add src/importer_publikacji/templates/importer_publikacji/partials/author_row.html src/importer_publikacji/templates/importer_publikacji/partials/step_authors.html
git commit -m "feat(importer): kolumna Typ (autor/redaktor) w kroku autorow (#384)"
```

---

### Task 8: `Status.PUNKTACJA` + `get_continue_url` + migracja

**Files:**
- Modify: `src/importer_publikacji/models.py:16-29` (Status) i `:195-215` (`get_continue_url`)
- Create: `src/importer_publikacji/migrations/0015_*.py` (wygenerowana)
- Test: `src/importer_publikacji/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# dopisz do src/importer_publikacji/tests/test_models.py
@pytest.mark.django_db
def test_get_continue_url_punktacja_po_autorach():
    from importer_publikacji.models import ImportSession

    s = baker.make(
        ImportSession, status=ImportSession.Status.AUTHORS_MATCHED
    )
    assert s.get_continue_url().endswith(f"/{s.pk}/punktacja/")

    s.status = ImportSession.Status.PUNKTACJA
    assert s.get_continue_url().endswith(f"/{s.pk}/review/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/importer_publikacji/tests/test_models.py::test_get_continue_url_punktacja_po_autorach -v`
Expected: FAIL — `AttributeError: PUNKTACJA` / URL kończy się na `/review/` dla AUTHORS_MATCHED.

- [ ] **Step 3: Dodaj status i przemapuj**

W `Status` (models.py) po `AUTHORS_MATCHED`:

```python
    PUNKTACJA = "punktacja", "Punktacja"
```

W `get_continue_url` w `status_url_map` zmień wpis `AUTHORS_MATCHED` i dodaj `PUNKTACJA`:

```python
        self.Status.AUTHORS_MATCHED: "punktacja",
        self.Status.PUNKTACJA: "review",
```

Wygeneruj migrację (AlterField choices):

```bash
DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations importer_publikacji
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/importer_publikacji/tests/test_models.py -v`
Expected: PASS. (URL `punktacja` istnieje dopiero po Task 9 — jeśli `reverse`
zawiedzie, wykonaj Task 9 Step „urls" przed uruchomieniem; patrz zależność niżej.)

**Zależność:** `get_continue_url` woła `reverse("importer_publikacji:punktacja")`,
który wymaga URL-a z Task 9. Wykonaj Task 9 Step 3 (urls + widok + re-export)
przed uruchomieniem tego testu, albo scal Task 8+9 w jednym przebiegu.

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/models.py src/importer_publikacji/migrations/0015_*.py src/importer_publikacji/tests/test_models.py
git commit -m "feat(importer): Status.PUNKTACJA + routing kroku (#384)"
```

---

### Task 9: Krok „Punktacja" — widok, renderer, URL, szablon, wpięcie

**Files:**
- Modify: `src/importer_publikacji/views/wizard.py` (nowy `PunktacjaView`; `AuthorsConfirmView.post:546`)
- Modify: `src/importer_publikacji/views/steps.py` (renderery)
- Modify: `src/importer_publikacji/views/helpers.py:25` (`STEP_PUNKTACJA`)
- Modify: `src/importer_publikacji/urls.py`, `views/__init__.py`, `forms.py`
- Create: `src/importer_publikacji/templates/importer_publikacji/partials/step_punktacja.html`
- Modify: `partials/step_review.html` (Wstecz → punktacja)
- Test: `src/importer_publikacji/tests/test_views_punktacja.py`

**Interfaces:**
- Produces: URL name `punktacja`; `PunktacjaView`; `_render_punktacja_step(request, session, form=None)`.
- Consumes: `_render_review_step` (istniejący), `SugestiaPunktacji`/funkcje (Task 1-2), role (Task 4-6).

- [ ] **Step 1: Write the failing test**

```python
# src/importer_publikacji/tests/test_views_punktacja.py
from decimal import Decimal

import pytest
from model_bakery import baker


@pytest.fixture
def _sesja_ciagla(importer_user):
    from bpp.models import Charakter_Formalny, Jezyk, Punktacja_Zrodla, Typ_KBN, Zrodlo
    from importer_publikacji.models import ImportSession

    zrodlo = baker.make(Zrodlo)
    baker.make(Punktacja_Zrodla, zrodlo=zrodlo, rok=2024, punkty_kbn=Decimal(140))
    return ImportSession.objects.create(
        created_by=importer_user, provider_name="CrossRef", identifier="10.1/x",
        raw_data={}, normalized_data={"year": 2024, "title": "T", "authors": []},
        zrodlo=zrodlo, jest_wydawnictwem_zwartym=False,
        status=ImportSession.Status.AUTHORS_MATCHED,
    )


@pytest.mark.django_db
def test_punktacja_get_proponuje_z_zrodla(
    _sesja_ciagla, importer_client, charaktery_formalne, typy_kbn, jezyki
):
    from django.urls import reverse

    url = reverse("importer_publikacji:punktacja", args=[_sesja_ciagla.pk])
    resp = importer_client.get(url, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert b"140" in resp.content  # sugestia widoczna czarno na bialym


@pytest.mark.django_db
def test_punktacja_post_zapisuje_i_idzie_do_review(
    _sesja_ciagla, importer_client, charaktery_formalne, typy_kbn, jezyki
):
    from django.urls import reverse

    url = reverse("importer_publikacji:punktacja", args=[_sesja_ciagla.pk])
    resp = importer_client.post(url, {"punkty_kbn": "100"})
    assert resp.status_code == 200
    _sesja_ciagla.refresh_from_db()
    assert _sesja_ciagla.matched_data.get("punkty_kbn") == "100"
    assert _sesja_ciagla.status == _sesja_ciagla.Status.PUNKTACJA
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/importer_publikacji/tests/test_views_punktacja.py -v`
Expected: FAIL — `NoReverseMatch: 'punktacja'`.

- [ ] **Step 3: Implementacja (forms, helpers, steps, view, urls, __init__, template)**

**3a. `forms.py`** — nowa forma:

```python
class PunktacjaForm(forms.Form):
    """Formularz kroku punktacji — jedno pole, edytowalne."""

    punkty_kbn = forms.DecimalField(
        label="Punkty MNiSW", required=False, min_value=0,
    )
```

**3b. `views/helpers.py:25`** — dodaj stałą przy pozostałych `STEP_*`:

```python
STEP_PUNKTACJA = "importer_publikacji/partials/step_punktacja.html"
```

**3c. `views/steps.py`** — dodaj renderery (import na górze: `from ..forms import
PunktacjaForm`, `from bpp import const`, `from bpp.punktacja_sugestia import
RodzajBraku, SugestiaPunktacji, zaproponuj_punkty_ciagle, zaproponuj_punkty_zwarte`,
`from .helpers import STEP_PUNKTACJA`):

```python
def _oblicz_sugestie(session):
    rok = session.normalized_data.get("year")
    if session.jest_wydawnictwem_zwartym:
        wydawca = session.wydawca
        if wydawca is None:
            return SugestiaPunktacji(
                None, rodzaj_braku=RodzajBraku.BRAK_WYDAWCY,
                powod_braku="Brak wydawcy — nie można zaproponować punktacji",
            ), None
        if not rok:
            return SugestiaPunktacji(
                None, rodzaj_braku=RodzajBraku.BRAK_ROKU,
                powod_braku="Brak roku publikacji",
            ), wydawca.get_tier(rok) if rok else None
        cf = session.charakter_formalny
        matched = session.authors.exclude(matched_autor=None)
        poziom = wydawca.get_tier(rok)
        sugestia = zaproponuj_punkty_zwarte(
            poziom=poziom,
            ksiazka=bool(cf and cf.charakter_sloty == const.CHARAKTER_SLOTY_KSIAZKA),
            rozdzial=bool(cf and cf.charakter_sloty == const.CHARAKTER_SLOTY_ROZDZIAL),
            autorstwo=matched.filter(typ_ogolny=const.TO_AUTOR).exists(),
            redakcja=matched.filter(typ_ogolny=const.TO_REDAKTOR).exists(),
        )
        return sugestia, poziom
    return zaproponuj_punkty_ciagle(session.zrodlo, rok), None


def _punktacja_context(request, session, form=None):
    from bpp.models import Punktacja_Zrodla

    sugestia, poziom = _oblicz_sugestie(session)
    rok = session.normalized_data.get("year")

    punktacja_zrodla = None
    if not session.jest_wydawnictwem_zwartym and session.zrodlo and rok:
        punktacja_zrodla = Punktacja_Zrodla.objects.filter(
            zrodlo=session.zrodlo, rok=rok
        ).first()

    ostrzezenie_hst = any(
        a.matched_dyscyplina.dyscyplina_hst
        for a in session.authors.exclude(matched_dyscyplina=None)
    )

    if form is None:
        zapisane = session.matched_data.get("punkty_kbn")
        initial = {
            "punkty_kbn": zapisane if zapisane not in (None, "") else sugestia.punkty
        }
        form = PunktacjaForm(initial=initial)

    return {
        "session": session,
        "form": form,
        "sugestia": sugestia,
        "punktacja_zrodla": punktacja_zrodla,
        "poziom_wydawcy": poziom,
        "rok": rok,
        "ostrzezenie_hst": ostrzezenie_hst,
    }


def _render_punktacja_step(request, session, form=None):
    ctx = _punktacja_context(request, session, form)
    url = reverse(
        "importer_publikacji:punktacja", kwargs={"session_id": session.pk}
    )
    response = render(request, STEP_PUNKTACJA, ctx)
    response = _with_breadcrumbs_oob(response, request, session)
    return _push_url(response, url)


def _render_punktacja_full(request, session, form=None):
    ctx = _punktacja_context(request, session, form)
    return _render_full_page(request, STEP_PUNKTACJA, ctx)
```

(Dodaj `_render_full_page` do importu z `.helpers`, jeśli nie jest.)

**3d. `views/wizard.py`** — nowy widok (wzorzec `SourceView`); import
`from .steps import _render_punktacja_step` oraz `from ..forms import PunktacjaForm`:

```python
class PunktacjaView(ImporterPermissionMixin, View):
    """Krok sugerowania punktacji ministerialnej."""

    def get(self, request, session_id):
        session = get_object_or_404(ImportSession, pk=session_id)
        if request.headers.get("HX-Request"):
            return _render_punktacja_step(request, session)
        from .steps import _render_punktacja_full

        return _render_punktacja_full(request, session)

    def post(self, request, session_id):
        session = get_object_or_404(ImportSession, pk=session_id)
        form = PunktacjaForm(request.POST)
        if not form.is_valid():
            return _render_punktacja_step(request, session, form=form)

        punkty = form.cleaned_data.get("punkty_kbn")
        session.matched_data["punkty_kbn"] = "" if punkty is None else str(punkty)
        session.status = ImportSession.Status.PUNKTACJA
        session.modified_by = request.user
        session.save()

        return _render_review_step(request, session)
```

Zmień `AuthorsConfirmView.post` (linia 546): `return _render_review_step(...)` →
`return _render_punktacja_step(request, session)`.

**3e. `urls.py`** — między `authors-confirm` a `review`:

```python
    path(
        "<int:session_id>/punktacja/",
        views.PunktacjaView.as_view(),
        name="punktacja",
    ),
```

**3f. `views/__init__.py`** — re-eksport `PunktacjaView` (i dodaj do `__all__`,
jeśli plik go używa).

**3g. Szablon** `partials/step_punktacja.html` (mirror `step_source.html`):

```django
<div class="callout">
    <h4><span class="fi-graph-bar"></span> Krok: Punktacja</h4>

    {% if session.jest_wydawnictwem_zwartym %}
        <p><strong>Wydawca:</strong>
            {{ session.wydawca|default:"— brak —" }}
            {% if poziom_wydawcy is not None and poziom_wydawcy >= 0 %}
                (poziom {{ poziom_wydawcy }})
            {% else %}
                (brak poziomu za {{ rok }} — spoza wykazu)
            {% endif %}
        </p>
    {% else %}
        <p><strong>Źródło:</strong> {{ session.zrodlo|default:"— brak —" }}</p>
        {% if punktacja_zrodla %}
            <p><strong>Punktacja źródła za {{ rok }}:</strong>
                {{ punktacja_zrodla.punkty_kbn }} pkt</p>
        {% else %}
            <p class="warning-text">Brak danych punktacji źródła za {{ rok }}.</p>
        {% endif %}
    {% endif %}

    {% if sugestia.punkty is not None %}
        <div class="callout success">
            Sugerowana punktacja: <strong>{{ sugestia.punkty }} pkt</strong>
            <br><small>{{ sugestia.podstawa }}</small>
        </div>
    {% else %}
        <div class="callout warning">
            Nie można zaproponować punktacji: {{ sugestia.powod_braku }}.
            Wpisz wartość ręcznie lub pozostaw puste.
        </div>
    {% endif %}

    {% if ostrzezenie_hst %}
        <div class="callout alert">
            Autorzy z dyscyplin HST — właściwy próg może być wyższy
            (np. 300 dla monografii). Zweryfikuj wartość.
        </div>
    {% endif %}

    <form hx-post="{% url 'importer_publikacji:punktacja' session.pk %}"
          hx-target="#importer-wizard"
          hx-indicator="#punktacja-spinner">
        {% csrf_token %}
        <div class="field-group">
            <label class="field-label" for="id_punkty_kbn">Punkty MNiSW</label>
            {{ form.punkty_kbn }}
        </div>

        {% if form.errors %}
            <div class="callout alert">
                {% for field, errors in form.errors.items %}
                    {% for error in errors %}<p>{{ error }}</p>{% endfor %}
                {% endfor %}
            </div>
        {% endif %}

        <button type="button" class="button secondary"
                hx-get="{% url 'importer_publikacji:authors' session.pk %}"
                hx-target="#importer-wizard">
            <span class="fi-arrow-left"></span> Wstecz
        </button>
        <button type="submit" class="button">Dalej <span class="fi-arrow-right"></span></button>
    </form>

    <div id="punktacja-spinner" class="htmx-indicator">
        <span class="fi-loop"></span> Przetwarzanie...
    </div>
</div>
```

**3h. `partials/step_review.html`** — przycisk „Wstecz" (jeśli obecny, kieruje do
`authors`) przekieruj na `punktacja`: zmień `{% url 'importer_publikacji:authors' session.pk %}`
w przycisku Wstecz na `{% url 'importer_publikacji:punktacja' session.pk %}`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/importer_publikacji/tests/test_views_punktacja.py src/importer_publikacji/tests/test_models.py -v`
Expected: PASS (krok + routing z Task 8).

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/
git commit -m "feat(importer): krok Punktacja z sugestia (ciagle+zwarte) (#384)"
```

---

### Task 10: Zastosowanie wybranej punktacji przy tworzeniu rekordu

**Files:**
- Modify: `src/importer_publikacji/views/publikacja.py:216-278` (`_create_publication`)
- Test: `src/importer_publikacji/tests/test_views_create_publication.py`

**Interfaces:**
- Consumes: `session.matched_data["punkty_kbn"]` (Task 9); `uzupelnij_punktacje_z_zrodla`.

- [ ] **Step 1: Write the failing test**

```python
# dopisz do src/importer_publikacji/tests/test_views_create_publication.py
@pytest.mark.django_db
def test_create_ciagle_operator_nadpisuje_punkty_kbn_po_zrodle(
    charaktery_formalne, typy_kbn, jezyki, statusy_korekt, typy_odpowiedzialnosci
):
    from decimal import Decimal

    from bpp.models import Punktacja_Zrodla, Zrodlo
    from importer_publikacji.models import ImportSession
    from importer_publikacji.views import _create_publication

    zrodlo = baker.make(Zrodlo)
    baker.make(
        Punktacja_Zrodla, zrodlo=zrodlo, rok=2024,
        punkty_kbn=Decimal(140), impact_factor=Decimal("3.5"),
    )
    session = baker.make(
        ImportSession, zrodlo=zrodlo, jest_wydawnictwem_zwartym=False,
        normalized_data={"year": 2024, "title": "T", "authors": []},
        matched_data={"punkty_kbn": "100"},
    )
    record = _create_publication(session)
    assert record.punkty_kbn == Decimal(100)      # operator ma ostatnie slowo
    assert record.impact_factor == Decimal("3.5")  # IF ze zrodla zachowany
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/importer_publikacji/tests/test_views_create_publication.py::test_create_ciagle_operator_nadpisuje_punkty_kbn_po_zrodle -v`
Expected: FAIL — `record.punkty_kbn == Decimal(140)` (brak nadpisania operatorem).

- [ ] **Step 3: Zastosuj wartość operatora**

W `src/importer_publikacji/views/publikacja.py` dodaj import u góry:

```python
from decimal import Decimal
```

Zamień blok `uzupelnij_punktacje_z_zrodla` (linie ~269-274) na:

```python
    if session.zrodlo and normalized_data.get("year"):
        from bpp.models.zrodlo import uzupelnij_punktacje_z_zrodla

        uzupelnij_punktacje_z_zrodla(record, session.zrodlo, normalized_data["year"])

    punkty_operator = session.matched_data.get("punkty_kbn")
    if punkty_operator not in (None, ""):
        record.punkty_kbn = Decimal(str(punkty_operator))
        record.save(update_fields=["punkty_kbn"])
```

(Dla zwartych `session.zrodlo` jest None → tylko nadpisanie operatorem; dla
ciągłych pełny fill ze źródła, potem nadpisanie `punkty_kbn`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/importer_publikacji/tests/test_views_create_publication.py -v`
Expected: PASS (nowy test + istniejące 10).

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/views/publikacja.py src/importer_publikacji/tests/test_views_create_publication.py
git commit -m "feat(importer): zastosuj wybrana punktacje przy tworzeniu rekordu (#384)"
```

---

### Task 11: Baseline + pełne testy + ręczna weryfikacja UI

**Files:** brak zmian kodu (walidacja).

- [ ] **Step 1: Odśwież baseline (po migracjach 0014/0015)**

Run: `cd /Users/mpasternak/Programowanie/bpp-384-sugeruj-punktacje-importer && make baseline-update`
Expected: mały diff (delta nowych migracji importer_publikacji). Commit obu plików:

```bash
git add baseline-sql/baseline.sql baseline-sql/baseline.meta.json
git commit -m "chore(baseline): update po migracjach importera (#384)"
```

- [ ] **Step 2: `makemigrations --check` (brak driftu)**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run`
Expected: „No changes detected".

- [ ] **Step 3: ruff**

Run: `ruff format . && ruff check src/importer_publikacji/ src/bpp/punktacja_sugestia.py src/pbn_api/management/commands/ustaw_zwrotnie_punkty_zwartych.py`
Expected: czysto. Napraw ręcznie ewentualne uwagi (bez `--fix` batch).

- [ ] **Step 4: Pełne testy dotkniętych obszarów**

Run: `uv run pytest src/importer_publikacji/ src/bpp/tests/test_punktacja_sugestia.py src/pbn_api/tests/test_ustaw_zwrotnie_punkty_zwartych_refactor.py -v`
Expected: all PASS.

- [ ] **Step 5: Ręczna weryfikacja UI (run-site)**

Run: `uv run run-site run --no-browser` w tle; zaloguj się autologinem; przejdź
importer: dodaj publikację → w kroku autorów ustaw jednego autora jako „redaktor" →
krok Punktacja pokazuje źródło/wydawcę + poziom + sugestię (albo „brak danych" +
powód) → zmień wartość → Review pokazuje wybraną punktację → utwórz rekord →
sprawdź `punkty_kbn` i typ odpowiedzialności redaktora na utworzonym rekordzie.

- [ ] **Step 6: Commit (jeśli ruff coś zmienił) i push**

```bash
git add -A && git commit -m "chore: ruff + finalizacja (#384)" || true
git push -u origin fd-384-sugeruj-punktacje-importer
```

---

## Self-Review (autor planu)

- **Pokrycie specu:** §5 typy → Task 1; §6 ciągłe → Task 2, 10; §7 zwarte +
  refaktor komendy → Task 1, 3; §4b typ autora → Task 4-7; §4/§8 plumbing kroku →
  Task 8-9; §9-A HST warning → Task 9 (`ostrzezenie_hst`); §9-C braki danych →
  Task 9 (`_oblicz_sugestie`); §3 zapis wartości → Task 10; §10 testy → każdy Task.
- **Zależność Task 8↔9:** `get_continue_url` wymaga URL-a `punktacja` z Task 9 —
  zaznaczone; przy wykonaniu scalić lub wykonać 9-Step-3 przed 8-Step-4.
- **Migracje:** 0014 (typ_ogolny) i 0015 (Status choices) — nowe, nie edytujemy
  istniejących; baseline raz w Task 11.
- **Brak placeholderów:** każdy krok ma konkretny kod/komendę i oczekiwany wynik.
