import uuid

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_anon_utworz_nie_daje_500(client):
    """Anon GET na gejtowany liveops CreateView — 302→login, NIE 500."""
    resp = client.get(reverse("import_polon:utworz-import"))
    assert resp.status_code != 500, "500-for-anon (handle_no_permission MRO bug)"
    assert resp.status_code == 302


@pytest.mark.django_db
def test_anon_restart_nie_daje_500(client):
    """Anon POST na gejtowany liveops RestartView — 302→login, NIE 500."""
    url = reverse("import_polon:importplikupolon-restart", args=[uuid.uuid4()])
    resp = client.post(url)
    assert resp.status_code != 500, "500-for-anon (handle_no_permission MRO bug)"
    assert resp.status_code == 302
