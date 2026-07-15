import pytest
from django.urls import reverse

from bpp import const
from bpp.models.system import Jezyk


# Pole ``jezyk`` w formularzu przechowuje PK rekordu ``Jezyk`` (FK), a PK jest
# artefaktem kolejności seedu — po ``TRUNCATE`` (transakcyjny sąsiad) słownik
# wraca z INNYM PK, więc hardkodowanie wartości "2" czyni test flaky.
# Oczekiwaną wartość wyliczamy z klucza naturalnego (``skrot_crossref="en"``,
# bo kaseta CrossRef dla tego DOI deklaruje ``language="en"``) — tak samo jak
# produkcyjny ``Komparator.porownaj_language``.
def _pk_jezyka_angielskiego():
    return str(Jezyk.objects.get(skrot_crossref="en").pk)


# Pomijamy matchowanie host/port, bo za egress proxy (np.
# w środowisku Claude Code) VCR widzi adres proxy zamiast
# docelowego api.crossref.org i nie dopasowuje kasety.
@pytest.mark.vcr(match_on=("method", "scheme", "path", "query"))
@pytest.mark.parametrize(
    "identyfikator_doi,nazwa_pola,oczekiwana_wartosc",
    [
        pytest.param(
            "10.12775/jehs.2022.12.07.045",
            "tytul_oryginalny",
            "Neurological and neuropsychological post-covid complications",
            id="tytul",
        ),
        pytest.param(
            "10.2478/cpp-2022-0006",
            "jezyk",
            _pk_jezyka_angielskiego,
            id="jezyk",
        ),
    ],
)
@pytest.mark.parametrize("url", ["wydawnictwo_ciagle"])
def test_integracyjny_strona_admina(
    url,
    identyfikator_doi,
    admin_app,
    jezyki,
    charaktery_formalne,
    nazwa_pola,
    oczekiwana_wartosc,
):
    # Literał albo callable rozwiązywany dopiero po zaseedowaniu słowników.
    oczekiwana = (
        oczekiwana_wartosc() if callable(oczekiwana_wartosc) else oczekiwana_wartosc
    )

    url = (
        reverse(f"admin:bpp_{url}_add")
        + f"?{const.CROSSREF_API_PARAM}={identyfikator_doi}"
    )

    page = admin_app.get(url)

    assert page.forms["wydawnictwo_ciagle_form"][nazwa_pola].value == oczekiwana
