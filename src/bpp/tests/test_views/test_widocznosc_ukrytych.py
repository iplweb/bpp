"""Publiczne widoki nie pokazują rekordów o statusach korekty ukrytych w kanale
``podglad`` ani autorów z ``pokazuj=False`` — spójnie ze stroną rekordu.
Użytkownik z uprawnieniami redaktorskimi widzi wszystko."""

import json

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import CHARAKTER_OGOLNY_KSIAZKA, GR_WPROWADZANIE_DANYCH
from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Charakter_Formalny,
    Rekord,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.models.fields import OpcjaWyswietlaniaField

TOKEN = "kwazarniewidzialny"
ROK = 2031


@pytest.fixture
def rekord_ukryty(
    uczelnia, przed_korekta, autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_autor
):
    pub = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny=f"Tajny {TOKEN} artykul",
        rok=ROK,
        status_korekty=przed_korekta,
    )
    pub.dodaj_autora(autor_jan_kowalski, jednostka, zapisany_jako="Kowalski Jan")
    Rekord.objects.full_refresh()
    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    return pub


def _uzytkownik(django_user_model, nazwa, *, wprowadzajacy):
    user = django_user_model.objects.create_user(nazwa, password="haslo123")
    if wprowadzajacy:
        grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
        user.groups.add(grupa)
    return user


ROLE = ["anonim", "zwykly", "redaktor"]


def _zaloguj(client, django_user_model, rola):
    if rola == "anonim":
        return
    client.force_login(
        _uzytkownik(django_user_model, rola, wprowadzajacy=rola == "redaktor")
    )


# --- bibtex ---------------------------------------------------------------


def _url_bibtex(pub):
    return reverse("bpp:bibtex_view", args=("wydawnictwo_ciagle", pub.pk))


@pytest.mark.django_db
@pytest.mark.parametrize("rola,oczekiwany", [("anonim", 403), ("zwykly", 403)])
def test_bibtex_ukryty_rekord_zabroniony(
    client, django_user_model, rekord_ukryty, rola, oczekiwany
):
    _zaloguj(client, django_user_model, rola)
    res = client.get(_url_bibtex(rekord_ukryty))
    assert res.status_code == oczekiwany
    assert TOKEN.encode() not in res.content


@pytest.mark.django_db
def test_bibtex_ukryty_rekord_dostepny_dla_redaktora(
    client, django_user_model, rekord_ukryty
):
    _zaloguj(client, django_user_model, "redaktor")
    res = client.get(_url_bibtex(rekord_ukryty))
    assert res.status_code == 200
    assert TOKEN in res.json()["bibtex"]


# --- AutorView ------------------------------------------------------------


@pytest.fixture
def autor_ukryty(uczelnia):
    return baker.make(Autor, imiona="Ukryty", nazwisko=f"Autor{TOKEN}", pokazuj=False)


@pytest.mark.django_db
@pytest.mark.parametrize("rola", ROLE)
@pytest.mark.parametrize("po", ["pk", "slug"])
def test_autor_ukryty(client, django_user_model, autor_ukryty, rola, po):
    _zaloguj(client, django_user_model, rola)
    arg = autor_ukryty.pk if po == "pk" else autor_ukryty.slug
    res = client.get(reverse("bpp:browse_autor", args=(arg,)))
    assert res.status_code == (200 if rola == "redaktor" else 404)


# --- RokView / LataView / strona główna ----------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("rola", ROLE)
def test_rok_view(client, django_user_model, rekord_ukryty, rola):
    _zaloguj(client, django_user_model, rola)
    res = client.get(reverse("bpp:browse_rok", args=(ROK,)))
    assert res.status_code == 200
    widac = TOKEN.encode() in res.content
    assert widac == (rola == "redaktor")


