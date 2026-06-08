# Import PBN — dopasowanie autorów + odporne przypisywanie dyscyplin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import oświadczeń PBN przestaje wywalać całą sesję na konflikcie dyscyplin, automatycznie dopasowuje współautorów o identycznym imieniu/nazwisku (inne ID) i auto-zakłada przypisania dyscyplin z PBN z sensownymi procentami, zostawiając ślad w logu/uwagach.

**Architecture:** Wydzielony, czysty helper `przypisz_dyscypline_pbn` zna logikę dwóch slotów `Autor_Dyscyplina` (dyscyplina + subdyscyplina) i zwraca enum wyniku. Duża funkcja `integruj_oswiadczenia_z_instytucji_pojedyncza_praca` mapuje wynik na log + `inconsistency_callback`, zamiast podnosić wyjątek. Raporty dopasowania autora są przeniesione tak, by alarm padał dopiero gdy ratunek faktycznie zawiedzie.

**Tech Stack:** Django, pytest (funkcyjny, `@pytest.mark.django_db`), `model_bakery.baker`. Wszystkie komendy Pythona przez `uv run`.

**Spec:** `docs/superpowers/specs/2026-06-07-pbn-import-dyscypliny-dopasowanie-autorow-design.md`

---

## File Structure

- **Create:** `src/pbn_integrator/utils/dyscypliny.py` — enum `WynikPrzypisaniaDyscypliny` + funkcja `przypisz_dyscypline_pbn`. Jedna odpowiedzialność: bezpieczne wpisanie dyscypliny do dwóch slotów `Autor_Dyscyplina` z auto-procentami.
- **Create:** `src/pbn_integrator/tests/test_dyscypliny.py` — unit testy helpera.
- **Modify:** `src/pbn_integrator/utils/statements.py` — wołanie helpera zamiast `raise`; przebudowa kolejności raportów dopasowania autora.
- **Modify:** `src/pbn_integrator/tests/test_statements.py` — testy integracyjne (konflikt bez crasha, dopasowanie po nazwisku, manual_fix).

Brak migracji — model `Autor_Dyscyplina` bez zmian.

---

## Task 1: Helper `przypisz_dyscypline_pbn` (slot-aware, auto-procenty)

**Files:**
- Create: `src/pbn_integrator/utils/dyscypliny.py`
- Test: `src/pbn_integrator/tests/test_dyscypliny.py`

- [ ] **Step 1: Write the failing tests**

Create `src/pbn_integrator/tests/test_dyscypliny.py`:

