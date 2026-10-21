"""Duplikat autora w inline'ie autorów (Rollbar #5321).

Formset inline'a autorów nadpisywał ``clean()`` bez ``super().clean()``,
przez co Django nie uruchamiało ``BaseModelFormSet.validate_unique()`` —
sprawdzenia unikalności MIĘDZY formularzami tego samego POST-a. Dwa wiersze
z tym samym autorem i typem odpowiedzialności przechodziły walidację (żadnego
jeszcze nie było w bazie), a drugi INSERT kończył się ``IntegrityError``
i pięćsetką.
"""

import pytest
from django.urls import reverse

from bpp.admin.core import KOMUNIKAT_DUPLIKAT_AUTORA

PREFIKS = "autorzy_set"


def _pola_formularza(page, nazwa_formularza):
    form = page.forms[nazwa_formularza]
    return {k: v for k, v in form.submit_fields() if k}


def _dodaj_nowy_wiersz(dane, autor, jednostka, zapisany_jako, kolejnosc):
    """Dokłada do POST-a nowy wiersz inline'a, wzorując się na szablonie
    ``__prefix__`` (ten sam, z którego JS admina klonuje nowe wiersze)."""
    nr = int(dane[f"{PREFIKS}-TOTAL_FORMS"])
    szablon = f"{PREFIKS}-__prefix__-"
    for klucz, wartosc in list(dane.items()):
        if klucz.startswith(szablon):
            dane[klucz.replace(szablon, f"{PREFIKS}-{nr}-")] = wartosc
    dane[f"{PREFIKS}-{nr}-autor"] = str(autor.pk)
    dane[f"{PREFIKS}-{nr}-jednostka"] = str(jednostka.pk)
    dane[f"{PREFIKS}-{nr}-zapisany_jako"] = zapisany_jako
    dane[f"{PREFIKS}-{nr}-kolejnosc"] = str(kolejnosc)
    dane[f"{PREFIKS}-{nr}-oswiadczenie_ken"] = ""
    dane[f"{PREFIKS}-TOTAL_FORMS"] = str(nr + 1)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "nazwa_modelu", ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"]
)
def test_dwa_nowe_wiersze_z_tym_samym_autorem_daja_blad_walidacji(
    request, admin_app, uczelnia, autor_jan_kowalski, jednostka, nazwa_modelu
):
    rekord = request.getfixturevalue(nazwa_modelu)
    url = reverse(f"admin:bpp_{nazwa_modelu}_change", args=(rekord.pk,))
    dane = _pola_formularza(admin_app.get(url), f"{nazwa_modelu}_form")

    for kolejnosc in (0, 1):
        _dodaj_nowy_wiersz(
            dane, autor_jan_kowalski, jednostka, "Kowalski Jan", kolejnosc
        )

    res = admin_app.post(url, dane)

    assert res.status_code == 200
    assert KOMUNIKAT_DUPLIKAT_AUTORA in res.text
    assert rekord.autorzy_set.count() == 0


@pytest.mark.django_db
def test_istniejacy_wiersz_przepiety_na_autora_z_nowego_wiersza(
    admin_app,
    uczelnia,
    wydawnictwo_ciagle,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
):
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=(wydawnictwo_ciagle.pk,))
    dane = _pola_formularza(admin_app.get(url), "wydawnictwo_ciagle_form")

    # Istniejący wiersz (Nowak) przepięty na Kowalskiego...
    dane[f"{PREFIKS}-0-autor"] = str(autor_jan_kowalski.pk)
    dane[f"{PREFIKS}-0-zapisany_jako"] = "Kowalski Jan"
    # ... i jednocześnie nowy wiersz z Kowalskim.
    _dodaj_nowy_wiersz(dane, autor_jan_kowalski, jednostka, "Kowalski Jan", 1)

    res = admin_app.post(url, dane)

    assert res.status_code == 200
    assert KOMUNIKAT_DUPLIKAT_AUTORA in res.text
    autorzy = wydawnictwo_ciagle.autorzy_set.values_list("autor", flat=True)
    assert list(autorzy) == [autor_jan_nowak.pk]


@pytest.mark.django_db
def test_nowy_wiersz_dubluje_autora_z_bazy(
    admin_app, uczelnia, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
):
    # Ta ścieżka (duplikat wiersza już zapisanego w bazie) była łapana i
    # wcześniej, ale ogólnikowym komunikatem Django — teraz ma ten sam,
    # czytelny komunikat.
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=(wydawnictwo_ciagle.pk,))
    dane = _pola_formularza(admin_app.get(url), "wydawnictwo_ciagle_form")
    _dodaj_nowy_wiersz(dane, autor_jan_kowalski, jednostka, "Kowalski Jan", 1)

    res = admin_app.post(url, dane)

    assert res.status_code == 200
    assert KOMUNIKAT_DUPLIKAT_AUTORA in res.text
    assert wydawnictwo_ciagle.autorzy_set.count() == 1
