from decimal import Decimal

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from import_punktacji_zrodel.core import analyze_jcr_file


@pytest.mark.django_db
def test_model_tworzy_sie_i_ma_wiersze(admin_user):
    from import_punktacji_zrodel.models import (
        ImportPunktacjiZrodel,
        WierszImportuPunktacjiZrodel,
    )

    imp = baker.make(ImportPunktacjiZrodel, owner=admin_user, rok=2025)
    WierszImportuPunktacjiZrodel.objects.create(
        parent=imp, dane_z_xls={"nazwa": "X"}, nr_wiersza=1, rezultat="ok"
    )
    assert imp.get_details_set().count() == 1


def _make_import(admin_user, **kw):
    from import_punktacji_zrodel.models import ImportPunktacjiZrodel

    defaults = dict(
        owner=admin_user,
        rok=2025,
        zapisz_zmiany_do_bazy=False,
        importuj_impact_factor=True,
        importuj_kwartyl_wos=True,
        ignoruj_zrodla_bez_odpowiednika=False,
        nie_porownuj_po_tytulach=False,
    )
    defaults.update(kw)
    return baker.make(ImportPunktacjiZrodel, **defaults)


@pytest.mark.django_db
def test_dry_run_nic_nie_zapisuje(admin_user, jcr_xlsx_path):
    from bpp.models import Punktacja_Zrodla, Zrodlo

    zrodlo = baker.make(Zrodlo, nazwa="LANCET", issn="0140-6736")
    imp = _make_import(admin_user, zapisz_zmiany_do_bazy=False)
    analyze_jcr_file(jcr_xlsx_path, imp, MockProgress(imp))

    # dry-run: brak wpisu Punktacja_Zrodla
    assert not Punktacja_Zrodla.objects.filter(zrodlo=zrodlo, rok=2025).exists()
    # ale wiersz raportu istnieje i wskazuje zmianę
    wiersz = imp.get_details_set().get(zrodlo=zrodlo)
    assert wiersz.wymaga_zmian is True


@pytest.mark.django_db
def test_commit_zapisuje_if_i_kwartyl(admin_user, jcr_xlsx_path):
    from bpp.models import Punktacja_Zrodla, Zrodlo

    zrodlo = baker.make(Zrodlo, nazwa="LANCET", issn="0140-6736")
    imp = _make_import(admin_user, zapisz_zmiany_do_bazy=True)
    analyze_jcr_file(jcr_xlsx_path, imp, MockProgress(imp))

    pz = Punktacja_Zrodla.objects.get(zrodlo=zrodlo, rok=2025)
    assert pz.impact_factor == Decimal("109.000")
    assert pz.kwartyl_w_wos == 1


@pytest.mark.django_db
def test_bez_zmian_gdy_wartosci_rowne(admin_user, jcr_xlsx_path):
    from bpp.models import Zrodlo

    zrodlo = baker.make(Zrodlo, nazwa="LANCET", issn="0140-6736")
    zrodlo.punktacja_zrodla_set.create(
        rok=2025, impact_factor=Decimal("109.000"), kwartyl_w_wos=1
    )
    imp = _make_import(admin_user, zapisz_zmiany_do_bazy=True)
    analyze_jcr_file(jcr_xlsx_path, imp, MockProgress(imp))

    wiersz = imp.get_details_set().get(zrodlo=zrodlo)
    assert wiersz.wymaga_zmian is False
    assert "bez zmian" in wiersz.rezultat


@pytest.mark.django_db
def test_niedopasowane_zrodlo(admin_user, jcr_xlsx_path):
    # Brak jakichkolwiek Zrodel -> wszystkie wiersze "Brak źródła w BPP"
    imp = _make_import(admin_user, zapisz_zmiany_do_bazy=True)
    analyze_jcr_file(jcr_xlsx_path, imp, MockProgress(imp))
    assert imp.get_details_set().filter(rezultat__icontains="Brak źródła").exists()


@pytest.mark.django_db
def test_toggle_kwartyl_off(admin_user, jcr_xlsx_path):
    from bpp.models import Punktacja_Zrodla, Zrodlo

    zrodlo = baker.make(Zrodlo, nazwa="LANCET", issn="0140-6736")
    imp = _make_import(
        admin_user, zapisz_zmiany_do_bazy=True, importuj_kwartyl_wos=False
    )
    analyze_jcr_file(jcr_xlsx_path, imp, MockProgress(imp))

    pz = Punktacja_Zrodla.objects.get(zrodlo=zrodlo, rok=2025)
    assert pz.impact_factor == Decimal("109.000")
    assert pz.kwartyl_w_wos is None  # nie ruszony


@pytest.mark.django_db
def test_autodetekcja_roku_gdy_brak(admin_user, jcr_xlsx_path):
    imp = _make_import(admin_user, rok=None, zapisz_zmiany_do_bazy=False)
    analyze_jcr_file(jcr_xlsx_path, imp, MockProgress(imp))
    imp.refresh_from_db()
    assert imp.rok == 2025


@pytest.mark.django_db
def test_ignoruj_zrodla_bez_odpowiednika_pomija_niedopasowane(
    admin_user, jcr_xlsx_path
):
    # Brak Zrodel w bazie + flaga True → żadnych wierszy "Brak źródła"
    imp = _make_import(
        admin_user,
        zapisz_zmiany_do_bazy=False,
        ignoruj_zrodla_bez_odpowiednika=True,
    )
    analyze_jcr_file(jcr_xlsx_path, imp, MockProgress(imp))
    assert imp.get_details_set().filter(zrodlo__isnull=True).count() == 0


@pytest.mark.django_db
def test_ignoruj_zrodla_bez_odpowiednika_dopasowane_sa_raportowane(
    admin_user, jcr_xlsx_path
):
    # Pasujące źródło nadal dostaje wiersz raportu, nawet z flagą True
    from bpp.models import Zrodlo

    baker.make(Zrodlo, nazwa="LANCET", issn="0140-6736")
    imp = _make_import(
        admin_user,
        zapisz_zmiany_do_bazy=False,
        ignoruj_zrodla_bez_odpowiednika=True,
    )
    analyze_jcr_file(jcr_xlsx_path, imp, MockProgress(imp))
    assert imp.get_details_set().filter(zrodlo__isnull=False).count() >= 1
