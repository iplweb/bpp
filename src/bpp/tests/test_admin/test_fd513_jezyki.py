"""FD#513: słownik języków — podgląd przed ukryciem, „Ukryj wszystkie
nieużywane”, liczba publikacji, kody dla CrossRef, edycja rekordu z ukrytym
językiem."""

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.urls import reverse
from model_bakery import baker

from bpp.kody_jezykow import kod_dla_nazwy
from bpp.models import (
    Jezyk,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Streszczenie,
    Wydawnictwo_Zwarte,
    Zrodlo,
)
from crossref_bpp.core import Komparator

URL = "admin:bpp_jezyk_changelist"


def _jezyk(skrot, **kw):
    kw.setdefault("widoczny", True)
    return baker.make(Jezyk, nazwa=f"język {skrot}", skrot=skrot, **kw)


def _stan(*jezyki):
    for jezyk in jezyki:
        jezyk.refresh_from_db()
    return tuple(jezyk.widoczny for jezyk in jezyki)


def _zatwierdz(client, podglad, **kw):
    """Wyślij formularz ze strony podglądu (akcja + lista PK z podglądu)."""
    ctx = podglad.context
    return client.post(
        reverse(URL),
        {
            "action": ctx["akcja"],
            "potwierdzam": "1",
            "pk_z_podgladu": [obj.pk for obj in ctx["do_ukrycia"]],
            "_selected_action": ctx["wybrane_pk"],
        },
        **kw,
    )


# --- podgląd i zatwierdzenie -------------------------------------------------


@pytest.mark.django_db
def test_ukryj_nieuzywane_najpierw_pokazuje_podglad(admin_client):
    uzywany = _jezyk("t-uz")
    wolny = _jezyk("t-wo")
    baker.make(Wydawnictwo_Ciagle, jezyk=uzywany)

    res = admin_client.post(
        reverse(URL),
        {"action": "ukryj_nieuzywane", "_selected_action": [uzywany.pk, wolny.pk]},
    )

    assert res.status_code == 200
    assert res.context["do_ukrycia"] == [wolny]
    assert res.context["pominiete"] == [uzywany]
    # Sam podgląd niczego nie zmienia.
    assert _stan(uzywany, wolny) == (True, True)


@pytest.mark.django_db
def test_ukryj_wszystkie_nieuzywane_bez_zaznaczania(admin_client):
    uzywany = _jezyk("t-uz")
    uzywany_alt = _jezyk("t-alt")
    wolny = _jezyk("t-wo")
    juz_ukryty = _jezyk("t-uk", widoczny=False)
    baker.make(Wydawnictwo_Ciagle, jezyk=uzywany)
    baker.make(Wydawnictwo_Zwarte, jezyk_alt=uzywany_alt)

    # Krok 1: akcja bez zaznaczonych wierszy → podgląd, bez zmian.
    res = admin_client.post(reverse(URL), {"action": "ukryj_wszystkie_nieuzywane"})
    assert res.status_code == 200
    do_ukrycia = res.context["do_ukrycia"]
    assert wolny in do_ukrycia
    assert uzywany not in do_ukrycia and uzywany_alt not in do_ukrycia
    assert juz_ukryty not in do_ukrycia
    assert _stan(uzywany, uzywany_alt, wolny) == (True, True, True)

    # Krok 2: zatwierdzenie.
    res = _zatwierdz(admin_client, res, follow=True)
    assert res.status_code == 200
    assert _stan(uzywany, uzywany_alt, wolny) == (True, True, False)
    # Żaden widoczny język nie jest już nieużywany.
    komunikaty = " ".join(str(m) for m in res.context["messages"])
    assert "Ukryto" in komunikaty and "Pokaż zaznaczone" in komunikaty

    # Krok 3: operacja jest odwracalna.
    admin_client.post(
        reverse(URL), {"action": "pokaz_zaznaczone", "_selected_action": [wolny.pk]}
    )
    assert _stan(wolny) == (True,)


@pytest.mark.django_db
def test_jezyk_uzyty_po_podgladzie_nie_zostanie_ukryty(admin_client):
    """Używane liczymy w chwili zatwierdzenia — język, który trafił do
    rekordu między podglądem a zatwierdzeniem, zostaje widoczny."""
    jezyk = _jezyk("t-wo")
    res = admin_client.post(reverse(URL), {"action": "ukryj_wszystkie_nieuzywane"})
    assert jezyk in res.context["do_ukrycia"]

    baker.make(Wydawnictwo_Ciagle, jezyk=jezyk)
    res = _zatwierdz(admin_client, res, follow=True)
    assert _stan(jezyk) == (True,)
    assert "Pominięto 1" in " ".join(str(m) for m in res.context["messages"])


@pytest.mark.django_db
def test_jezyk_dodany_po_podgladzie_nie_zostanie_ukryty(admin_client):
    """Zatwierdzenie dotyczy listy z podglądu, nie „wszystkiego, co dziś
    jest nieużywane”."""
    stary = _jezyk("t-st")
    res = admin_client.post(reverse(URL), {"action": "ukryj_wszystkie_nieuzywane"})
    nowy = _jezyk("t-no")

    _zatwierdz(admin_client, res)
    assert _stan(stary, nowy) == (False, True)


