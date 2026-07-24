import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_anon_new_nie_daje_500(client):
    """Anon GET na gejtowany liveops CreateView — 302→login, NIE 500."""
    resp = client.get(reverse("import_list_if:new"))
    assert resp.status_code != 500, "500-for-anon (handle_no_permission MRO bug)"
    assert resp.status_code == 302