@pytest.mark.django_db
def test_rok_view_sasiedni_rok_z_samymi_ukrytymi(client, rekord_ukryty):
    res = client.get(reverse("bpp:browse_rok", args=(ROK - 1,)))
    assert res.context["next_year"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("rola", ROLE)
def test_lata_view(client, django_user_model, rekord_ukryty, rola):
    _zaloguj(client, django_user_model, rola)
    res = client.get(reverse("bpp:browse_lata"))
    lata = [x["year"] for x in res.context["years"]]
    assert (ROK in lata) == (rola == "redaktor")


@pytest.mark.django_db
def test_strona_glowna_bez_ukrytych(uczelnia, rekord_ukryty):
    from bpp.views.browse import get_uczelnia_context_data

    get_uczelnia_context_data.invalidate()
    ctx = get_uczelnia_context_data(uczelnia)
    assert TOKEN not in " ".join(r.tytul_oryginalny for r in ctx["recently_updated"])
    assert ctx["total_rekord_count"] == 0


# --- autocomplete'y --------------------------------------------------------


@pytest.fixture
def ksiazka_ukryta(uczelnia, przed_korekta):
    cf = baker.make(Charakter_Formalny, charakter_ogolny=CHARAKTER_OGOLNY_KSIAZKA)
    ksiazka = baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny=f"Ksiazka {TOKEN}",
        charakter_formalny=cf,
        status_korekty=przed_korekta,
        rok=ROK,
    )
    # rozdział — żeby książka była „wydawnictwem nadrzędnym"
    baker.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=ksiazka)
    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    return ksiazka


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    [
        "bpp:wydawnictwo-nadrzedne-autocomplete",
        "bpp:public-wydawnictwo-nadrzedne-autocomplete",
        "zglos_publikacje:public-wydawnictwo-nadrzedne-autocomplete",
    ],
)
@pytest.mark.parametrize("rola", ROLE)
def test_autocomplete_wydawnictwo_nadrzedne(
    client, django_user_model, ksiazka_ukryta, url, rola
):
    _zaloguj(client, django_user_model, rola)
    res = client.get(reverse(url), {"q": TOKEN})
    assert res.status_code == 200
    assert (TOKEN.encode() in res.content) == (rola == "redaktor")


@pytest.mark.django_db
@pytest.mark.parametrize("rola", ROLE)
def test_autocomplete_podrzedna_habilitacyjna(
    client, django_user_model, rekord_ukryty, autor_jan_kowalski, rola
):
    _zaloguj(client, django_user_model, rola)
    res = client.get(
        reverse("bpp:podrzedna-publikacja-habilitacyjna-autocomplete"),
        {"q": TOKEN, "forward": json.dumps({"autor": str(autor_jan_kowalski.pk)})},
    )
    assert res.status_code == 200
    assert (TOKEN.encode() in res.content) == (rola == "redaktor")


@pytest.fixture
def przypisanie_dyscypliny(autor_jan_kowalski, dyscyplina1):
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=ROK, dyscyplina_naukowa=dyscyplina1
    )
    return json.dumps({"autor": str(autor_jan_kowalski.pk), "rok": str(ROK)})


def _dyscypliny(client, forward):
    return client.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"),
        {"forward": forward},
    )


@pytest.mark.django_db
@pytest.mark.parametrize("rola", ROLE)
def test_dyscyplina_przypisanie_formularz_zglaszania_nigdy(
    client, django_user_model, uczelnia, przypisanie_dyscypliny, dyscyplina1, rola
):
    uczelnia.pokazuj_formularz_zglaszania_publikacji = (
        OpcjaWyswietlaniaField.POKAZUJ_NIGDY
    )
    uczelnia.save()
    _zaloguj(client, django_user_model, rola)
    res = _dyscypliny(client, przypisanie_dyscypliny)
    if rola == "redaktor":
        assert res.status_code == 200
        assert dyscyplina1.nazwa in res.content.decode()
    else:
        assert res.status_code == 403


@pytest.mark.django_db
def test_dyscyplina_przypisanie_formularz_zglaszania_zawsze_anonim(
    client, uczelnia, przypisanie_dyscypliny, dyscyplina1
):
    uczelnia.pokazuj_formularz_zglaszania_publikacji = (
        OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    )
    uczelnia.save()
    res = _dyscypliny(client, przypisanie_dyscypliny)
    assert res.status_code == 200
    assert dyscyplina1.nazwa in res.content.decode()


