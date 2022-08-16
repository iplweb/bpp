import pytest
from django.db import transaction
from django.urls import reverse

from zglos_publikacje.models import Zgloszenie_Publikacji

from bpp.core import editors_emails


@pytest.mark.django_db
def test_pierwsza_strona_wymagaj_pliku(webtest_app):
    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    page.forms[0]["0-tytul_oryginalny"] = "123"
    page.forms[0]["0-rok"] = "2020"
    page.forms[0]["0-email"] = "123@123.pl"

    page2 = page.forms[0].submit()
    assert page2.status_code == 200
    assert b"Plik" in page2.content


@pytest.mark.django_db
def test_pierwsza_strona_nie_wymagaj_pliku(webtest_app):
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
    webtest_app, wprowadzanie_danych_user, transactional_db, typy_odpowiedzialnosci
):
    assert editors_emails()
    try:
        url = reverse("zglos_publikacje:nowe_zgloszenie")
        page = webtest_app.get(url)
        page.forms[0]["0-tytul_oryginalny"] = "123"
        page.forms[0]["0-rok"] = "2020"
        page.forms[0]["0-strona_www"] = "https://onet.pl/"
        page.forms[0]["0-email"] = "123@123.pl"

        page2 = page.forms[0].submit()

        page3 = page2.forms[0].submit()

        page3.forms[0]["3-opl_pub_cost_free"] = "true"

        page4 = page3.forms[0].submit().maybe_follow()

        assert b"powiadomiony" in page4.content
        transaction.commit()
        from django.core import mail

        assert len(mail.outbox) == 1
    finally:
        Zgloszenie_Publikacji.objects.all().delete()
