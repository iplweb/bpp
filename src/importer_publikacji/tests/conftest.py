import pytest

from bpp.const import GR_WPROWADZANIE_DANYCH


@pytest.fixture
def importer_user(db):
    """Użytkownik z uprawnieniami do importu."""
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    User = get_user_model()
    user = User.objects.create_user(
        username="importer",
        password="testpass123",
    )
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    return user


@pytest.fixture
def importer_client(importer_user, client):
    """Zalogowany klient z uprawnieniami do importu."""
    client.force_login(importer_user)
    return client


@pytest.fixture
def sample_crossref_data():
    """Przykładowe dane CrossRef API."""
    return {
        "DOI": "10.1234/test.2024.001",
        "title": ["Test Publication Title"],
        "type": "journal-article",
        "author": [
            {
                "family": "Kowalski",
                "given": "Jan",
                "ORCID": "https://orcid.org/0000-0001-2345-6789",
            },
            {
                "family": "Nowak",
                "given": "Anna",
            },
        ],
        "container-title": ["Test Journal"],
        "short-container-title": ["Test J."],
        "publisher": "Test Publisher",
        "language": "en",
        "volume": "42",
        "issue": "3",
        "page": "100-110",
        "published": {"date-parts": [[2024]]},
        "ISSN": ["1234-5678"],
        "issn-type": [
            {"type": "print", "value": "1234-5678"},
        ],
        "subject": ["Computer Science"],
        "resource": {"primary": {"URL": "https://example.com/article"}},
        "license": [
            {
                "URL": "https://creativecommons.org/licenses/by/4.0/",
                "delay-in-days": 0,
            }
        ],
    }
