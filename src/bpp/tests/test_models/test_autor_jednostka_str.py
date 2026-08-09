"""Reprezentacja tekstowa ``Autor_Jednostka`` przy wiszącej referencji.

Po skasowaniu autora ``str()`` bywa wołany na obiekcie ``Autor_Jednostka``,
który wciąż żyje w pamięci, choć jego wiersz (i wiersz autora) już zniknął —
m.in. przez audyt ``easyaudit``, który liczy ``object_repr`` w
``transaction.on_commit`` (patrz analogiczny komentarz w
``bpp/models/jednostka.py``). ``__str__`` ma na to fallback i się nie wywala,
ale raportował ten spodziewany przypadek do Rollbara jako błąd (#1098, #450).

Testujemy OBIE gałęzie rozdzielenia: spodziewany ``ObjectDoesNotExist`` →
log bez Rollbara, wszystko inne → raport jak dotąd.
"""

import logging

import pytest

from bpp.models.autor import Autor, Autor_Jednostka


@pytest.mark.django_db
def test_str_autor_jednostka_dziala_normalnie(autor_jan_kowalski, jednostka):
    aj = Autor_Jednostka.objects.create(autor=autor_jan_kowalski, jednostka=jednostka)

    assert str(autor_jan_kowalski) in str(aj)
    assert jednostka.skrot in str(aj)


@pytest.mark.django_db
def test_str_autor_jednostka_po_skasowaniu_autora_nie_raportuje(
    autor_jan_kowalski, jednostka, mocker, caplog
):
    """Wisząca referencja po kaskadzie → fallback, ale BEZ raportu do Rollbara."""
    report = mocker.patch("bpp.util.wyjatki.rollbar.report_exc_info")

    Autor_Jednostka.objects.create(autor=autor_jan_kowalski, jednostka=jednostka)
    # Świeży obiekt z bazy — bez podpiętego w pamięci cache'u FK ``autor``,
    # dokładnie tak jak w produkcyjnym tracebacku.
    aj = Autor_Jednostka.objects.get(autor=autor_jan_kowalski, jednostka=jednostka)
    # ``hard_delete()``, nie ``delete()``: od fazy 04 ``Autor`` jest modelem
    # soft-delete, więc zwykłe kasowanie zostawia wiersz w bazie i ŻADNA
    # wisząca referencja by nie powstała — a to ją właśnie testujemy.
    # Wiszące referencje nie zniknęły z produkcji razem z soft-deletem:
    # biorą się z twardych kasowań (`hard_delete`, kaskady ORM, ręcznego SQL).
    Autor.objects.filter(pk=autor_jan_kowalski.pk).hard_delete()

    with caplog.at_level(logging.ERROR, logger="bpp.models.autor"):
        assert str(aj) == f"Autor_Jednostka #{aj.pk}"

    assert not report.called, (
        "Spodziewana wisząca referencja nie powinna iść do Rollbara"
    )
    # Wyciszamy Rollbara, NIE diagnostykę — ślad w logu musi zostać.
    assert any("Autor_Jednostka" in r.message for r in caplog.records)


@pytest.mark.django_db
def test_str_autor_jednostka_nadal_raportuje_nieoczekiwane_bledy(
    autor_jan_kowalski, jednostka, mocker
):
    """Druga gałąź: cokolwiek INNEGO niż DoesNotExist nadal idzie do Rollbara.

    Bez tego testu nic nie broni przed cofnięciem całego sensu tej zmiany —
    zamianą ``except ObjectDoesNotExist`` z powrotem na ``except Exception``.
    """
    report = mocker.patch("bpp.util.wyjatki.rollbar.report_exc_info")
    aj = Autor_Jednostka.objects.create(autor=autor_jan_kowalski, jednostka=jednostka)

    # Awaria, która NIE jest wiszącą referencją — np. uszkodzony rekord autora.
    mocker.patch(
        "bpp.models.autor.Autor.__str__", side_effect=RuntimeError("coś padło")
    )

    assert str(aj) == f"Autor_Jednostka #{aj.pk}"
    assert report.called, "Nieoczekiwany błąd MUSI trafić do Rollbara"
