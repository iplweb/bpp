import json

import pytest
from django.http.response import HttpResponseNotAllowed, HttpResponseRedirect
from django.urls import reverse
from model_bakery import baker

from django.contrib.contenttypes.models import ContentType

from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.patent import Patent
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.profile import BppUser
from bpp.models.struktura import Jednostka
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.models.zrodlo import Zrodlo
from bpp.views.global_nav import global_nav_redir


def test_global_nav_redir_err():
    class FakeRequest:
        method = "POST"
        GET = {}

    res = global_nav_redir(FakeRequest(), "")
    assert isinstance(res, HttpResponseNotAllowed)


@pytest.mark.parametrize(
    ["model", "source"],
    [
        (Autor, "user"),
        (Rekord, "user"),
        (Jednostka, "user"),
        (Zrodlo, "user"),
        (Autor, "admin"),
        (Wydawnictwo_Ciagle, "admin"),
        (Wydawnictwo_Zwarte, "admin"),
        (Zrodlo, "admin"),
        (Patent, "admin"),
        (Praca_Habilitacyjna, "admin"),
        (Praca_Doktorska, "admin"),
        (BppUser, "admin"),
    ],
)
@pytest.mark.django_db
def test_global_nav_redir(model, source, typy_odpowiedzialnosci):
    class FakeRequest:
        method = "GET"
        GET = {"source": source}

    if model == Rekord:
        baker.make(Wydawnictwo_Ciagle)
        a = Rekord.objects.first()
    else:
        a = baker.make(model)

    res = global_nav_redir(
        FakeRequest(), f"{ContentType.objects.get_for_model(a).pk}-{a.pk}"
    )

    assert isinstance(res, HttpResponseRedirect)


def test_global_nav_ukrywanie_statusow_przed_korekta_praca_schowana(
    client, uczelnia, wydawnictwo_ciagle, przed_korekta, po_korekcie
):
    wydawnictwo_ciagle.status_korekty = przed_korekta
    wydawnictwo_ciagle.tytul_oryginalny = "123 test"
    wydawnictwo_ciagle.save()

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)

    res = client.get(reverse("bpp:navigation-autocomplete") + "?q=123")

    assert len(json.loads(res.content)["results"]) == 0


def test_global_nav_ukrywanie_statusow_przed_korekta_praca_schowana_ale_dla_admina_widoczna(
    admin_client, uczelnia, wydawnictwo_ciagle, przed_korekta, po_korekcie
):
    wydawnictwo_ciagle.status_korekty = przed_korekta
    wydawnictwo_ciagle.tytul_oryginalny = "123 test"
    wydawnictwo_ciagle.save()

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)

    res = admin_client.get(reverse("bpp:navigation-autocomplete") + "?q=123")

    assert len(json.loads(res.content)["results"]) == 1


def test_global_nav_ukrywanie_statusow_przed_korekta_praca_widoczna(
    client, uczelnia, wydawnictwo_ciagle, przed_korekta, po_korekcie
):
    wydawnictwo_ciagle.status_korekty = po_korekcie
    wydawnictwo_ciagle.tytul_oryginalny = "123 test"
    wydawnictwo_ciagle.save()

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)

    res = client.get(reverse("bpp:navigation-autocomplete") + "?q=123")

    assert len(json.loads(res.content)["results"]) == 1
