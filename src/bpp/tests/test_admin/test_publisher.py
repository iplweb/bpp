from bpp.const import PBN_UID_LEN


def test_PublisherAdmin_get_search_results_tekst(admin_client):
    url = "/admin/pbn_api/publisher/autocomplete/?term=tekt"
    res = admin_client.get(url, follow=True)
    assert res.status_code == 200


def test_PublisherAdmin_get_search_results_pbn_uid(admin_client):
    x = "A" * PBN_UID_LEN

    url = "/admin/pbn_api/publisher/autocomplete/?term=" + x

    res = admin_client.get(url, follow=True)
    assert res.status_code == 200
