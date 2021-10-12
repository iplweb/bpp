import pytest

from nowe_raporty.views import (
    GenerujRaportDlaAutora,
    GenerujRaportDlaJednostki,
    GenerujRaportDlaUczelni,
    GenerujRaportDlaWydzialu,
)


@pytest.mark.parametrize("par", [True, False])
def test_view_GenerujRaportDlaUczelni_get_base_queryset(uczelnia, rf, par):
    v = GenerujRaportDlaUczelni()

    v.request = rf.get("/", args={"_tzju": str(par)})
    assert list(v.get_base_queryset()) == []


@pytest.mark.parametrize("par", [True, False])
def test_view_GenerujRaportDlaWydzialu_get_base_queryset(wydzial, rf, par):
    v = GenerujRaportDlaWydzialu()
    v.object = wydzial

    v.request = rf.get("/", args={"_tzju": str(par)})
    assert list(v.get_base_queryset()) == []


@pytest.mark.parametrize("par", [True, False])
def test_view_GenerujRaportDlaJednostki_get_base_queryset(jednostka, rf, par):
    v = GenerujRaportDlaJednostki()
    v.object = jednostka

    v.request = rf.get("/", args={"_tzju": str(par)})
    assert list(v.get_base_queryset()) == []


@pytest.mark.parametrize("par", [True, False])
def test_view_GenerujRaportDlaAutora_get_base_queryset(autor, rf, par):
    v = GenerujRaportDlaAutora()
    v.object = autor

    v.request = rf.get("/", args={"_tzju": str(par)})
    assert list(v.get_base_queryset()) == []
