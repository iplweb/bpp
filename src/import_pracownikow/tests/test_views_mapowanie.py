from import_pracownikow.forms import MapowanieForm
from import_pracownikow.mapping import POLE_POMIN


def _dane(naglowki, mapowanie, zapisz=False, nazwa=""):
    d = {f"kol__{h}": mapowanie.get(h, POLE_POMIN) for h in naglowki}
    d["zapisz_profil"] = zapisz
    d["nazwa_profilu"] = nazwa
    return d


def test_mapowanieform_buduje_pola_z_naglowkow():
    f = MapowanieForm(naglowki=["nazwisko", "imię", "jedn_org"])
    assert "kol__nazwisko" in f.fields
    assert "kol__jedn_org" in f.fields
    # auto-propozycja jako initial
    assert f.fields["kol__jedn_org"].initial == "nazwa_jednostki"


def test_mapowanieform_valid_zwraca_mapowanie():
    naglowki = ["nazwisko", "imię", "jedn_org"]
    f = MapowanieForm(
        naglowki=naglowki,
        data=_dane(
            naglowki,
            {"nazwisko": "nazwisko", "imię": "imię", "jedn_org": "nazwa_jednostki"},
        ),
    )
    assert f.is_valid(), f.errors
    assert f.mapowanie() == {
        "nazwisko": "nazwisko",
        "imię": "imię",
        "jedn_org": "nazwa_jednostki",
    }


def test_mapowanieform_invalid_bez_jednostki():
    naglowki = ["nazwisko", "imię"]
    f = MapowanieForm(
        naglowki=naglowki,
        data=_dane(naglowki, {"nazwisko": "nazwisko", "imię": "imię"}),
    )
    assert not f.is_valid()
