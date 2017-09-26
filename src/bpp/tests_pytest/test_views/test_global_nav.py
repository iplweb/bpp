# -*- encoding: utf-8 -*-
import pytest
from django.contrib.contenttypes.models import ContentType
from django.http.response import HttpResponseNotAllowed, HttpResponseRedirect
from model_mommy import mommy

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
    ])
@pytest.mark.django_db
def test_global_nav_redir(model, source):
    class FakeRequest:
        method = "GET"
        GET = {"source": source}

    if model == Rekord:
        mommy.make(Wydawnictwo_Ciagle)
        a = Rekord.objects.first()
    else:
        a = mommy.make(model)

    res = global_nav_redir(FakeRequest(), "%s-%s" % (
        ContentType.objects.get_for_model(a).pk,
        a.pk
    ))

    assert isinstance(res, HttpResponseRedirect)