```python
"""Unit testy helpera przypisz_dyscypline_pbn."""

from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina, Dyscyplina_Naukowa
from pbn_integrator.utils.dyscypliny import (
    WynikPrzypisaniaDyscypliny,
    przypisz_dyscypline_pbn,
)

ROK = 2022


@pytest.fixture
def autor(db):
    return baker.make(Autor)


@pytest.fixture
def dyscyplina_X(db):
    return baker.make(Dyscyplina_Naukowa, nazwa="nauki medyczne", kod="3.2")


@pytest.fixture
def dyscyplina_Y(db):
    return baker.make(Dyscyplina_Naukowa, nazwa="psychologia", kod="5.11")


@pytest.fixture
def dyscyplina_Z(db):
    return baker.make(Dyscyplina_Naukowa, nazwa="nauki prawne", kod="5.7")


@pytest.mark.django_db
def test_brak_wiersza_tworzy_z_procentem_100(autor, dyscyplina_X):
    wynik = przypisz_dyscypline_pbn(autor, ROK, dyscyplina_X)

    assert wynik == WynikPrzypisaniaDyscypliny.UTWORZONO
    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=ROK)
    assert ad.dyscyplina_naukowa == dyscyplina_X
    assert ad.procent_dyscypliny == Decimal("100.00")
    assert ad.subdyscyplina_naukowa is None


@pytest.mark.django_db
def test_dyscyplina_juz_glowna_brak_zmian(autor, dyscyplina_X):
    baker.make(
        Autor_Dyscyplina, autor=autor, rok=ROK, dyscyplina_naukowa=dyscyplina_X
    )

    wynik = przypisz_dyscypline_pbn(autor, ROK, dyscyplina_X)

    assert wynik == WynikPrzypisaniaDyscypliny.BRAK_ZMIAN
    assert Autor_Dyscyplina.objects.filter(autor=autor, rok=ROK).count() == 1


@pytest.mark.django_db
def test_dyscyplina_juz_jako_sub_brak_zmian(autor, dyscyplina_X, dyscyplina_Y):
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        rok=ROK,
        dyscyplina_naukowa=dyscyplina_X,
        subdyscyplina_naukowa=dyscyplina_Y,
    )

    wynik = przypisz_dyscypline_pbn(autor, ROK, dyscyplina_Y)

    assert wynik == WynikPrzypisaniaDyscypliny.BRAK_ZMIAN


@pytest.mark.django_db
def test_pusty_sub_auto_procenty_50_50(autor, dyscyplina_X, dyscyplina_Y):
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        rok=ROK,
        dyscyplina_naukowa=dyscyplina_X,
        procent_dyscypliny=Decimal("100.00"),
        subdyscyplina_naukowa=None,
    )

    wynik = przypisz_dyscypline_pbn(autor, ROK, dyscyplina_Y)

    assert wynik == WynikPrzypisaniaDyscypliny.DODANO_SUB
    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=ROK)
    assert ad.subdyscyplina_naukowa == dyscyplina_Y
    assert ad.procent_dyscypliny == Decimal("50.00")
    assert ad.procent_subdyscypliny == Decimal("50.00")


@pytest.mark.django_db
def test_pusty_sub_z_recznym_podzialem_nie_rusza_procentow(
    autor, dyscyplina_X, dyscyplina_Y
):
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        rok=ROK,
        dyscyplina_naukowa=dyscyplina_X,
        procent_dyscypliny=Decimal("70.00"),
        subdyscyplina_naukowa=None,
    )

    wynik = przypisz_dyscypline_pbn(autor, ROK, dyscyplina_Y)

    assert wynik == WynikPrzypisaniaDyscypliny.DODANO_SUB
    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=ROK)
    assert ad.subdyscyplina_naukowa == dyscyplina_Y
    assert ad.procent_dyscypliny == Decimal("70.00")  # nietknięte
    assert ad.procent_subdyscypliny is None  # do weryfikacji


@pytest.mark.django_db
def test_oba_sloty_zajete_konflikt(autor, dyscyplina_X, dyscyplina_Y, dyscyplina_Z):
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        rok=ROK,
        dyscyplina_naukowa=dyscyplina_X,
        subdyscyplina_naukowa=dyscyplina_Y,
    )

    wynik = przypisz_dyscypline_pbn(autor, ROK, dyscyplina_Z)

    assert wynik == WynikPrzypisaniaDyscypliny.KONFLIKT_BRAK_MIEJSCA
    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=ROK)
    assert ad.dyscyplina_naukowa == dyscyplina_X  # bez zmian
    assert ad.subdyscyplina_naukowa == dyscyplina_Y  # bez zmian
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/pbn_integrator/tests/test_dyscypliny.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pbn_integrator.utils.dyscypliny'`

- [ ] **Step 3: Write the helper**

Create `src/pbn_integrator/utils/dyscypliny.py`:

