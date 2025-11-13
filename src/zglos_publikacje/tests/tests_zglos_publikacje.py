import os

import pytest
from django.urls import reverse
from model_bakery import baker

from zglos_publikacje.models import (
    Obslugujacy_Zgloszenia_Wydzialow,
    Zgloszenie_Publikacji,
)

from django.contrib.auth.models import Group

from bpp.const import GR_ZGLOSZENIA_PUBLIKACJI
from bpp.core import zgloszenia_publikacji_emails
from bpp.models import BppUser

EMAIL = "test@panie.random.lol.pl"


@pytest.mark.django_db
def test_pierwsza_strona_wymagaj_zgody_na_publikacje(webtest_app, uczelnia):
    uczelnia.pytaj_o_zgode_na_publikacje_pelnego_tekstu = True
    uczelnia.save()

    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    page.forms[0]["0-tytul_oryginalny"] = "123"
    page.forms[0]["0-rok"] = "2020"
    page.forms[0][
        "0-rodzaj_zglaszanej_publikacji"
    ] = Zgloszenie_Publikacji.Rodzaje.ARTYKUL_LUB_MONOGRAFIA
    page.forms[0]["0-email"] = "123@123.pl"

    page2 = page.forms[0].submit()
    assert page2.status_code == 200
    assert b"To pole jest wymagane" in page2.content

    page2.forms[0]["0-zgoda_na_publikacje_pelnego_tekstu"] = "False"
    page2 = page2.forms[0].submit()
    assert page2.status_code == 200
    assert b"Plik" in page2.content


@pytest.mark.django_db
def test_pierwsza_strona_wymagaj_pliku(webtest_app, uczelnia):
    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    page.forms[0]["0-tytul_oryginalny"] = "123"
    page.forms[0]["0-rok"] = "2020"
    page.forms[0][
        "0-rodzaj_zglaszanej_publikacji"
    ] = Zgloszenie_Publikacji.Rodzaje.ARTYKUL_LUB_MONOGRAFIA
    page.forms[0]["0-email"] = "123@123.pl"

    page2 = page.forms[0].submit()
    assert page2.status_code == 200
    assert b"Plik" in page2.content


@pytest.mark.django_db
def test_pierwsza_strona_nie_wymagaj_pliku(webtest_app, uczelnia):
    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    page.forms[0]["0-tytul_oryginalny"] = "123"
    page.forms[0]["0-strona_www"] = "https://onet.pl"
    page.forms[0]["0-rok"] = "2020"
    page.forms[0]["0-email"] = "123@123.pl"

    page2 = page.forms[0].submit()
    assert page2.status_code == 200
    assert b"Plik" not in page2.content


def test_druga_strona(
    webtest_app,
    wprowadzanie_danych_user,
    typy_odpowiedzialnosci,
    uczelnia,
    django_capture_on_commit_callbacks,
):
    assert zgloszenia_publikacji_emails()

    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    page.forms[0]["0-tytul_oryginalny"] = "123"
    page.forms[0]["0-rok"] = "2020"
    page.forms[0][
        "0-rodzaj_zglaszanej_publikacji"
    ] = Zgloszenie_Publikacji.Rodzaje.ARTYKUL_LUB_MONOGRAFIA
    page.forms[0]["0-strona_www"] = "https://onet.pl/"
    page.forms[0]["0-email"] = "123@123.pl"

    page2 = page.forms[0].submit()

    page3 = page2.forms[0].submit()

    page3.forms[0]["3-opl_pub_cost_free"] = "true"

    with django_capture_on_commit_callbacks(execute=True):  # as callbacks:
        page4 = page3.forms[0].submit().maybe_follow()

    assert b"powiadomiony" in page4.content
    from django.core import mail

    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_zglos_publikacje_bez_pliku_artykul(
    webtest_app, uczelnia, typy_odpowiedzialnosci
):
    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    page.forms[0]["0-tytul_oryginalny"] = "123"
    page.forms[0][
        "0-rodzaj_zglaszanej_publikacji"
    ] = Zgloszenie_Publikacji.Rodzaje.ARTYKUL_LUB_MONOGRAFIA

    page.forms[0]["0-strona_www"] = "https://onet.pl"
    page.forms[0]["0-rok"] = "2020"
    page.forms[0]["0-email"] = "123@123.pl"

    # Lista autorow
    page2 = page.forms[0].submit()

    # Dane o platnosciach
    page3 = page2.forms[0].submit()
    page3.forms[0]["3-opl_pub_cost_free"] = "true"

    # Sukces!
    page4 = page3.forms[0].submit().maybe_follow()

    assert b"zostanie zaakceptowane" in page4.content


