import pytest
from django.urls import reverse

from bpp import const


@pytest.mark.vcr
@pytest.mark.parametrize(
    "identyfikator_doi,nazwa_pola,wartosc",
    [
        (
            "10.12775/jehs.2022.12.07.045",
            "tytul_oryginalny",
            "Neurological and neuropsychological post-covid complications",
        ),
        ("10.2478/cpp-2022-0006", "jezyk", "2"),
    ],
)
@pytest.mark.parametrize("url", ["wydawnictwo_ciagle"])
def test_integracyjny_strona_admina(
    url, identyfikator_doi, admin_app, jezyki, charaktery_formalne, nazwa_pola, wartosc
):
    url = (
        reverse(f"admin:bpp_{url}_add")
        + f"?{const.CROSSREF_API_PARAM}={identyfikator_doi}"
    )

    page = admin_app.get(url)

    assert page.forms[1][nazwa_pola].value == wartosc