```python
"""Przypisywanie dyscyplin z PBN do Autor_Dyscyplina.

Slot-aware (dyscyplina_naukowa + subdyscyplina_naukowa), odporne na konflikty:
nigdy nie podnosi wyjątku ani nie nadpisuje ręcznych procentów — zwraca enum
wyniku, a wołający decyduje o logu/raporcie.
"""

from __future__ import annotations

import enum
import logging
from decimal import Decimal

from django.db import transaction

from bpp.models import Autor_Dyscyplina

logger = logging.getLogger(__name__)

PROCENT_100 = Decimal("100.00")
PROCENT_50 = Decimal("50.00")


class WynikPrzypisaniaDyscypliny(enum.Enum):
    BRAK_ZMIAN = "brak_zmian"
    UTWORZONO = "utworzono"
    DODANO_SUB = "dodano_sub"
    KONFLIKT_BRAK_MIEJSCA = "konflikt_brak_miejsca"


def _procenty_wygladaja_na_auto(ad: Autor_Dyscyplina) -> bool:
    """True, gdy procenty nie wyglądają na ręczny podział użytkownika.

    Traktujemy jako "auto" sytuację: brak procentu głównej dyscypliny, albo
    główna = 100% przy pustej sub (to nasz własny wynik auto-utworzenia).
    """
    if ad.procent_dyscypliny is None:
        return True
    return ad.procent_dyscypliny == PROCENT_100 and ad.procent_subdyscypliny is None


def przypisz_dyscypline_pbn(autor, rok, dyscyplina) -> WynikPrzypisaniaDyscypliny:
    """Przypisz `dyscyplina` autorowi na `rok`, korzystając z dwóch slotów.

    Procenty uzupełniamy TYLKO gdy brak danych użytkownika: 100% dla jednej
    dyscypliny, 50/50 dla dwóch. Ręcznych procentów nie nadpisujemy.
    """
    try:
        ad = Autor_Dyscyplina.objects.get(autor=autor, rok=rok)
    except Autor_Dyscyplina.DoesNotExist:
        with transaction.atomic():
            Autor_Dyscyplina.objects.create(
                autor=autor,
                rok=rok,
                dyscyplina_naukowa=dyscyplina,
                procent_dyscypliny=PROCENT_100,
            )
        return WynikPrzypisaniaDyscypliny.UTWORZONO

    if dyscyplina.pk in (ad.dyscyplina_naukowa_id, ad.subdyscyplina_naukowa_id):
        return WynikPrzypisaniaDyscypliny.BRAK_ZMIAN

    if ad.subdyscyplina_naukowa_id is None:
        ad.subdyscyplina_naukowa = dyscyplina
        if _procenty_wygladaja_na_auto(ad):
            ad.procent_dyscypliny = PROCENT_50
            ad.procent_subdyscypliny = PROCENT_50
        # else: zostaw ręczne procenty głównej, sub bez procentu (do weryfikacji)
        with transaction.atomic():
            ad.save()
        return WynikPrzypisaniaDyscypliny.DODANO_SUB

    return WynikPrzypisaniaDyscypliny.KONFLIKT_BRAK_MIEJSCA
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/pbn_integrator/tests/test_dyscypliny.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/pbn_integrator/utils/dyscypliny.py src/pbn_integrator/tests/test_dyscypliny.py
git commit -m "feat(pbn-import): helper przypisz_dyscypline_pbn — slot-aware, auto-procenty

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Wpięcie helpera do statements.py — koniec twardego crasha

**Files:**
- Modify: `src/pbn_integrator/utils/statements.py` (blok dyscyplin ~266-281, importy)
- Test: `src/pbn_integrator/tests/test_statements.py`

- [ ] **Step 1: Write the failing integration test**

Dopisz na końcu `src/pbn_integrator/tests/test_statements.py`. Najpierw upewnij się,
że na górze pliku są importy (dodaj brakujące):

```python
from decimal import Decimal

