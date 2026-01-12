import base64

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Rekord, Wydawnictwo_Ciagle


@pytest.fixture
def autor_m():
    return baker.make(
        Autor,
        # base64, bo RODO:
        nazwisko=base64.decodebytes(b"TWllbG5pY3plaw==\n").decode("ascii"),
        imiona="Katarzyna",
    )


@pytest.mark.vcr
def test_crossref_api_autor_wo_selenium(admin_app, autor_m):
    url = "/admin/bpp/wydawnictwo_ciagle/pobierz-z-crossref/"
    page = admin_app.get(url)
    page.forms["crossref_form"]["identyfikator_doi"] = "10.12775/jehs.2022.12.07.045"
    page = page.forms["crossref_form"].submit().maybe_follow()
    if b"id_ustaw_orcid_button_author.0" not in page.content:
        page.showbrowser()
        raise Exception


@pytest.fixture
def wydawnictwo_ciagle_jehs_2022():
    return baker.make(
        Wydawnictwo_Ciagle,
        doi="10.12775/jehs.2022.12.07.045",
        tytul_oryginalny="Neurological and neuropsychological post-covid complications",
    )


@pytest.mark.django_db
@pytest.mark.vcr(ignore_localhost=True)
def test_crossref_api_strony_view(
    wydawnictwo_ciagle_jehs_2022,
    csrf_exempt_django_admin_app,
):
    csrf_exempt_django_admin_app.post(
        reverse("bpp:api_ustaw_strony"),
        {"rekord": Rekord.objects.all().first().form_post_pk, "strony": "447-452"},
    )

    wydawnictwo_ciagle_jehs_2022.refresh_from_db()

    return wydawnictwo_ciagle_jehs_2022.strony == "447-452"
