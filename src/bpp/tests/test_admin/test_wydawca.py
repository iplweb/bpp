def test_Wydawca_search_space_len_24_like_pbn_uid(admin_client):
    url = "/admin/bpp/wydawca/?q=uniwersytet przyrodniczy"
    res = admin_client.get(url, follow=True)
    assert res.status_code == 200


def test_Wydawca_search_no_space_len_24_like_pbn_uid(admin_client):
    url = "/admin/bpp/wydawca/?q=uniwersytet-przyrodniczy"
    res = admin_client.get(url, follow=True)
    assert res.status_code == 200