@pytest.mark.django_db
def test_zatwierdzenie_bez_listy_z_podgladu_niczego_nie_ukrywa(admin_client):
    jezyk = _jezyk("t-wo")
    admin_client.post(
        reverse(URL), {"action": "ukryj_wszystkie_nieuzywane", "potwierdzam": "1"}
    )
    assert _stan(jezyk) == (True,)


@pytest.mark.django_db
def test_lista_z_podgladu_nie_pozwala_ukryc_uzywanego(admin_client):
    """Nawet podrobiona lista PK nie ukryje używanego języka."""
    uzywany = _jezyk("t-uz")
    baker.make(Wydawnictwo_Ciagle, jezyk=uzywany)
    admin_client.post(
        reverse(URL),
        {
            "action": "ukryj_wszystkie_nieuzywane",
            "potwierdzam": "1",
            "pk_z_podgladu": [uzywany.pk],
        },
    )
    assert _stan(uzywany) == (True,)


@pytest.mark.django_db
def test_ukryj_wszystkie_nieuzywane_wymaga_uprawnienia(client, django_user_model):
    jezyk = _jezyk("t-wo")
    user = django_user_model.objects.create_user(
        username="bez-uprawnien", password="x", is_staff=True
    )
    client.force_login(user)
    client.post(
        reverse(URL),
        {
            "action": "ukryj_wszystkie_nieuzywane",
            "potwierdzam": "1",
            "pk_z_podgladu": [jezyk.pk],
        },
    )
    assert _stan(jezyk) == (True,)


# --- lista: liczba publikacji, kolumna „Używane”, filtr kodu CrossRef --------


@pytest.mark.django_db
def test_liczba_publikacji_i_sortowanie(admin_client):
    duzo = _jezyk("t-duzo")
    malo = _jezyk("t-malo")
    zero = _jezyk("t-zero")
    baker.make(Wydawnictwo_Ciagle, jezyk=duzo, _quantity=2)
    # Jedna publikacja wskazująca na ten sam język dwoma polami liczy się raz.
    baker.make(Wydawnictwo_Zwarte, jezyk=duzo, jezyk_orig=duzo)
    baker.make(Wydawnictwo_Zwarte, jezyk_alt=malo)
    # Język źródła: używany, ale nie przez publikację.
    baker.make(Zrodlo, jezyk=zero)

    res = admin_client.get(reverse(URL), {"q": "t-"})
    assert res.status_code == 200
    wynik = {j.skrot: j for j in res.context["cl"].result_list}
    assert wynik["t-duzo"]._liczba_publikacji == 3
    assert wynik["t-malo"]._liczba_publikacji == 1
    assert wynik["t-zero"]._liczba_publikacji == 0
    assert wynik["t-zero"]._uzywane is True

    kolumny = admin.site._registry[Jezyk].get_list_display(res.wsgi_request)
    nr = kolumny.index("liczba_publikacji") + 1  # +1: kolumna z checkboxem
    res = admin_client.get(reverse(URL), {"q": "t-", "o": f"-{nr}"})
    assert [j.skrot for j in res.context["cl"].result_list] == [
        "t-duzo",
        "t-malo",
        "t-zero",
    ]


@pytest.mark.django_db
def test_filtr_kod_dla_crossref(admin_client):
    ze_skrotem = _jezyk("t-a", skrot_crossref="xa", kod_bcp47="")
    z_bcp = _jezyk("t-b", skrot_crossref=None, kod_bcp47="xb")
    bez = _jezyk("t-c", skrot_crossref=None, kod_bcp47="")

    res = admin_client.get(reverse(URL), {"q": "t-", "kod_crossref": "nie"})
    assert list(res.context["cl"].result_list) == [bez]
    res = admin_client.get(reverse(URL), {"q": "t-", "kod_crossref": "tak"})
    assert set(res.context["cl"].result_list) == {ze_skrotem, z_bcp}


# --- kody języków a CrossRef --------------------------------------------------


@pytest.mark.django_db
def test_komparator_dopasowuje_jezyk_spoza_dawnej_listy():
    """Dawniej ``porownaj_language`` odrzucał wszystko poza en/es/pl."""
    Jezyk.objects.filter(kod_bcp47__istartswith="xq").delete()
    jezyk = _jezyk("t-xq", kod_bcp47="xq")

    wynik = Komparator.porownaj_language("xq")
    assert wynik.rekord_po_stronie_bpp == jezyk
    # Region jest pomijany.
    assert Komparator.porownaj_language("xq-PL").rekord_po_stronie_bpp == jezyk


@pytest.mark.django_db
def test_komparator_brak_jezyka_daje_czytelny_blad():
    wynik = Komparator.porownaj_language("xz")
    assert wynik.rekord_po_stronie_bpp is None
    assert "Kod języka wg BCP 47" in wynik.opis


