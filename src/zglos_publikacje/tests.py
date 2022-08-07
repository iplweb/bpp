import pytest
from django.db import transaction
from django.urls import reverse

from zglos_publikacje.models import Zgloszenie_Publikacji

from bpp.core import editors_emails


@pytest.mark.django_db
def test_pierwsza_strona(webtest_app):
    url = reverse("zglos_publikacje:nowe_zgloszenie")
    page = webtest_app.get(url)
    page.forms[1]["0-tytul_oryginalny"] = "123"
    page.forms[1]["0-email"] = "123@123.pl"

    page2 = page.forms[0].submit()
    assert page2.status_code == 200


def test_druga_strona(webtest_app, wprowadzanie_danych_user, transactional_db):
    assert editors_emails()
    try:
        url = reverse("zglos_publikacje:nowe_zgloszenie")
        page = webtest_app.get(url)
        page.forms[0]["0-tytul_oryginalny"] = "123"
        page.forms[0]["0-email"] = "123@123.pl"

        page2 = page.forms[0].submit()
        page2.forms[0]["1-opl_pub_cost_free"] = "true"

        page3 = page2.forms[0].submit().maybe_follow()
        assert b"powiadomiony" in page3.content
        transaction.commit()
        from django.core import mail

        assert len(mail.outbox) == 1
    finally:
        Zgloszenie_Publikacji.objects.all().delete()