@pytest.mark.django_db
def test_zglos_publikacje_bez_pliku_nie_artykul(
    webtest_app, uczelnia, typy_odpowiedzialnosci
):
    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    page.forms[0]["0-tytul_oryginalny"] = "123"
    page.forms[0][
        "0-rodzaj_zglaszanej_publikacji"
    ] = Zgloszenie_Publikacji.Rodzaje.POZOSTALE

    page.forms[0]["0-strona_www"] = "https://onet.pl"
    page.forms[0]["0-rok"] = "2020"
    page.forms[0]["0-email"] = "123@123.pl"

    # Lista autorow
    page2 = page.forms[0].submit()

    # Sukces!
    page3 = page2.forms[0].submit().maybe_follow()

    assert b"zostanie zaakceptowane" in page3.content


@pytest.mark.django_db
def test_zglos_publikacje_tytul_wielkosc_liter(
    webtest_app, uczelnia, typy_odpowiedzialnosci
):
    TYTUL_PRACY = "Test Wielkich Liter"

    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    page.forms[0]["0-tytul_oryginalny"] = TYTUL_PRACY
    page.forms[0][
        "0-rodzaj_zglaszanej_publikacji"
    ] = Zgloszenie_Publikacji.Rodzaje.POZOSTALE

    page.forms[0]["0-strona_www"] = "https://onet.pl"
    page.forms[0]["0-rok"] = "2020"
    page.forms[0]["0-email"] = "123@123.pl"

    # Lista autorow
    page2 = page.forms[0].submit()

    # Sukces!
    page2.forms[0].submit().maybe_follow()

    assert Zgloszenie_Publikacji.objects.first().tytul_oryginalny == TYTUL_PRACY


def zrob_submit_calego_formularza(
    webtest_app,
    django_capture_on_commit_callbacks,
    autor=None,
    jednostka=None,
    tytul_oryginalny="123",
):

    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    page.forms[0]["0-tytul_oryginalny"] = tytul_oryginalny
    page.forms[0]["0-rok"] = "2020"
    page.forms[0][
        "0-rodzaj_zglaszanej_publikacji"
    ] = Zgloszenie_Publikacji.Rodzaje.ARTYKUL_LUB_MONOGRAFIA
    page.forms[0]["0-strona_www"] = "https://onet.pl/"
    page.forms[0]["0-email"] = "123@123.pl"

    page2 = page.forms[0].submit()

    if autor is not None:
        page2.forms[0]["2-0-autor"].force_value(autor.pk)
        page2.forms[0]["2-0-jednostka"].force_value(jednostka.pk)

    page3 = page2.forms[0].submit()
    # page3.showbrowser()

    page3.forms[0]["3-opl_pub_cost_free"] = "true"

    with django_capture_on_commit_callbacks(execute=True):  # as callbacks:
        page4 = page3.forms[0].submit().maybe_follow()

    assert b"powiadomiony" in page4.content


def test_wysylanie_maili_brak_ludzi_w_bazie(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    wydzial,
    jednostka,
):
    from django.core import mail

    zrob_submit_calego_formularza(webtest_app, django_capture_on_commit_callbacks)

    assert len(mail.outbox) == 0

    # Bo nie było do kogo wysłać


def test_wysylanie_maili_trafi_do_grupy_zglaszanie_publikacji(
    webtest_app,
    django_capture_on_commit_callbacks,
    normal_django_user,
    typy_odpowiedzialnosci,
    uczelnia,
    wydzial,
    jednostka,
):
    normal_django_user.email = EMAIL
    normal_django_user.save()

    normal_django_user.groups.add(
        Group.objects.get_or_create(name=GR_ZGLOSZENIA_PUBLIKACJI)[0]
    )

    from django.core import mail

    zrob_submit_calego_formularza(webtest_app, django_capture_on_commit_callbacks)
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [
        EMAIL,
    ]


def test_wysylanie_maili_tytul_ma_nowe_linie(
    webtest_app,
    django_capture_on_commit_callbacks,
    normal_django_user,
    typy_odpowiedzialnosci,
    uczelnia,
    wydzial,
    jednostka,
):
    normal_django_user.email = EMAIL
    normal_django_user.save()

    normal_django_user.groups.add(
        Group.objects.get_or_create(name=GR_ZGLOSZENIA_PUBLIKACJI)[0]
    )

    from django.core import mail

    zrob_submit_calego_formularza(
        webtest_app,
        django_capture_on_commit_callbacks,
        tytul_oryginalny="PANIE\nCzy to pojdzie?",
    )
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [
        EMAIL,
    ]


