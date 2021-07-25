from django.urls import reverse


def test_SentDataAdmin_list_filter_works(admin_client):
    url = reverse("admin:pbn_api_sentdata_changelist")
    res = admin_client.get(url + "?q=123")
    assert res.status_code == 200
