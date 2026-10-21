"""Ustawianie kolejności autorów w inline'ie autorów (przeciąganie wierszy).

Pole ``kolejnosc`` jest ukryte; przy „Zapisz" JS grappelli przenumerowuje
wiersze 0, 1, 2… według ich pozycji na ekranie. Unikalność pozycji pilnuje
w bazie ograniczenie ``UNIQUE (rekord_id, kolejnosc) DEFERRABLE INITIALLY
DEFERRED`` (migracja 0132) — sprawdzane na COMMIT, dzięki czemu zamiana dwóch
wierszy miejscami przechodzi. Testy wymuszają to sprawdzenie przez
``SET CONSTRAINTS ALL IMMEDIATE``, bo transakcja testu nigdy się nie commituje.
"""

import pytest
from django.db import connection
from django.urls import reverse
from model_bakery import baker

from bpp.admin.core import KOMUNIKAT_POWTORZONA_KOLEJNOSC
from bpp.models import Autor

PREFIKS = "autorzy_set"
MODELE = ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"]


def _pola_formularza(app, url, nazwa_modelu):
    form = app.get(url).forms[f"{nazwa_modelu}_form"]
    return {k: v for k, v in form.submit_fields() if k}


def _sprawdz_odroczone_ograniczenia():
    """Odpala sprawdzenie odroczonych ograniczeń tak, jak zrobiłby to COMMIT."""
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def _kolejnosc(rekord):
    return list(
        rekord.autorzy_set.order_by("kolejnosc").values_list(
            "autor__nazwisko", "typ_odpowiedzialnosci__skrot", "kolejnosc"
        )
    )


@pytest.mark.django_db
@pytest.mark.parametrize("nazwa_modelu", MODELE)
def test_zamiana_miejscami_tego_samego_autora_z_dwoma_typami(
    request,
    admin_app,
    uczelnia,
    autor_jan_kowalski,
    jednostka,
    typy_odpowiedzialnosci,
    nazwa_modelu,
):
    # Ta sama osoba jako autor i redaktor; przeciągnięcie redaktora na górę.
    # Wcześniej ``unique_together (rekord, autor, kolejnosc)`` odrzucało to
    # błędem „Istnieje już instancja modelu…", bo każdy wiersz był sprawdzany
    # osobno względem bazy, w której drugi wiersz ma jeszcze starą pozycję.
    rekord = request.getfixturevalue(nazwa_modelu)
    rekord.dodaj_autora(autor_jan_kowalski, jednostka, kolejnosc=0)
    rekord.dodaj_autora(
        autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="red.", kolejnosc=1
    )
    url = reverse(f"admin:bpp_{nazwa_modelu}_change", args=(rekord.pk,))
    dane = _pola_formularza(admin_app, url, nazwa_modelu)
    dane[f"{PREFIKS}-0-kolejnosc"] = "1"
    dane[f"{PREFIKS}-1-kolejnosc"] = "0"

    res = admin_app.post(url, dane)

    assert res.status_code == 302
    _sprawdz_odroczone_ograniczenia()
    assert _kolejnosc(rekord) == [
        ("Kowalski", "red.", 0),
        ("Kowalski", "aut.", 1),
    ]


@pytest.mark.django_db
def test_zamiana_miejscami_roznych_autorow_z_usunieciem(
    admin_app,
    uczelnia,
    wydawnictwo_ciagle,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    typy_odpowiedzialnosci,
):
    trzeci = baker.make(Autor, nazwisko="Trzeci", imiona="Adam")
    rekord = wydawnictwo_ciagle
    rekord.dodaj_autora(autor_jan_kowalski, jednostka, kolejnosc=0)
    rekord.dodaj_autora(autor_jan_nowak, jednostka, kolejnosc=1)
    rekord.dodaj_autora(trzeci, jednostka, kolejnosc=2)
    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=(rekord.pk,))
    dane = _pola_formularza(admin_app, url, "wydawnictwo_ciagle")
    # Ekran po przeciągnięciu: Trzeci, Nowak (do usunięcia), Kowalski —
    # grappelli numeruje także wiersze oznaczone do usunięcia.
    dane[f"{PREFIKS}-2-kolejnosc"] = "0"
    dane[f"{PREFIKS}-1-kolejnosc"] = "1"
    dane[f"{PREFIKS}-1-DELETE"] = "on"
    dane[f"{PREFIKS}-0-kolejnosc"] = "2"

    res = admin_app.post(url, dane)

    assert res.status_code == 302
    _sprawdz_odroczone_ograniczenia()
    assert _kolejnosc(rekord) == [("Trzeci", "aut.", 0), ("Kowalski", "aut.", 2)]


@pytest.mark.django_db
@pytest.mark.parametrize("nazwa_modelu", MODELE)
def test_powtorzona_kolejnosc_daje_blad_walidacji(
    request,
    admin_app,
    uczelnia,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    typy_odpowiedzialnosci,
    nazwa_modelu,
):
    # Np. JS grappelli nie przenumerował wierszy. Wcześniej Django nie znało
    # ograniczenia (rekord, kolejnosc), więc kończyło się to IntegrityError
    # na COMMIT, czyli pięćsetką.
    rekord = request.getfixturevalue(nazwa_modelu)
    rekord.dodaj_autora(autor_jan_kowalski, jednostka, kolejnosc=0)
    rekord.dodaj_autora(autor_jan_nowak, jednostka, kolejnosc=1)
    url = reverse(f"admin:bpp_{nazwa_modelu}_change", args=(rekord.pk,))
    dane = _pola_formularza(admin_app, url, nazwa_modelu)
    dane[f"{PREFIKS}-1-kolejnosc"] = "0"

    res = admin_app.post(url, dane)

    assert res.status_code == 200
    assert KOMUNIKAT_POWTORZONA_KOLEJNOSC in res.text
    _sprawdz_odroczone_ograniczenia()
    assert _kolejnosc(rekord) == [
        ("Kowalski", "aut.", 0),
        ("Nowak", "aut.", 1),
    ]


@pytest.mark.django_db
def test_kolejnosc_zajeta_przez_autora_spoza_formularza(
    admin_app, uczelnia, wydawnictwo_ciagle, jednostka, typy_odpowiedzialnosci
):
    # Formularz pokazuje tylko pierwszych 25 autorów; reszta jest
    # w bazie, ale nie w POST-cie. Pozycja zajęta przez takiego autora też
    # musi dać błąd walidacji, a nie pięćsetkę na COMMIT.
    rekord = wydawnictwo_ciagle
    for nr in range(26):
        autor = baker.make(Autor, nazwisko=f"Autor{nr:02}", imiona="Jan")
        rekord.dodaj_autora(autor, jednostka, kolejnosc=nr)
    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=(rekord.pk,))
    dane = _pola_formularza(admin_app, url, "wydawnictwo_ciagle")
    assert dane[f"{PREFIKS}-TOTAL_FORMS"] == "25"
    dane[f"{PREFIKS}-0-kolejnosc"] = "25"

    res = admin_app.post(url, dane)

    assert res.status_code == 200
    assert KOMUNIKAT_POWTORZONA_KOLEJNOSC in res.text
    _sprawdz_odroczone_ograniczenia()
    assert rekord.autorzy_set.get(autor__nazwisko="Autor00").kolejnosc == 0
