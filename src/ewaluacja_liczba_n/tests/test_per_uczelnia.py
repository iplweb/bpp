from decimal import Decimal

import pytest
from model_bakery import baker

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