from bpp.models import Autor, Autor_Dyscyplina, Dyscyplina_Naukowa
```

(`Autor` jest potrzebny w testach Tasku 3; `date`, `baker`, `Publication`,
`OswiadczenieInstytucji`, `Scientist` są już importowane na górze pliku.)

Następnie dopisz test:

```python
@pytest.mark.django_db
def test_konflikt_dyscyplin_nie_wywala_importu(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
    pbn_institution,
    typ_odpowiedzialnosci_autor,
):
    """Dwa sloty zajęte + trzecia dyscyplina z PBN => raport, nie wyjątek."""
    pub = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    autor_rec = pub.autorzy_set.first()
    autor = autor_rec.autor
    rok = pub.rok

    disc_X = baker.make(Dyscyplina_Naukowa, nazwa="medycyna-X", kod="3.21")
    disc_Y = baker.make(Dyscyplina_Naukowa, nazwa="psychologia-Y", kod="5.111")
    disc_Z = baker.make(Dyscyplina_Naukowa, nazwa="bezpieczenstwo-Z", kod="5.3")

    # Autor ma na ten rok dwa sloty zajęte (X + Y)
    Autor_Dyscyplina.objects.filter(autor=autor, rok=rok).delete()
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=rok,
        dyscyplina_naukowa=disc_X,
        subdyscyplina_naukowa=disc_Y,
    )

    pbn_pub = baker.make(Publication, mongoId="konflikt-pub-1")
    pub.pbn_uid = pbn_pub
    pub.save()

    oswiadczenie = OswiadczenieInstytucji.objects.create(
        addedTimestamp=date(2024, 1, 1),
        inOrcid=False,
        institutionId=pbn_institution,
        personId=autor.pbn_uid,
        publicationId=pbn_pub,
        type="AUTHOR",
        disciplines={"name": disc_Z.nazwa},
    )

    zgloszenia = []

    def callback(**kwargs):
        zgloszenia.append(kwargs)

    # NIE powinno podnieść wyjątku
    integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
        oswiadczenie, set(), set(), inconsistency_callback=callback
    )

    typy = [z["inconsistency_type"] for z in zgloszenia]
    assert "discipline_conflict_no_room" in typy

    # Sloty autora bez zmian — Z nie dopisane
    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=rok)
    assert ad.dyscyplina_naukowa == disc_X
    assert ad.subdyscyplina_naukowa == disc_Y
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest src/pbn_integrator/tests/test_statements.py::test_konflikt_dyscyplin_nie_wywala_importu -v`
Expected: FAIL — podniesiony `Exception: Nie ma przypsiania do ... ale jakeis inne jest...` (obecny `raise`).

- [ ] **Step 3: Dodaj import helpera w statements.py**

W `src/pbn_integrator/utils/statements.py`, w bloku importów `from pbn_integrator.utils...`, dodaj:

```python
from pbn_integrator.utils.dyscypliny import (
    WynikPrzypisaniaDyscypliny,
    przypisz_dyscypline_pbn,
)
```

- [ ] **Step 4: Zamień blok dyscyplin na wołanie helpera**

W `src/pbn_integrator/utils/statements.py` zastąp obecny blok (linie ~266-281):

```python
    if elem.disciplines:
        if elem.get_bpp_discipline().pk != rec.dyscyplina_naukowa_id:
            rec.dyscyplina_naukowa_id = elem.get_bpp_discipline().pk
            try:
                rec.clean()
            except ValidationError:
                try:
                    Autor_Dyscyplina.objects.get(rok=rec.rekord.rok, autor=rec.autor)
                    raise Exception(
                        f"Nie ma przypsiania do {elem.get_bpp_discipline()}, ale jakeis inne jest..."
                    )
                except Autor_Dyscyplina.DoesNotExist:
                    rec.autor.autor_dyscyplina_set.update_or_create(
                        rok=rec.rekord.rok,
                        defaults={"dyscyplina_naukowa": elem.get_bpp_discipline()},
                    )
