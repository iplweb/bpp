"""Reprezentacja tekstowa ``Autor_Jednostka`` przy wiszącej referencji.

Podczas kaskadowego kasowania autora Django potrafi zbudować ``str()``
obiektu ``Autor_Jednostka``, który wciąż żyje w pamięci, choć jego wiersz
(i wiersz autora) już zniknął. ``__str__`` ma na to fallback i nie wywala
się — ale raportował ten spodziewany przypadek do Rollbara jako błąd
(#1098, #450).
"""

import pytest

from bpp.models.autor import Autor, Autor_Jednostka


@pytest.mark.django_db
def test_str_autor_jednostka_dziala_normalnie(autor_jan_kowalski, jednostka):
    aj = Autor_Jednostka.objects.create(autor=autor_jan_kowalski, jednostka=jednostka)

    assert str(autor_jan_kowalski) in str(aj)
    assert jednostka.skrot in str(aj)


@pytest.mark.django_db
def test_str_autor_jednostka_po_skasowaniu_autora_nie_raportuje(
    autor_jan_kowalski, jednostka, mocker
):
    """Wisząca referencja po kaskadzie → fallback, ale BEZ raportu do Rollbara."""
    report = mocker.patch("bpp.util.wyjatki.rollbar.report_exc_info")

    Autor_Jednostka.objects.create(autor=autor_jan_kowalski, jednostka=jednostka)
    # Świeży obiekt z bazy — bez podpiętego w pamięci cache'u FK ``autor``,
    # dokładnie tak jak w produkcyjnym tracebacku.
    aj = Autor_Jednostka.objects.get(autor=autor_jan_kowalski, jednostka=jednostka)
    Autor.objects.filter(pk=autor_jan_kowalski.pk).delete()

    assert str(aj) == f"Autor_Jednostka #{aj.pk}"
    assert not report.called, (
        "Spodziewana wisząca referencja nie powinna iść do Rollbara"
    )