def test_wysylanie_maili_obslugujacym_zgloszenia(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    wydzial,
    aktualna_jednostka,
    autor_jan_kowalski,
):
    inny_user = baker.make(BppUser, email=EMAIL)
    Obslugujacy_Zgloszenia_Wydzialow.objects.create(user=inny_user, wydzial=wydzial)

    zrob_submit_calego_formularza(
        webtest_app,
        django_capture_on_commit_callbacks,
        autor=autor_jan_kowalski,
        jednostka=aktualna_jednostka,
    )

    from django.core import mail

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [inny_user.email]


def test_zglos_publikacje_czy_pliki_trafiaja_do_bazy(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
):
    example_content = open(
        os.path.join(os.path.dirname(__name__), "example.pdf"), "rb"
    ).read()

    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    page.forms[0]["0-tytul_oryginalny"] = "123"
    page.forms[0]["0-rok"] = "2020"
    page.forms[0][
        "0-rodzaj_zglaszanej_publikacji"
    ] = Zgloszenie_Publikacji.Rodzaje.ARTYKUL_LUB_MONOGRAFIA
    page.forms[0]["0-email"] = "123@123.pl"

    page2 = page.forms[0].submit()
    page2.forms[0]["1-plik"] = (
        "123.pdf",
        example_content,
    )

    page3 = page2.forms[0].submit()

    page4 = page3.forms[0].submit()

    page4.forms[0]["3-opl_pub_cost_free"] = "true"

    with django_capture_on_commit_callbacks(execute=True):  # as callbacks:
        page4.forms[0].submit().maybe_follow()

    assert Zgloszenie_Publikacji.objects.first().plik.read() == example_content


@pytest.mark.django_db
def test_wymagaj_logowania_zglos_publikacje_niezalogowany_przekierowanie(
    webtest_app, uczelnia
):
    """Test: niezalogowany użytkownik z wymagaj_logowania_zglos_publikacje=True
    → przekierowanie na stronę logowania"""
    uczelnia.wymagaj_logowania_zglos_publikacje = True
    uczelnia.save()

    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url, expect_errors=True)

    # Powinniśmy dostać przekierowanie 302
    assert page.status_code == 302
    # Przekierowanie na stronę logowania
    assert "/accounts/login/" in page.location
    # Sprawdź czy jest parametr next w URL
    assert "next=" in page.location


@pytest.mark.django_db
def test_wymagaj_logowania_zglos_publikacje_zalogowany_dostep(
    webtest_app, uczelnia, normal_django_user
):
    """Test: zalogowany użytkownik z wymagaj_logowania_zglos_publikacje=True
    → dostęp do formularza"""
    uczelnia.wymagaj_logowania_zglos_publikacje = True
    uczelnia.save()

    # Zaloguj użytkownika
    webtest_app.set_user(normal_django_user)

    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)

    # Powinniśmy dostać stronę formularza
    assert page.status_code == 200
    assert b"Formularz" in page.content or b"formularz" in page.content


@pytest.mark.django_db
def test_wymagaj_logowania_zglos_publikacje_false_niezalogowany_dostep(
    webtest_app, uczelnia
):
    """Test: niezalogowany użytkownik z wymagaj_logowania_zglos_publikacje=False
    → dostęp do formularza (zachowanie wsteczne)"""
    uczelnia.wymagaj_logowania_zglos_publikacje = False
    uczelnia.save()

    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)

    # Powinniśmy dostać stronę formularza
    assert page.status_code == 200
    assert b"tytul_oryginalny" in page.content


@pytest.mark.django_db
def test_wymagaj_logowania_nadpisuje_pokazuj_formularz_ustawienie(
    webtest_app, uczelnia
):
    """Test: pole wymagaj_logowania_zglos_publikacje nadpisuje logikę pokazuj_formularz_zglaszania_publikacji.
    Nawet gdy pokazuj_formularz_zglaszania_publikacji='always', niezalogowany użytkownik
    powinien być przekierowany na logowanie gdy wymagaj_logowania_zglos_publikacje=True"""
    from bpp.models.fields import OpcjaWyswietlaniaField

    uczelnia.pokazuj_formularz_zglaszania_publikacji = (
        OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    )
    uczelnia.wymagaj_logowania_zglos_publikacje = True
    uczelnia.save()

    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url, expect_errors=True)

    # Mimo że pokazuj_formularz='always', użytkownik powinien być przekierowany
    assert page.status_code == 302
    assert "/accounts/login/" in page.location