```

nowym blokiem:

```python
    if elem.disciplines:
        discipline = elem.get_bpp_discipline()
        if discipline.pk != rec.dyscyplina_naukowa_id:
            rok = rec.rekord.rok
            wynik = przypisz_dyscypline_pbn(rec.autor, rok, discipline)

            if wynik == WynikPrzypisaniaDyscypliny.KONFLIKT_BRAK_MIEJSCA:
                # Oba sloty Autor_Dyscyplina zajęte inną dyscypliną — NIE
                # ustawiamy rec.dyscyplina_naukowa na D (rec.save() na końcu
                # funkcji nie waliduje, więc utrwaliłby niespójną parę).
                msg = (
                    f"Autor {rec.autor} ma na rok {rok} dwie inne dyscypliny niż "
                    f"{discipline} (praca: {pub}) — nie przypisuję, wymaga ręcznej "
                    f"weryfikacji."
                )
                logger.warning(f"!!! KONFLIKT DYSCYPLIN: {msg}")
                if inconsistency_callback:
                    inconsistency_callback(
                        inconsistency_type="discipline_conflict_no_room",
                        pbn_publication=elem.publicationId,
                        pbn_author=elem.personId,
                        bpp_publication=pub,
                        bpp_author=rec.autor,
                        discipline=discipline,
                        message=msg,
                        action_taken="Brak zmian — oba sloty dyscyplin zajęte",
                    )
            else:
                rec.dyscyplina_naukowa_id = discipline.pk
                if wynik == WynikPrzypisaniaDyscypliny.UTWORZONO:
                    msg = (
                        f"Autorowi {rec.autor} przypisano dyscyplinę {discipline} "
                        f"na podstawie pracy {pub}, rok {rok} — automatycznie, "
                        f"brak danych w BPP."
                    )
                    logger.info(f"AUTO-DYSCYPLINA: {msg}")
                    if inconsistency_callback:
                        inconsistency_callback(
                            inconsistency_type="discipline_auto_assigned",
                            pbn_publication=elem.publicationId,
                            pbn_author=elem.personId,
                            bpp_publication=pub,
                            bpp_author=rec.autor,
                            discipline=discipline,
                            message=msg,
                            action_taken="Utworzono Autor_Dyscyplina (100%)",
                        )
                elif wynik == WynikPrzypisaniaDyscypliny.DODANO_SUB:
                    msg = (
                        f"Autorowi {rec.autor} dopisano subdyscyplinę {discipline} "
                        f"na podstawie pracy {pub}, rok {rok} — automatycznie, "
                        f"brak danych w BPP."
                    )
                    logger.info(f"AUTO-SUBDYSCYPLINA: {msg}")
                    if inconsistency_callback:
                        inconsistency_callback(
                            inconsistency_type="discipline_added_as_sub",
                            pbn_publication=elem.publicationId,
                            pbn_author=elem.personId,
                            bpp_publication=pub,
                            bpp_author=rec.autor,
                            discipline=discipline,
                            message=msg,
                            action_taken="Dopisano subdyscyplinę",
                        )
```

Uwaga (F4): w nowym bloku `discipline` jest policzone RAZ — nie wołaj ponownie
`elem.get_bpp_discipline()`.

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest src/pbn_integrator/tests/test_statements.py::test_konflikt_dyscyplin_nie_wywala_importu -v`
Expected: PASS

- [ ] **Step 6: Sprawdź nieużywany import + cały plik testów**

Po usunięciu `rec.clean()`/`raise` sprawdź, czy `ValidationError` jest jeszcze
używane w `statements.py`:

Run: `grep -n "ValidationError" src/pbn_integrator/utils/statements.py`
Jeśli nie ma już żadnego użycia poza importem — usuń linię
`from django.core.exceptions import ValidationError`. Następnie:

Run: `uv run pytest src/pbn_integrator/tests/test_statements.py -v`
Expected: PASS (wszystkie, łącznie z istniejącymi testami statedTimestamp)

- [ ] **Step 7: Commit**

