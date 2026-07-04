"""Track 2 (audyt uczelnia 2026-06-04): raport słotów zerowy zawęża stronę
'existent' (punkty) do uczelni oglądającego.

Połowiczny fix ``29734f833`` dodał parametr ``uczelnia`` do
``autorzy_z_punktami``/``autorzy_zerowi`` w ``core.py``, ale widok
``RaportSlotowZerowyWyniki.get_queryset`` go nie przekazywał — autor z punktami
TYLKO na uczelni U2 był błędnie wykluczany z raportu zerowego uczelni U1
(fałszywy negatyw: ma punkty „gdzieś", więc nie-zerowy, mimo że nie na U1).
"""

from unittest.mock import MagicMock

import pytest
from django.contrib.auth.models import AnonymousUser

from bpp.models import Autor_Dyscyplina
from raport_slotow.forms.zerowy import RaportSlotowZerowyParametryFormularz
from raport_slotow.tests.conftest import _rekord_slotu_maker
from raport_slotow.views.zerowy import RaportSlotowZerowyWyniki


@pytest.mark.django_db
def test_zerowy_zaweza_punkty_do_uczelni_ogladajacego(
    autor_jan_kowalski,
    jednostka,
    jednostka_drugiej_uczelni,
    dyscyplina1,
    wydawnictwo_ciagle_z_autorem,
    rok,
    rf,
):
    uczelnia1 = jednostka.uczelnia

    # strona 'defined' — deklaracja dyscypliny, niezależna od uczelni
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=rok, dyscyplina_naukowa=dyscyplina1
    )

    # strona 'existent' — punkty TYLKO na uczelni U2
    wydawnictwo_ciagle_z_autorem.rok = rok
    wydawnictwo_ciagle_z_autorem.save()
    _rekord_slotu_maker(
        autor_jan_kowalski,
        jednostka_drugiej_uczelni,
        dyscyplina1,
        wydawnictwo_ciagle_z_autorem,
        rok,
    )

    request = rf.get("/")
    request._uczelnia = uczelnia1
    request.user = AnonymousUser()

    view = RaportSlotowZerowyWyniki(min_pk=0)
    view.request = request
    view.form = MagicMock()
    view.form.cleaned_data = {
        "od_roku": rok,
        "do_roku": rok,
        "min_pk": 0,
        "rodzaj_raportu": (
            RaportSlotowZerowyParametryFormularz.RodzajeRaportu.SUMA_LAT
        ),
    }

    autor_ids = set(view.get_queryset().values_list("autor_id", flat=True))

    # Na U1 autor NIE ma punktów → jest zerowy (mimo punktów na U2).
    assert autor_jan_kowalski.id in autor_ids
