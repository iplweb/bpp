import pytest
from django.contrib.auth.models import AnonymousUser

from bpp.models import Rekord


def _anonymous_request(rf):
    # render_to_string(..., request=request) przechodzi przez context
    # processory (m.in. pbn_token_aktualny), które czytają request.user.
    # RequestFactory — w odróżnieniu od Client — nie przepuszcza żądania
    # przez middleware, więc request.user trzeba dostawić ręcznie
    # (ten sam wzorzec co w test_permissions.py / test_zapytanie.py).
    request = rf.get("/")
    request.user = AnonymousUser()
    return request


@pytest.mark.django_db
def test_document_export_response_html_zawiera_opis(rf, wydawnictwo_ciagle, denorms):
    # "list" to id ReportType z multiseek_registry.reports (etykieta w UI
    # to "lista" — nie mylić kluczy raportu z ich polskimi etykietami).
    from bpp.views.multiseek_export import document_export_response

    denorms.flush()
    request = _anonymous_request(rf)
    response = document_export_response(
        Rekord.objects.all(), request, "list", "Tytuł", "html"
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/html")
    # sanitize_export_html (nh3.clean) zdejmuje class z <div> (patrz komentarz
    # w export-document.html) — sprawdzamy więc strukturę partiala listy
    # (<ol>, nie <table>) i realną treść opisu bibliograficznego rekordu.
    assert b"<ol" in response.content
    assert b"<table" not in response.content
    assert wydawnictwo_ciagle.tytul_oryginalny.encode() in response.content


@pytest.mark.django_db
def test_document_export_response_tabela_ma_sumy(rf, wydawnictwo_ciagle, denorms):
    wydawnictwo_ciagle.punkty_kbn = 40
    wydawnictwo_ciagle.save()
    denorms.flush()

    # "table" to id ReportType (etykieta w UI: "tabela").
    from bpp.views.multiseek_export import document_export_response

    request = _anonymous_request(rf)
    response = document_export_response(
        Rekord.objects.all(), request, "table", "Tytuł", "html"
    )

    assert b"<table" in response.content
    assert b"Suma" in response.content
    assert b"40.00" in response.content


@pytest.mark.django_db
def test_document_export_response_docx(rf, wydawnictwo_ciagle, denorms):
    from bpp.views.multiseek_export import document_export_response

    denorms.flush()
    request = _anonymous_request(rf)
    response = document_export_response(
        Rekord.objects.all(), request, "list", "Tytuł", "docx"
    )

    assert "wordprocessingml" in response["Content-Type"]
