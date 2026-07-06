"""Multi-hosted: domyślna wartość pola ``afiliuje`` w admin-owym formularzu
inline autora (``generuj_formularz_dla_autorow``).

Formularz inline NIE dostaje requestu (świadoma, minimalna decyzja — to tylko
UI-default nowego wiersza). Zamiast zgadywać pierwszą-z-brzegu uczelnię
(``Uczelnia.objects.first()``) używa ``get_single_uczelnia_or_none``:
- single-install → czyta ``domyslnie_afiliuje`` z tej jednej uczelni,
- >1 uczelnia → None → neutralny hardcoded default (True), bez zgadywania.
"""

import pytest

from bpp.admin.core import generuj_formularz_dla_autorow
from bpp.models import Wydawnictwo_Ciagle_Autor


def _form_class():
    return generuj_formularz_dla_autorow(
        Wydawnictwo_Ciagle_Autor, include_rekord=True
    )


@pytest.mark.django_db
def test_afiliuje_default_wiele_uczelni_neutralny(uczelnia1, uczelnia2):
    """>1 uczelnia: bez requestu nie da się ustalić uczelni → neutralny
    default True, NIE ``domyslnie_afiliuje`` pierwszej-z-brzegu (uczelnia1)."""
    uczelnia1.domyslnie_afiliuje = False  # to jest first() (niższy pk)
    uczelnia1.save()

    form = _form_class()()
    assert form.fields["afiliuje"].initial is True


@pytest.mark.django_db
def test_afiliuje_default_single_install_czyta_uczelnie(uczelnia):
    """Single-install: czyta ``domyslnie_afiliuje`` z jedynej uczelni."""
    uczelnia.domyslnie_afiliuje = False
    uczelnia.save()

    form = _form_class()()
    assert form.fields["afiliuje"].initial is False
