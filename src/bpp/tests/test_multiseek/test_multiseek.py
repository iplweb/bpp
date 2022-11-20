import json

import pytest
from django.conf import settings
from django.urls import reverse
from multiseek.views import MULTISEEK_SESSION_KEY


def test_multiseek_status_korekty_ukrywanie(
    uczelnia,
    client,
    wydawnictwo_zwarte_przed_korekta,
    wydawnictwo_zwarte_po_korekcie,
    wydawnictwo_zwarte_w_trakcie_korekty,
    statusy_korekt,
    admin_client,
):
    res = client.get(reverse("multiseek:results"))
    assert b"Rezultaty wyszukiwania (3" in res.content

    for elem in ["przed korektą", "w trakcie korekty"]:
        uczelnia.ukryj_status_korekty_set.create(status_korekty=statusy_korekt[elem])

    res = client.get(reverse("multiseek:results"))
    assert b"Rezultaty wyszukiwania (1" in res.content

    res = admin_client.get(reverse("multiseek:results"))
    assert b"Rezultaty wyszukiwania (3" in res.content


@pytest.mark.django_db
def test_multiseek_tabelka_wyswietlanie(
    webtest_app,
    wydawnictwo_ciagle,
):

    webtest_app.set_cookie(settings.SESSION_COOKIE_NAME, "whatever")
    page = webtest_app.get(reverse("multiseek:results"))

    webtest_app.session[MULTISEEK_SESSION_KEY] = json.dumps({"report_type": "1"})
    page = webtest_app.get(reverse("multiseek:results"))

    page.showbrowser()
    raise NotImplementedError
