"""M10 (audyt bezpieczeństwa 2026-07): rekordy o statusie ukrytym na poziomie
``podglad`` nie mogą być odnajdywane w globalnej wyszukiwarce ani otwierane na
stronie szczegółów przez użytkownika BEZ uprawnień redaktorskich.

Dotąd oba miejsca (``GlobalNavigationAutocomplete`` i ``PracaView``) stosowały
ograniczenie tylko wobec anonima — zwykłe zalogowane konto (bez
``moze_wprowadzac_dane``) omijało je, wbrew intencji pola ``podglad``.
"""

import pytest
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.http import urlencode
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Rekord, Wydawnictwo_Ciagle

TOKEN = "neurodetektorpodgladowy"


@pytest.fixture
def rekord_ukryty_podglad(
    uczelnia, przed_korekta, autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_autor
):
    pub = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny=f"Tajny {TOKEN} artykul",
        rok=2031,
        status_korekty=przed_korekta,
    )
    pub.dodaj_autora(autor_jan_kowalski, jednostka, zapisany_jako="Kowalski Jan")
    Rekord.objects.full_refresh()
    # oznacz status jako ukryty na poziomie "podglad" dla tej uczelni
    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    return pub


def _uzytkownik(django_user_model, nazwa, *, wprowadzajacy):
    user = django_user_model.objects.create_user(nazwa, password="haslo123")
    if wprowadzajacy:
        grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
        user.groups.add(grupa)
    return user


@pytest.mark.django_db
def test_global_nav_ukrywa_podglad_przed_anonimem(client, rekord_ukryty_podglad):
    url = reverse("bpp:navigation-autocomplete") + "?" + urlencode({"q": TOKEN})
    assert TOKEN.encode() not in client.get(url).content


@pytest.mark.django_db
def test_global_nav_ukrywa_podglad_przed_zwyklym_zalogowanym(
    client, django_user_model, rekord_ukryty_podglad
):
    client.force_login(_uzytkownik(django_user_model, "zwykly", wprowadzajacy=False))
    url = reverse("bpp:navigation-autocomplete") + "?" + urlencode({"q": TOKEN})
    assert TOKEN.encode() not in client.get(url).content


@pytest.mark.django_db
def test_global_nav_pokazuje_podglad_wprowadzajacemu(
    client, django_user_model, rekord_ukryty_podglad
):
    client.force_login(_uzytkownik(django_user_model, "redaktor", wprowadzajacy=True))
    url = reverse("bpp:navigation-autocomplete") + "?" + urlencode({"q": TOKEN})
    assert TOKEN.encode() in client.get(url).content


def _url_rekordu(pub):
    return reverse(
        "bpp:browse_praca",
        args=(
            ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
            pub.pk,
        ),
    )


@pytest.mark.django_db
def test_strona_rekordu_zabroniona_dla_anonima(client, rekord_ukryty_podglad):
    assert client.get(_url_rekordu(rekord_ukryty_podglad)).status_code == 403


@pytest.mark.django_db
def test_strona_rekordu_zabroniona_dla_zwyklego_zalogowanego(
    client, django_user_model, rekord_ukryty_podglad
):
    client.force_login(_uzytkownik(django_user_model, "zwykly", wprowadzajacy=False))
    assert client.get(_url_rekordu(rekord_ukryty_podglad)).status_code == 403


@pytest.mark.django_db
def test_strona_rekordu_dostepna_dla_wprowadzajacego(
    client, django_user_model, rekord_ukryty_podglad
):
    client.force_login(_uzytkownik(django_user_model, "redaktor", wprowadzajacy=True))
    # follow=True: rekord ze slugiem redirectuje na browse_praca_by_slug
    res = client.get(_url_rekordu(rekord_ukryty_podglad), follow=True)
    assert res.status_code == 200
