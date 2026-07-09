import pytest
from django.urls import reverse
from model_bakery import baker

from importer_publikacji.models import (
    ImportSession,
    MultipleWorksImport,
    MultipleWorksImportEntry,
)

TWO_ENTRIES = """@article{a,
  title = {Pierwsza},
  author = {Kowalski, Jan},
  year = {2021},
}

@book{b,
  title = {Druga},
  author = {Nowak, Anna},
  year = {2022},
}"""

ONE_ENTRY = """@article{a,
  title = {Jedyna},
  author = {Kowalski, Jan},
  year = {2021},
}"""


@pytest.fixture
def operator(django_user_model):
    user = baker.make(django_user_model, is_superuser=True, is_staff=True)
    return user


@pytest.mark.django_db
def test_fetch_two_entries_creates_batch_and_hx_redirects(client, operator):
    client.force_login(operator)
    resp = client.post(
        reverse("importer_publikacji:fetch"),
        {"provider": "BibTeX", "text_input": TWO_ENTRIES},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    batch = MultipleWorksImport.objects.get()
    assert batch.entries.count() == 2
    assert MultipleWorksImportEntry.objects.filter(session__isnull=False).count() == 0
    expected = reverse(
        "importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk}
    )
    assert resp["HX-Redirect"] == expected
    # Zaden ImportSession nie powstal (leniwy drip):
    assert ImportSession.objects.count() == 0


@pytest.mark.django_db
def test_fetch_single_entry_unchanged(client, operator):
    client.force_login(operator)
    resp = client.post(
        reverse("importer_publikacji:fetch"),
        {"provider": "BibTeX", "text_input": ONE_ENTRY},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    assert MultipleWorksImport.objects.count() == 0
    session = ImportSession.objects.get()
    assert resp["HX-Redirect"] == reverse(
        "importer_publikacji:task-status", kwargs={"session_id": session.pk}
    )
