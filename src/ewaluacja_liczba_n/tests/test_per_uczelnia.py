from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.models import Autor, Jednostka, Uczelnia
from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
from ewaluacja_liczba_n.models import (
    IloscUdzialowDlaAutoraZaCalosc,
    IloscUdzialowDlaAutoraZaRok,
)


def _make_autor_dyscyplina(autor, rok, dyscyplina, rodzaj_autora=None):
    """
    Tworzy Autor_Dyscyplina z niezerowym udziałem (wymiar_etatu=1.0,
    procent_dyscypliny=100) i rodzajem autora jest_w_n=True, licz_sloty=True.
    Jeśli rodzaj_autora nie jest przekazany, tworzy go (lub pobiera istniejący).
    """
    from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina
    from ewaluacja_common.models import Rodzaj_Autora

    if rodzaj_autora is None:
        rodzaj_autora, _ = Rodzaj_Autora.objects.get_or_create(
            skrot="N",
            defaults=dict(
                nazwa="pracownik naukowy w liczbie N",
                jest_w_n=True,
                licz_sloty=True,
                sort=1,
            ),
        )
    return Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=rok,
        dyscyplina_naukowa=dyscyplina,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=Decimal("100.0"),
        rodzaj_autora=rodzaj_autora,
    )


@pytest.mark.django_db
def test_zarok_ma_uczelnia(autor_jan_kowalski, dyscyplina1):
    u = baker.make("bpp.Uczelnia")
    obj = IloscUdzialowDlaAutoraZaRok.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        rok=2022,
        ilosc_udzialow=Decimal("1.0"),
        ilosc_udzialow_monografie=Decimal("0.5"),
        uczelnia=u,
    )
    assert obj.uczelnia_id == u.pk


@pytest.mark.django_db
def test_zacalosc_ma_uczelnia(autor_jan_kowalski, dyscyplina1):
    u = baker.make("bpp.Uczelnia")
    obj = IloscUdzialowDlaAutoraZaCalosc.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        ilosc_udzialow=Decimal("1.0"),
        ilosc_udzialow_monografie=Decimal("0.5"),
        uczelnia=u,
    )
    assert obj.uczelnia_id == u.pk


@pytest.mark.django_db
def test_pipeline_izolacja_dwie_uczelnie(db):
    from bpp.models import Autor, Jednostka, Uczelnia
    from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
    from ewaluacja_liczba_n.models import (
        IloscUdzialowDlaAutoraZaRok,
        LiczbaNDlaUczelni,
    )
    from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025

    u1 = baker.make(Uczelnia, skrot="U1", nazwa="U1")
    u2 = baker.make(Uczelnia, skrot="U2", nazwa="U2")
    j1 = baker.make(Jednostka, uczelnia=u1, skupia_pracownikow=True)
    j2 = baker.make(Jednostka, uczelnia=u2, skupia_pracownikow=True)
    dyscyplina = baker.make(Dyscyplina_Naukowa)
    a1 = baker.make(Autor, aktualna_jednostka=j1)
    a2 = baker.make(Autor, aktualna_jednostka=j2)
    for autor in (a1, a2):
        for rok in (2022, 2023, 2024, 2025):
            _make_autor_dyscyplina(autor, rok, dyscyplina)

    oblicz_liczby_n_dla_ewaluacji_2022_2025(u1)
    oblicz_liczby_n_dla_ewaluacji_2022_2025(u2)  # second run must NOT wipe u1

    assert IloscUdzialowDlaAutoraZaRok.objects.filter(uczelnia=u1, autor=a1).exists()
    assert IloscUdzialowDlaAutoraZaRok.objects.filter(uczelnia=u2, autor=a2).exists()
    assert not IloscUdzialowDlaAutoraZaRok.objects.filter(
        uczelnia=u1, autor=a2
    ).exists()
    assert not IloscUdzialowDlaAutoraZaRok.objects.filter(
        uczelnia=u2, autor=a1
    ).exists()
    assert LiczbaNDlaUczelni.objects.filter(uczelnia=u1).exists()
    assert LiczbaNDlaUczelni.objects.filter(uczelnia=u2).exists()


@pytest.mark.django_db
def test_pipeline_pomija_nieprzypisanych(db):
    from bpp.models import Autor, Jednostka, Uczelnia
    from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok
    from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025

    u1 = baker.make(Uczelnia, skrot="U1", nazwa="U1")
    obca = baker.make(Jednostka, uczelnia=u1, skupia_pracownikow=False)
    dyscyplina = baker.make(Dyscyplina_Naukowa)
    a_null = baker.make(Autor, aktualna_jednostka=None)
    a_obca = baker.make(Autor, aktualna_jednostka=obca)
    for autor in (a_null, a_obca):
        _make_autor_dyscyplina(autor, 2022, dyscyplina)

    oblicz_liczby_n_dla_ewaluacji_2022_2025(u1)

    assert not IloscUdzialowDlaAutoraZaRok.objects.filter(autor=a_null).exists()
    assert not IloscUdzialowDlaAutoraZaRok.objects.filter(autor=a_obca).exists()