```bash
git add src/pbn_integrator/utils/statements.py src/pbn_integrator/tests/test_statements.py
git commit -m "fix(pbn-import): konflikt dyscyplin nie wywala importu — raport zamiast raise

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Dopasowanie autora po imieniu/nazwisku — koniec fałszywego author_not_found

**Files:**
- Modify: `src/pbn_integrator/utils/statements.py` (raport ~126, raport ~236, komunikat ~204/211)
- Test: `src/pbn_integrator/tests/test_statements.py`

- [ ] **Step 1: Write the failing integration tests**

Dopisz do `src/pbn_integrator/tests/test_statements.py`:

```python
@pytest.mark.django_db
def test_dopasowanie_po_nazwisku_zamiast_author_not_found(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
    pbn_institution,
    typ_odpowiedzialnosci_autor,
):
    """Współautor o tym samym imieniu/nazwisku (inne ID) => match by name,
    NIE author_not_found."""
    pub = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    autor_rec = pub.autorzy_set.first()
    autor_B = autor_rec.autor  # współautor faktycznie na pracy

    # Autor A: ten sam imię/nazwisko, INNE ID, to on dostaje pbn_uid z oświadczenia
    from pbn_api.models import Scientist

    scientist = baker.make(
        Scientist, lastName=autor_B.nazwisko, name=autor_B.imiona
    )
    autor_A = baker.make(
        Autor,
        nazwisko=autor_B.nazwisko,
        imiona=autor_B.imiona,
        pbn_uid=scientist,
    )
    assert autor_A.pk != autor_B.pk

    pbn_pub = baker.make(Publication, mongoId="match-name-pub-1")
    pub.pbn_uid = pbn_pub
    pub.save()

    oswiadczenie = OswiadczenieInstytucji.objects.create(
        addedTimestamp=date(2024, 1, 1),
        inOrcid=False,
        institutionId=pbn_institution,
        personId=scientist,
        publicationId=pbn_pub,
        type="AUTHOR",
        disciplines={"name": autor_rec.dyscyplina_naukowa.nazwa},
    )

    zgloszenia = []

    def callback(**kwargs):
        zgloszenia.append(kwargs)

    integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
        oswiadczenie, set(), set(), inconsistency_callback=callback
    )

    typy = [z["inconsistency_type"] for z in zgloszenia]
    assert "author_matched_by_name" in typy
    assert "author_not_found" not in typy


@pytest.mark.django_db
def test_autor_spoza_pracy_wymaga_recznej_korekty(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
    pbn_institution,
    typ_odpowiedzialnosci_autor,
):
    """Autor o tym samym imieniu/nazwisku istnieje w BPP, ale NIE jest
    współautorem tej pracy => manual_fix, autor NIE dopisany."""
    pub = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    liczba_autorow_przed = pub.autorzy_set.count()

    from pbn_api.models import Scientist

    scientist = baker.make(Scientist, lastName="Bałdys-Waligórska", name="Agata")
    baker.make(
        Autor, nazwisko="Bałdys-Waligórska", imiona="Agata", pbn_uid=scientist
    )

    pbn_pub = baker.make(Publication, mongoId="manual-fix-pub-1")
    pub.pbn_uid = pbn_pub
    pub.save()

    oswiadczenie = OswiadczenieInstytucji.objects.create(
        addedTimestamp=date(2024, 1, 1),
        inOrcid=False,
        institutionId=pbn_institution,
        personId=scientist,
        publicationId=pbn_pub,
        type="AUTHOR",
        disciplines={"name": pub.autorzy_set.first().dyscyplina_naukowa.nazwa},
    )

    zgloszenia = []

    def callback(**kwargs):
        zgloszenia.append(kwargs)

    integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
        oswiadczenie, set(), set(), inconsistency_callback=callback
    )

    typy = [z["inconsistency_type"] for z in zgloszenia]
    assert "author_needs_manual_fix" in typy
    # Autor NIE został dopisany do publikacji
    assert pub.autorzy_set.count() == liczba_autorow_przed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/pbn_integrator/tests/test_statements.py::test_dopasowanie_po_nazwisku_zamiast_author_not_found src/pbn_integrator/tests/test_statements.py::test_autor_spoza_pracy_wymaga_recznej_korekty -v`
Expected: FAIL — pierwszy test: `author_not_found` jest obecne (raport ~126) i brak `author_matched_by_name`.

- [ ] **Step 3: Usuń przedwczesny raport author_not_found**

W `src/pbn_integrator/utils/statements.py` w bloku `except pub.autorzy_set.model.DoesNotExist:` (po nieudanym tier-1, ~linie 118-135) usuń wywołanie `inconsistency_callback(inconsistency_type="author_not_found", ...)`. Zostaw `logger.info` z `msg` (diagnostyka), ale skasuj cały blok:

```python
        if inconsistency_callback:
            inconsistency_callback(
                inconsistency_type="author_not_found",
                pbn_publication=elem.publicationId,
                pbn_author=elem.personId,
                bpp_publication=pub,
                bpp_author=aut,
                discipline=elem.get_bpp_discipline() if elem.disciplines else None,
                message=msg,
            )