@pytest.mark.django_db
def test_dla_kodu_kolejnosc_pol_i_widoczne_przed_ukrytymi():
    ukryty_bcp = _jezyk("t-1", kod_bcp47="xq", widoczny=False)
    widoczny_bcp = _jezyk("t-2", kod_bcp47="xq-AA")
    assert Jezyk.dla_kodu("xq") == widoczny_bcp

    # Jawny „Skrót CrossRef” ma pierwszeństwo przed kodem BCP 47…
    jawny = _jezyk("t-3", skrot_crossref="xq", kod_bcp47="")
    assert Jezyk.dla_kodu("xq") == jawny
    # …ale UKRYTY język ze skrótem nie przesłania widocznego z kodem BCP 47.
    Jezyk.objects.filter(pk=jawny.pk).update(widoczny=False)
    assert Jezyk.dla_kodu("xq") == widoczny_bcp
    # Gdy widocznego nie ma — zwracany jest ukryty (wołający to obsługuje).
    Jezyk.objects.filter(pk=widoczny_bcp.pk).delete()
    assert Jezyk.dla_kodu("xq") == jawny
    assert Jezyk.dla_kodu("") is None and Jezyk.dla_kodu(None) is None
    assert ukryty_bcp != jawny


@pytest.mark.django_db
def test_skrot_crossref_przyjmuje_dowolny_poprawny_kod():
    jezyk = baker.prepare(Jezyk, nazwa="t-niem", skrot="t-n", skrot_crossref="de")
    jezyk.clean_fields()  # dawniej: „de” spoza listy wyboru → błąd

    jezyk.skrot_crossref = "Niemiecki!"
    with pytest.raises(ValidationError):
        jezyk.clean_fields()


@pytest.mark.parametrize(
    "nazwa,kod",
    [
        ("ukraiński", "uk"),
        (" Czeski ", "cs"),
        ("język angielski", "en"),
        ("brak danych", None),
        ("", None),
    ],
)
def test_kod_dla_nazwy(nazwa, kod):
    assert kod_dla_nazwy(nazwa) == kod


# --- polecenie ukryj_nieuzywane_jezyki ---------------------------------------


@pytest.mark.django_db
def test_polecenie_ukrywa_tylko_nieuzywane():
    from django.core.management import call_command

    uzywany = _jezyk("t-uz")
    # Język streszczenia też jest „używany”.
    w_streszczeniu = _jezyk("t-st")
    recznie_ukryty = _jezyk("t-ru", widoczny=False)
    wolny = _jezyk("t-wo")
    rekord = baker.make(Wydawnictwo_Ciagle, jezyk=uzywany, jezyk_alt=recznie_ukryty)
    baker.make(
        Wydawnictwo_Ciagle_Streszczenie,
        rekord=rekord,
        jezyk_streszczenia=w_streszczeniu,
    )

    call_command("ukryj_nieuzywane_jezyki", dry_run=True)
    assert _stan(uzywany, w_streszczeniu, recznie_ukryty, wolny) == (
        True,
        True,
        False,
        True,
    )

    call_command("ukryj_nieuzywane_jezyki")
    # Używany, ale ręcznie ukryty język zostaje ukryty (decyzja redakcji).
    assert _stan(uzywany, w_streszczeniu, recznie_ukryty, wolny) == (
        True,
        True,
        False,
        False,
    )


# --- źródło wskazuje na UKRYTY język -----------------------------------------


@pytest.mark.django_db
def test_komparator_ukryty_jezyk_daje_wyjasnienie_zamiast_pustego_pola():
    Jezyk.objects.filter(kod_bcp47__istartswith="xq").delete()
    ukryty = _jezyk("t-xq", kod_bcp47="xq", widoczny=False)

    wynik = Komparator.porownaj_language("xq")
    # Ukrytego języka nie ma na liście wyboru nowego rekordu, więc nie
    # udajemy dopasowania — mówimy, co zrobić.
    assert wynik.rekord_po_stronie_bpp is None
    assert ukryty.nazwa in wynik.opis and "Pokaż zaznaczone" in wynik.opis


@pytest.mark.django_db
def test_dodaj_z_crossref_ostrzega_o_ukrytym_jezyku(rf, admin_user, mocker):
    from django.contrib.messages import get_messages
    from django.contrib.messages.storage.fallback import FallbackStorage

    Jezyk.objects.filter(kod_bcp47__istartswith="xq").delete()
    ukryty = _jezyk("t-xq", kod_bcp47="xq", widoczny=False)
    model_admin = admin.site._registry[Wydawnictwo_Ciagle]
    mocker.patch.object(
        model_admin, "get_crossref_api_data", return_value={"language": "xq"}
    )
    mocker.patch(
        "bpp.admin.crossref_api_helpers.ostrzez_o_zduplikowanych_zrodlach_crossref"
    )
    mocker.patch(
        "bpp.admin.crossref_api_helpers.convert_crossref_to_changeform_initial_data",
        return_value={},
    )
    request = rf.get("/")
    request.user = admin_user
    request.session = {}
    request._messages = FallbackStorage(request)

    model_admin.get_changeform_initial_data(request)

    komunikaty = [str(m) for m in get_messages(request)]
    assert any(ukryty.nazwa in k and "ukryty" in k for k in komunikaty), komunikaty
