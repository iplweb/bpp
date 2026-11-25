"""FD#513: słownik języków — podgląd przed ukryciem, „Ukryj wszystkie
nieużywane”, liczba publikacji, kody dla CrossRef, edycja rekordu z ukrytym
językiem."""

from importlib import import_module

import pytest
from django.apps import apps
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.urls import reverse
from model_bakery import baker

from bpp.kody_jezykow import kod_dla_nazwy
from bpp.models import (
    Jezyk,
    Typ_KBN,
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
    res = admin_client.post(
        reverse(URL),
        {"action": "ukryj_wszystkie_nieuzywane", "potwierdzam": "1"},
        follow=True,
    )
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
    admin_client.post(
        reverse(URL), {"action": "ukryj_wszystkie_nieuzywane", "potwierdzam": "1"}
    )
    assert _stan(jezyk) == (True,)


@pytest.mark.django_db
def test_ukryj_wszystkie_nieuzywane_wymaga_uprawnienia(client, django_user_model):
    jezyk = _jezyk("t-wo")
    user = django_user_model.objects.create_user(
        username="bez-uprawnien", password="x", is_staff=True
    )
    client.force_login(user)
    client.post(
        reverse(URL), {"action": "ukryj_wszystkie_nieuzywane", "potwierdzam": "1"}
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
def test_skrot_crossref_ma_pierwszenstwo_i_widoczny_przed_ukrytym():
    ukryty = _jezyk("t-1", kod_bcp47="xq", widoczny=False)
    widoczny = _jezyk("t-2", kod_bcp47="xq-AA")
    assert Jezyk.dla_kodu("xq") == widoczny

    jawny = _jezyk("t-3", skrot_crossref="xq", kod_bcp47="")
    assert Jezyk.dla_kodu("xq") == jawny
    assert Jezyk.dla_kodu("") is None and Jezyk.dla_kodu(None) is None
    assert ukryty != jawny


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


@pytest.mark.django_db
def test_migracja_uzupelnia_tylko_puste_kody():
    migracja = import_module("bpp.migrations.0533_jezyk_kody_crossref_fd513")
    Jezyk.objects.filter(nazwa__in=["ukraiński", "czeski"]).delete()
    pusty = baker.make(Jezyk, nazwa="ukraiński", skrot="t-ukr", kod_bcp47="")
    reczny = baker.make(Jezyk, nazwa="czeski", skrot="t-cz", kod_bcp47="cs-CZ")
    nieznany = baker.make(Jezyk, nazwa="t-klingoński", skrot="t-kl", kod_bcp47="")

    migracja.uzupelnij_kody(apps, None)

    for jezyk in (pusty, reczny, nieznany):
        jezyk.refresh_from_db()
    assert (pusty.kod_bcp47, reczny.kod_bcp47, nieznany.kod_bcp47) == (
        "uk",
        "cs-CZ",
        "",
    )


# --- edycja rekordu z ukrytym językiem ---------------------------------------


def _formularz(model, admin_user, obj=None):
    request = RequestFactory().get("/")
    request.user = admin_user
    klasa = admin.site._registry[model].get_form(request, obj)
    return klasa(instance=obj) if obj is not None else klasa()


@pytest.mark.django_db
def test_rekord_z_ukrytym_jezykiem_da_sie_zapisac(admin_user):
    """Ukryty język znika z list wyboru nowych rekordów, ale rekord, który
    już go ma, musi go dalej pokazywać i przyjmować przy zapisie."""
    ukryty = _jezyk("t-uk", widoczny=False)
    inny_ukryty = _jezyk("t-uk2", widoczny=False)
    rekord = baker.make(
        Wydawnictwo_Ciagle, jezyk=ukryty, jezyk_alt=ukryty, jezyk_orig=None
    )

    form = _formularz(Wydawnictwo_Ciagle, admin_user, rekord)
    for pole in ("jezyk", "jezyk_alt"):
        assert form.fields[pole].clean(str(ukryty.pk)) == ukryty
        # …ale innego ukrytego języka wybrać się nie da.
        with pytest.raises(ValidationError):
            form.fields[pole].clean(str(inny_ukryty.pk))
    # Pole bez wartości: tylko widoczne języki.
    assert ukryty not in form.fields["jezyk_orig"].queryset

    nowy = _formularz(Wydawnictwo_Ciagle, admin_user)
    for pole in ("jezyk", "jezyk_alt", "jezyk_orig"):
        assert ukryty not in nowy.fields[pole].queryset
        assert nowy.fields[pole].queryset.filter(widoczny=True).exists()


@pytest.mark.django_db
def test_rekord_z_ukrytym_typem_mnisw_da_sie_zapisac(admin_user):
    """Ten sam mechanizm dla pozostałych ukrywanych słowników."""
    ukryty = baker.make(Typ_KBN, nazwa="t-ukryty", skrot="t-uk", ukryty=True)
    rekord = baker.make(Wydawnictwo_Zwarte, typ_kbn=ukryty)

    form = _formularz(Wydawnictwo_Zwarte, admin_user, rekord)
    assert form.fields["typ_kbn"].clean(str(ukryty.pk)) == ukryty
    assert ukryty not in _formularz(Wydawnictwo_Zwarte, admin_user).fields[
        "typ_kbn"
    ].queryset


@pytest.mark.django_db
def test_streszczenie_i_zrodlo_z_ukrytym_jezykiem(admin_user):
    ukryty = _jezyk("t-uk", widoczny=False)
    zrodlo = baker.make(Zrodlo, jezyk=ukryty)
    form = _formularz(Zrodlo, admin_user, zrodlo)
    assert form.fields["jezyk"].clean(str(ukryty.pk)) == ukryty
    assert ukryty not in _formularz(Zrodlo, admin_user).fields["jezyk"].queryset

    rekord = baker.make(Wydawnictwo_Ciagle)
    streszczenie = baker.make(
        Wydawnictwo_Ciagle_Streszczenie, rekord=rekord, jezyk_streszczenia=ukryty
    )
    request = RequestFactory().get("/")
    request.user = admin_user
    model_admin = admin.site._registry[Wydawnictwo_Ciagle]
    inline = next(
        i
        for i in model_admin.get_inline_instances(request, rekord)
        if i.model is Wydawnictwo_Ciagle_Streszczenie
    )
    formset = inline.get_formset(request, rekord)(instance=rekord)
    pola = [f.fields["jezyk_streszczenia"] for f in formset.forms]
    istniejace = formset.forms[0]
    assert istniejace.instance == streszczenie
    assert ukryty in pola[0].queryset
    assert ukryty not in formset.empty_form.fields["jezyk_streszczenia"].queryset


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
