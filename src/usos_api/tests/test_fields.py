from usos_api.fields import buduj_selektor


def test_buduj_selektor_laczy_proste_pola_pionowa_kreska():
    assert buduj_selektor("id", "first_name", "last_name") == "id|first_name|last_name"


def test_buduj_selektor_zapisuje_podpola_w_nawiasach_kwadratowych():
    assert buduj_selektor("id", {"stats": ["staff_count"]}) == "id|stats[staff_count]"


def test_buduj_selektor_laczy_wiele_podpol_jednego_pola():
    assert buduj_selektor({"path": ["id", "name"]}) == "path[id|name]"


def test_buduj_selektor_obsluguje_zagniezdzenie_dwupoziomowe():
    assert (
        buduj_selektor({"user": ["id", {"titles": ["before", "after"]}]})
        == "user[id|titles[before|after]]"
    )
