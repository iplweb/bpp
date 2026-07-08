from decimal import Decimal

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from import_punktacji_zrodel.core import analyze_jcr_file


@pytest.mark.django_db
def test_repro_fd388_pelny_przebieg(admin_user, jcr_xlsx_path):
    from bpp.models import Punktacja_Zrodla, Zrodlo
    from import_punktacji_zrodel.models import ImportPunktacjiZrodel

    # dwa realne źródła z pliku
    lancet = baker.make(Zrodlo, nazwa="LANCET", issn="0140-6736")
    blood = baker.make(Zrodlo, nazwa="BLOOD", issn="0006-4971")

    imp = baker.make(
        ImportPunktacjiZrodel,
        owner=admin_user,
        rok=2025,
        zapisz_zmiany_do_bazy=True,
        importuj_impact_factor=True,
        importuj_kwartyl_wos=True,
        ignoruj_zrodla_bez_odpowiednika=False,
        nie_porownuj_po_tytulach=False,
    )
    analyze_jcr_file(jcr_xlsx_path, imp, MockProgress(imp))

    # raport pokrywa cały plik (136 czasopism)
    assert imp.get_details_set().count() == 136
    # dopasowane źródła dostały wartości
    pz_lancet = Punktacja_Zrodla.objects.get(zrodlo=lancet, rok=2025)
    assert pz_lancet.impact_factor == Decimal("109.000")
    assert pz_lancet.kwartyl_w_wos == 1
    pz_blood = Punktacja_Zrodla.objects.get(zrodlo=blood, rok=2025)
    assert pz_blood.impact_factor == Decimal("23.900")
    # są też niedopasowane (większość pliku nie ma odpowiednika)
    assert imp.get_details_set().filter(zrodlo__isnull=True).exists()
