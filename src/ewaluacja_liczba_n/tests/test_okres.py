"""Liczba N per okres ewaluacji: współistnienie okresów, filtrowanie widoków
po okresie wybranym w sesji, limit udziałów zależny od długości okresu."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from model_bakery import baker

from bpp.models import Autor, Jednostka, Uczelnia
from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
from ewaluacja_common.okres import KLUCZ_SESJI
from ewaluacja_liczba_n.models import (
    IloscUdzialowDlaAutoraZaCalosc,
    IloscUdzialowDlaAutoraZaRok,
    LiczbaNDlaUczelni,
)
from ewaluacja_liczba_n.tests.test_per_uczelnia import _make_autor_dyscyplina
from ewaluacja_liczba_n.utils import (
    oblicz_dyscypliny_nieraportowane,
    oblicz_liczbe_n_na_koniec_okresu,
    oblicz_liczby_n_dla_ewaluacji_2022_2025,
    oblicz_liczby_n_dla_okresu,
)


@pytest.fixture
def uczelnia_z_autorem(db):
    uczelnia = baker.make(Uczelnia, skrot="OK", nazwa="Uczelnia okresów")
    jednostka = baker.make(Jednostka, uczelnia=uczelnia, skupia_pracownikow=True)
    autor = baker.make(Autor, aktualna_jednostka=jednostka)
    dyscyplina = baker.make(Dyscyplina_Naukowa)
    for rok in (2022, 2023, 2024, 2025, 2026, 2027):
        _make_autor_dyscyplina(autor, rok, dyscyplina)
    return uczelnia, autor, dyscyplina


def _request(rf, uczelnia, okres):
    request = rf.get("/")
    request.user = baker.make("bpp.BppUser")
    request._uczelnia = uczelnia
    request.session = {KLUCZ_SESJI: okres.pk}
    return request


@pytest.mark.django_db
def test_dwa_okresy_wspolistnieja_sankcje_przetrwaja(
    uczelnia_z_autorem, okres_2022_2025, okres_2026_2030
):
    uczelnia, _autor, dyscyplina = uczelnia_z_autorem

    oblicz_liczby_n_dla_okresu(uczelnia, okres=okres_2022_2025)
    LiczbaNDlaUczelni.objects.filter(uczelnia=uczelnia, okres=okres_2022_2025).update(
        sankcje=Decimal("1.50")
    )

    oblicz_liczby_n_dla_okresu(uczelnia, okres=okres_2026_2030)

    stary = LiczbaNDlaUczelni.objects.get(
        uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina, okres=okres_2022_2025
    )
    nowy = LiczbaNDlaUczelni.objects.get(
        uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina, okres=okres_2026_2030
    )
    assert stary.sankcje == Decimal("1.50")
    # 4 lata po 1 udziale / 4 lata
    assert stary.liczba_n == Decimal("1.00")
    # 2 lata po 1 udziale / 5 lat okresu
    assert nowy.liczba_n == Decimal("0.40")
    assert nowy.sankcje == Decimal("0")

    # Udziały za cały okres — osobne wiersze dla każdego okresu
    assert IloscUdzialowDlaAutoraZaCalosc.objects.filter(uczelnia=uczelnia).count() == 2

    # Ponowne przeliczenie 2022–2025 zachowuje sankcje tego okresu
    oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)
    # (wiersze są kasowane i tworzone od nowa, więc pobieramy ponownie)
    stary = LiczbaNDlaUczelni.objects.get(
        uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina, okres=okres_2022_2025
    )
    assert stary.sankcje == Decimal("1.50")
    assert LiczbaNDlaUczelni.objects.filter(okres=okres_2026_2030).exists()


@pytest.mark.django_db
def test_lata_jako_argumenty_wybieraja_okres(uczelnia_z_autorem, okres_2026_2030):
    uczelnia, _autor, _dyscyplina = uczelnia_z_autorem

    oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia, rok_min=2026, rok_max=2030)

    assert LiczbaNDlaUczelni.objects.filter(okres=okres_2026_2030).count() == 1
    assert not LiczbaNDlaUczelni.objects.exclude(okres=okres_2026_2030).exists()
    assert not IloscUdzialowDlaAutoraZaRok.objects.filter(rok__lt=2026).exists()


@pytest.mark.django_db
def test_nieraportowane_i_koniec_okresu_wg_ostatniego_roku(
    uczelnia_z_autorem, okres_2022_2025, okres_2026_2030
):
    uczelnia, _autor, dyscyplina = uczelnia_z_autorem
    oblicz_liczby_n_dla_okresu(uczelnia, okres=okres_2022_2025)

    assert oblicz_liczbe_n_na_koniec_okresu(uczelnia, okres=okres_2022_2025) == {
        dyscyplina.pk: Decimal("1.00")
    }
    # 2030 bez danych — nic do policzenia
    assert oblicz_liczbe_n_na_koniec_okresu(uczelnia, okres=okres_2026_2030) == {}
    assert oblicz_dyscypliny_nieraportowane(uczelnia, okres=okres_2022_2025) == {
        dyscyplina.pk
    }
    assert oblicz_dyscypliny_nieraportowane(uczelnia, okres=okres_2026_2030) == set()


@pytest.mark.django_db
def test_maksimum_udzialow_skaluje_sie_z_dlugoscia_okresu(
    autor_jan_kowalski, dyscyplina1, okres_2022_2025, okres_2026_2030
):
    maks = IloscUdzialowDlaAutoraZaCalosc.maksymalna_ilosc_udzialow
    assert maks(okres_2022_2025) == Decimal("16")
    assert maks(okres_2026_2030) == Decimal("20")

    def rekord(okres, ilosc):
        return IloscUdzialowDlaAutoraZaCalosc(
            autor=autor_jan_kowalski,
            dyscyplina_naukowa=dyscyplina1,
            ilosc_udzialow=Decimal(ilosc),
            ilosc_udzialow_monografie=Decimal("0"),
            okres=okres,
        )

    with pytest.raises(ValidationError):
        rekord(okres_2022_2025, "18").clean()
    rekord(okres_2026_2030, "18").clean()
    with pytest.raises(ValidationError):
        rekord(okres_2026_2030, "20.5").clean()


@pytest.mark.django_db
def test_widoki_filtruja_po_okresie_z_sesji(
    rf, uczelnia_z_autorem, okres_2022_2025, okres_2026_2030
):
    from ewaluacja_liczba_n.views.index import LiczbaNIndexView
    from ewaluacja_liczba_n.views.list import (
        AutorzyLiczbaNListView,
        UdzialyZaCaloscListView,
    )

    uczelnia, _autor, _dyscyplina = uczelnia_z_autorem
    oblicz_liczby_n_dla_okresu(uczelnia, okres=okres_2022_2025)
    oblicz_liczby_n_dla_okresu(uczelnia, okres=okres_2026_2030)

    for okres in (okres_2022_2025, okres_2026_2030):
        request = _request(rf, uczelnia, okres)

        view = UdzialyZaCaloscListView()
        view.setup(request)
        assert {u.okres_id for u in view.get_queryset()} == {okres.pk}

        view = AutorzyLiczbaNListView()
        view.setup(request)
        lata = set(view.get_queryset().values_list("rok", flat=True))
        assert lata and all(okres.zawiera(rok) for rok in lata)

        view = LiczbaNIndexView()
        view.setup(request)
        context = view.get_context_data()
        liczby = context["liczby_n"] + context["dyscypliny_nieraportowane"]
        assert {liczba.okres_id for liczba in liczby} == {okres.pk}
        assert context["okres"] == okres


@pytest.mark.django_db
def test_eksport_udzialow_za_calosc_wg_okresu(
    rf, uczelnia_z_autorem, okres_2022_2025, okres_2026_2030
):
    from ewaluacja_liczba_n.views.export import UdzialyZaCaloscExporter

    uczelnia, _autor, _dyscyplina = uczelnia_z_autorem
    oblicz_liczby_n_dla_okresu(uczelnia, okres=okres_2022_2025)
    oblicz_liczby_n_dla_okresu(uczelnia, okres=okres_2026_2030)

    exporter = UdzialyZaCaloscExporter()
    response = exporter.export(_request(rf, uczelnia, okres_2026_2030))

    assert "2026_2030" in response["Content-Disposition"]
    qs = exporter._get_filtered_udzialy_calosc_queryset(
        _request(rf, uczelnia, okres_2026_2030)
    )
    assert {u.okres_id for u in qs} == {okres_2026_2030.pk}


@pytest.mark.django_db
def test_przelicz_n_z_argumentem_okres(uczelnia_z_autorem, okres_2026_2030):
    uczelnia, _autor, _dyscyplina = uczelnia_z_autorem

    call_command("przelicz_n", uczelnia_id=uczelnia.pk, okres=2026)

    assert set(LiczbaNDlaUczelni.objects.values_list("okres_id", flat=True)) == {
        okres_2026_2030.pk
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "nazwa",
    [
        "index",
        "autorzy-list",
        "udzialy-za-calosc-list",
        "weryfikuj-baze",
        "autorzy-export",
        "udzialy-za-calosc-export",
    ],
)
def test_strony_renderuja_wybrany_okres(admin_client, uczelnia, okres_2026_2030, nazwa):
    from django.urls import reverse

    sesja = admin_client.session
    sesja[KLUCZ_SESJI] = okres_2026_2030.pk
    sesja.save()

    res = admin_client.get(reverse(f"ewaluacja_liczba_n:{nazwa}"))

    assert res.status_code == 200
    if nazwa.endswith("export"):
        assert "2026_2030" in res["Content-Disposition"]
    else:
        assert "2026–2030" in res.content.decode()