@pytest.mark.django_db
def test_dyscyplina_przypisanie_ukryty_autor_dla_anonima(
    client, uczelnia, autor_ukryty, dyscyplina1
):
    Autor_Dyscyplina.objects.create(
        autor=autor_ukryty, rok=ROK, dyscyplina_naukowa=dyscyplina1
    )
    res = _dyscypliny(
        client, json.dumps({"autor": str(autor_ukryty.pk), "rok": str(ROK)})
    )
    assert dyscyplina1.nazwa not in res.content.decode()


# --- multiseek: zapisane formularze ----------------------------------------


@pytest.fixture
def wlasciciel(django_user_model):
    return django_user_model.objects.create_user(
        "wlasciciel", password="x", is_staff=True
    )


@pytest.fixture
def prywatny_formularz(wlasciciel):
    from multiseek.models import SearchForm

    return SearchForm.objects.create(
        name="prywatny", public=False, data='{"form_data": [null]}', owner=wlasciciel
    )


@pytest.mark.django_db
def test_load_form_cudzy_prywatny_zabroniony(
    client, django_user_model, prywatny_formularz
):
    inny = django_user_model.objects.create_user("inny", password="x")
    client.force_login(inny)
    res = client.get(reverse("multiseek:load_form", args=(prywatny_formularz.pk,)))
    assert res.status_code == 403


@pytest.mark.django_db
def test_load_form_anonim_prywatny_zabroniony(client, prywatny_formularz):
    res = client.get(reverse("multiseek:load_form", args=(prywatny_formularz.pk,)))
    assert res.status_code == 403


@pytest.mark.django_db
def test_load_form_wlasciciel_i_superuser(
    client, admin_user, wlasciciel, prywatny_formularz
):
    url = reverse("multiseek:load_form", args=(prywatny_formularz.pk,))
    client.force_login(wlasciciel)
    assert client.get(url).status_code == 302
    client.force_login(admin_user)
    assert client.get(url).status_code == 302


@pytest.mark.django_db
def test_load_form_publiczny_dla_innego(client, django_user_model, wlasciciel):
    from multiseek.models import SearchForm

    sf = SearchForm.objects.create(
        name="publiczny", public=True, data='{"form_data": [null]}', owner=wlasciciel
    )
    client.force_login(django_user_model.objects.create_user("inny", password="x"))
    assert client.get(reverse("multiseek:load_form", args=(sf.pk,))).status_code == 302


def _zapisz(client, nazwa, overwrite):
    return client.post(
        reverse("multiseek:save_form"),
        {
            "json": '{"form_data": [null]}',
            "name": nazwa,
            "public": "false",
            "overwrite": "true" if overwrite else "false",
        },
    )


@pytest.mark.django_db
@pytest.mark.parametrize("overwrite", [True, False])
def test_save_form_nie_nadpisuje_cudzego(
    client, django_user_model, prywatny_formularz, wlasciciel, overwrite
):
    inny = django_user_model.objects.create_user("inny", password="x", is_staff=True)
    client.force_login(inny)
    res = _zapisz(client, "prywatny", overwrite)
    assert res.status_code == 200
    assert res.json()["result"] not in ("saved", "overwrite-prompt")
    prywatny_formularz.refresh_from_db()
    assert prywatny_formularz.owner == wlasciciel


@pytest.mark.django_db
def test_save_form_wlasciciel_nadpisuje_swoj(client, prywatny_formularz, wlasciciel):
    client.force_login(wlasciciel)
    assert _zapisz(client, "prywatny", False).json()["result"] == "overwrite-prompt"
    assert _zapisz(client, "prywatny", True).json()["result"] == "saved"


@pytest.mark.django_db
def test_save_form_nowy(client, wlasciciel):
    client.force_login(wlasciciel)
    assert _zapisz(client, "nowy", False).json()["result"] == "saved"