```

(Raport o niedopasowaniu padnie teraz dopiero w gałęzi `author_needs_manual_fix`,
gdy WSZYSTKIE tiery zawiodą.)

- [ ] **Step 4: Zamień author_auto_fixed na author_matched_by_name**

W tym samym pliku, w bloku `if elem.disciplines:` po udanym ratunku (~linie 234-244),
zmień `inconsistency_type="author_auto_fixed"` na `inconsistency_type="author_matched_by_name"`. Reszta argumentów callbacku bez zmian:

```python
            if inconsistency_callback:
                inconsistency_callback(
                    inconsistency_type="author_matched_by_name",
                    pbn_publication=elem.publicationId,
                    pbn_author=elem.personId,
                    bpp_publication=pub,
                    bpp_author=aut,
                    discipline=discipline,
                    message=msg,
                    action_taken=f"Autor zmieniony z {rec.autor} na {aut}",
                )
```

- [ ] **Step 5: Doprecyzuj komunikat manual_fix**

W gałęzi `if rec is None:` (~linie 203-221) zmień `msg` na opisowy:

```python
                if rec is None:
                    msg = (
                        f"Autor {aut} (PBN: {elem.personId}) o tym samym imieniu i "
                        f"nazwisku istnieje w BPP, ale nie figuruje jako współautor "
                        f"pracy {pub} — wymaga ręcznej korekty."
                    )
                    logger.info(
                        f"XXX {msg}\n"
                        "==========================================================="
                    )
```

(Pozostaw istniejące wywołanie `inconsistency_callback(inconsistency_type="author_needs_manual_fix", ...)` poniżej bez zmian — przekaże nowy `msg`.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest src/pbn_integrator/tests/test_statements.py -v`
Expected: PASS (wszystkie testy w pliku)

- [ ] **Step 7: Commit**

```bash
git add src/pbn_integrator/utils/statements.py src/pbn_integrator/tests/test_statements.py
git commit -m "fix(pbn-import): dopasowanie autora po nazwisku zamiast falszywego author_not_found

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Weryfikacja całości + pre-commit

**Files:** brak nowych — kontrola jakości.

- [ ] **Step 1: Uruchom pełny moduł testów PBN integrator/import**

Run: `uv run pytest src/pbn_integrator/tests/test_dyscypliny.py src/pbn_integrator/tests/test_statements.py -v`
Expected: PASS (wszystkie)

- [ ] **Step 2: Pre-commit na zmienionych plikach**

Run: `pre-commit run --files src/pbn_integrator/utils/dyscypliny.py src/pbn_integrator/utils/statements.py src/pbn_integrator/tests/test_dyscypliny.py src/pbn_integrator/tests/test_statements.py`
Expected: wszystkie hooki PASS. Jeśli ruff/format zgłosi problemy — napraw KAŻDY ręcznie przez Edit (NIE `ruff --fix` batch), zgodnie z regułami repo. Zwróć uwagę na limit 88 znaków.

- [ ] **Step 3: Commit ewentualnych poprawek pre-commit**

```bash
git add -A
git commit -m "style(pbn-import): pre-commit fixes

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

(Pomiń, jeśli pre-commit nic nie zmienił.)

---

## Notatki implementacyjne

- **Kolejność tierów dopasowania autora pozostaje bez zmian** — zmieniamy tylko KIEDY i JAKI raport leci, nie samą logikę matchowania (tiery 2-4 już działają poprawnie).
- **Nie dopisujemy autorów do publikacji** — gałąź `manual_fix` świadomie kończy się `return` bez modyfikacji `pub.autorzy_set`.
- **Transakcje:** helper osłania zapisy `transaction.atomic()`, by `IntegrityError` nie unieważnił zewnętrznej transakcji sesji importu.
- **Procenty:** auto-uzupełniamy tylko gdy brak danych użytkownika; „100% + pusty sub" traktujemy jako naszą auto-daną (rebalansowalną do 50/50).