@pytest.mark.django_db
def test_autorzy_list_view_filtruje_po_uczelni(rf, db):
    """AutorzyLiczbaNListView.get_queryset zwraca tylko wiersze uczelni z requestu."""
    from decimal import Decimal

    from model_bakery import baker

    from bpp.models import Autor, Jednostka, Uczelnia
    from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok
    from ewaluacja_liczba_n.views.list import AutorzyLiczbaNListView

    u1 = baker.make(Uczelnia, skrot="V1", nazwa="Uczelnia V1")
    u2 = baker.make(Uczelnia, skrot="V2", nazwa="Uczelnia V2")
    dyscyplina = baker.make(Dyscyplina_Naukowa)
    j1 = baker.make(Jednostka, uczelnia=u1, skupia_pracownikow=True)
    j2 = baker.make(Jednostka, uczelnia=u2, skupia_pracownikow=True)
    a1 = baker.make(Autor, aktualna_jednostka=j1)
    a2 = baker.make(Autor, aktualna_jednostka=j2)

    IloscUdzialowDlaAutoraZaRok.objects.create(
        autor=a1,
        dyscyplina_naukowa=dyscyplina,
        rok=2022,
        ilosc_udzialow=Decimal("1.0"),
        ilosc_udzialow_monografie=Decimal("0.5"),
        uczelnia=u1,
    )
    IloscUdzialowDlaAutoraZaRok.objects.create(
        autor=a2,
        dyscyplina_naukowa=dyscyplina,
        rok=2022,
        ilosc_udzialow=Decimal("2.0"),
        ilosc_udzialow_monografie=Decimal("1.0"),
        uczelnia=u2,
    )

    user = baker.make("bpp.BppUser")
    request = rf.get("/")
    request.user = user
    request._uczelnia = u1

    view = AutorzyLiczbaNListView()
    view.request = request
    view.kwargs = {}

    qs = view.get_queryset()

    autor_ids = list(qs.values_list("autor_id", flat=True))
    assert a1.pk in autor_ids, "U1 row missing from queryset"
    assert a2.pk not in autor_ids, "U2 row must be excluded"


# ---------------------------------------------------------------------------
# Verify view scoping tests (R2 rule)
# ---------------------------------------------------------------------------


def _setup_two_universities_with_bad_ad(dyscyplina):
    """
    Build two universities (U1, U2), each with one author having an
    Autor_Dyscyplina record that has wymiar_etatu=None (data-quality issue).
    Returns (u1, u2, a1, a2, ad1, ad2).
    """
    from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina
    from ewaluacja_common.models import Rodzaj_Autora

    rodzaj_n, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults=dict(
            nazwa="pracownik naukowy w liczbie N",
            jest_w_n=True,
            licz_sloty=True,
            sort=1,
        ),
    )

    u1 = baker.make(Uczelnia, skrot="W1", nazwa="Uczelnia W1")
    u2 = baker.make(Uczelnia, skrot="W2", nazwa="Uczelnia W2")
    j1 = baker.make(Jednostka, uczelnia=u1, skupia_pracownikow=True)
    j2 = baker.make(Jednostka, uczelnia=u2, skupia_pracownikow=True)
    a1 = baker.make(Autor, aktualna_jednostka=j1)
    a2 = baker.make(Autor, aktualna_jednostka=j2)

    ad1 = Autor_Dyscyplina.objects.create(
        autor=a1,
        rok=2023,
        dyscyplina_naukowa=dyscyplina,
        wymiar_etatu=None,
        procent_dyscypliny=Decimal("100.0"),
        rodzaj_autora=rodzaj_n,
    )
    ad2 = Autor_Dyscyplina.objects.create(
        autor=a2,
        rok=2023,
        dyscyplina_naukowa=dyscyplina,
        wymiar_etatu=None,
        procent_dyscypliny=Decimal("100.0"),
        rodzaj_autora=rodzaj_n,
    )
    return u1, u2, a1, a2, ad1, ad2


@pytest.mark.django_db
def test_weryfikuj_baze_view_bez_wymiaru_etatu_per_uczelnia(rf, db):
    """
    WeryfikujBazeView.get_context_data with request._uczelnia=U1 must report
    bez_wymiaru_etatu == 1 (only U1's bad record), not 2.
    """
    from ewaluacja_liczba_n.views.verify import WeryfikujBazeView

    dyscyplina = baker.make(Dyscyplina_Naukowa)
    u1, u2, _a1, _a2, _ad1, _ad2 = _setup_two_universities_with_bad_ad(
        dyscyplina
    )

    user = baker.make("bpp.BppUser")
    request = rf.get("/")
    request.user = user
    request._uczelnia = u1

    view = WeryfikujBazeView()
    view.request = request
    view.kwargs = {}

    context = view.get_context_data()

    assert context["bez_wymiaru_etatu"] == 1, (
        f"Expected 1 (only U1 record), got {context['bez_wymiaru_etatu']}. "
        "WeryfikujBazeView must scope queries to the requesting university."
    )


@pytest.mark.django_db
def test_ustaw_wymiar_etatu_view_post_per_uczelnia(rf, db):
    """
    UstawWymiarEtatuView.post with request._uczelnia=U1 must update only U1's
    Autor_Dyscyplina records; U2's record must stay None.
    """
    from unittest.mock import patch

    from ewaluacja_liczba_n.views.verify import UstawWymiarEtatuView

    dyscyplina = baker.make(Dyscyplina_Naukowa)
    u1, u2, _a1, _a2, ad1, ad2 = _setup_two_universities_with_bad_ad(
        dyscyplina
    )

    user = baker.make("bpp.BppUser")
    request = rf.post("/")
    request.user = user
    request._uczelnia = u1

    view = UstawWymiarEtatuView()
    view.request = request
    view.kwargs = {}

    # Patch messages.success so that rf (no middleware) doesn't raise;
    # we only care about DB mutation here.
    with patch("ewaluacja_liczba_n.views.verify.messages"):
        view.post(request)

    ad1.refresh_from_db()
    ad2.refresh_from_db()

    assert ad1.wymiar_etatu == Decimal("1.0"), (
        "U1 record was not updated by UstawWymiarEtatuView.post"
    )
    assert ad2.wymiar_etatu is None, (
        "U2 record must NOT be updated when request._uczelnia=U1"
    )
