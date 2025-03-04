import pytest

from bpp.views.autocomplete.wydawnictwo_nadrzedne_w_pbn import (
    Wydawnictwo_Nadrzedne_W_PBNAutocomplete,
)


@pytest.mark.django_db
def test_Wydawnictwo_Nadrzedne_W_PBNAutocomplete_post_mniej_jak_max_wiecej_jak_1(
    mocker, rf, pbn_uczelnia
):
    x = Wydawnictwo_Nadrzedne_W_PBNAutocomplete()

    mocker.patch("pbn_api.integrator.zapisz_mongodb")
    search_publications = mocker.patch("pbn_api.client.PBNClient.search_publications")
    mocker.patch("pbn_api.client.PBNClient.get_publication_by_id")

    search_publications.return_value = [
        {
            "mongoId": "asdf",
        }
    ] * 3  # mniej jak MAX, wiecej jak 1
    req = rf.post("/", {"text": "foobar"})

    x.request = req
    x.post(
        req,
    )
