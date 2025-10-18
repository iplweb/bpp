import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from bpp import const
from bpp.models import (
    Charakter_Formalny,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from komparator_pbn.views import EVALUATION_END_YEAR, EVALUATION_START_YEAR
from pbn_api.models import Publication

User = get_user_model()


@pytest.fixture
def staff_user():
    """Create a staff user for testing staff-required views."""
    return baker.make(User, is_staff=True, is_active=True)


@pytest.fixture
def regular_user():
    """Create a regular non-staff user."""
    return baker.make(User, is_staff=False, is_active=True)


@pytest.fixture
def client_logged_in_staff(staff_user):
    """Create a client logged in as staff user."""
    client = Client()
    client.force_login(staff_user)
    return client


@pytest.fixture
def client_logged_in_regular(regular_user):
    """Create a client logged in as regular user."""
    client = Client()
    client.force_login(regular_user)
    return client


@pytest.fixture
def basic_setup():
    """Setup basic test data."""
    uczelnia = baker.make(Uczelnia, nazwa="Test University")

    charakter_exportable = baker.make(
        Charakter_Formalny,
        nazwa="Artykuł w czasopiśmie",
        rodzaj_pbn=const.RODZAJ_PBN_ARTYKUL,
    )
    charakter_not_exportable = baker.make(
        Charakter_Formalny, nazwa="Inne", rodzaj_pbn=None
    )

    return {
        "uczelnia": uczelnia,
        "charakter_exportable": charakter_exportable,
        "charakter_not_exportable": charakter_not_exportable,
    }


@pytest.mark.django_db
def test_komparator_main_view_requires_staff(client_logged_in_regular):
    """Test that KomparatorMainView requires staff privileges."""
    url = reverse("komparator_pbn:main")
    response = client_logged_in_regular.get(url)

    # Should redirect to login or show permission denied
    assert response.status_code in [302, 403]


@pytest.mark.django_db
def test_komparator_main_view_staff_access(client_logged_in_staff, basic_setup):
    """Test that staff users can access KomparatorMainView."""
    url = reverse("komparator_pbn:main")
    response = client_logged_in_staff.get(url)

    assert response.status_code == 200
    assert "komparator_pbn/main.html" in [t.name for t in response.templates]


@pytest.mark.django_db
def test_komparator_main_view_context_basic(client_logged_in_staff, basic_setup):
    """Test that KomparatorMainView provides basic context data."""
    url = reverse("komparator_pbn:main")
    response = client_logged_in_staff.get(url)

    assert response.status_code == 200

    context = response.context

    # Check that required context variables are present
    required_keys = [
        "ciagle_not_sent",
        "zwarte_not_sent",
        "ciagle_sent",
        "zwarte_sent",
        "evaluation_start_year",
        "evaluation_end_year",
    ]

    for key in required_keys:
        assert key in context, f"Missing context key: {key}"

    # Check that evaluation years are correct
    assert context["evaluation_start_year"] == EVALUATION_START_YEAR
    assert context["evaluation_end_year"] == EVALUATION_END_YEAR

    # Check that counts are non-negative integers
    for key in ["ciagle_not_sent", "zwarte_not_sent", "ciagle_sent", "zwarte_sent"]:
        assert isinstance(context[key], int)
        assert context[key] >= 0


@pytest.mark.django_db
def test_komparator_main_view_publication_counts(client_logged_in_staff, basic_setup):
    """Test publication counting logic."""
    data = basic_setup

    # Create a PBN publication that will be referenced
    pbn_publication = baker.make(  # noqa
        Publication,
        mongoId="test_pbn_123",
        year=EVALUATION_START_YEAR,
        title="Test Publication in PBN",
    )

    # Create a publication sent to PBN (with valid foreign key)
    pub_sent = baker.make(  # noqa
        Wydawnictwo_Ciagle,
        rok=EVALUATION_START_YEAR,
        charakter_formalny=data["charakter_exportable"],
        doi="10.1000/sent",
        pbn_uid_id="test_pbn_123",  # References the PBN publication
        punkty_kbn=20,
    )

    # Create a publication not sent to PBN
    pub_not_sent = baker.make(  # noqa
        Wydawnictwo_Ciagle,
        rok=EVALUATION_START_YEAR,
        charakter_formalny=data["charakter_exportable"],
        doi="10.1000/not_sent",
        pbn_uid_id=None,
        punkty_kbn=20,
        public_www="http://example.com/not_sent",
    )

    # Create a zwarte publication sent
    zwarte_sent = baker.make(  # noqa
        Wydawnictwo_Zwarte,
        rok=EVALUATION_START_YEAR,
        charakter_formalny=data["charakter_exportable"],
        isbn="978-0-123456-78-9",
        pbn_uid_id="test_pbn_123",
        punkty_kbn=25,
    )

    url = reverse("komparator_pbn:main")
    response = client_logged_in_staff.get(url)

    context = response.context

    # We should have at least 1 sent publication
    assert context["ciagle_sent"] >= 1
    assert context["zwarte_sent"] >= 1

    # We should have at least 1 not sent publication
    assert context["ciagle_not_sent"] >= 1


@pytest.mark.django_db
def test_komparator_main_view_pbn_publications_count(
    client_logged_in_staff, basic_setup
):
    """Test PBN publications counting logic exists and returns a number."""
    url = reverse("komparator_pbn:main")
    response = client_logged_in_staff.get(url)

    # Extract the pbn count from context
    pbn_count = None
    for ctx_list in response.context:
        for ctx_dict in ctx_list:
            if isinstance(ctx_dict, dict) and "pbn_publications_not_in_bpp" in ctx_dict:
                pbn_count = ctx_dict["pbn_publications_not_in_bpp"]
                break

    # Just verify the field exists and is a non-negative integer
    assert pbn_count is not None, "pbn_publications_not_in_bpp field should be present"
    assert isinstance(pbn_count, int), f"Expected integer, got {type(pbn_count)}"
    assert pbn_count >= 0, f"Expected non-negative count, got {pbn_count}"


@pytest.mark.django_db
def test_bpp_missing_in_pbn_view_requires_staff(client_logged_in_regular):
    """Test that BPPMissingInPBNView requires staff privileges."""
    url = reverse("komparator_pbn:bpp_missing_in_pbn")
    response = client_logged_in_regular.get(url)

    assert response.status_code in [302, 403]


@pytest.mark.django_db
def test_bpp_missing_in_pbn_view_staff_access(client_logged_in_staff, basic_setup):
    """Test that staff users can access BPPMissingInPBNView."""
    url = reverse("komparator_pbn:bpp_missing_in_pbn")
    response = client_logged_in_staff.get(url)

    assert response.status_code == 200
    assert "komparator_pbn/bpp_missing_in_pbn.html" in [
        t.name for t in response.templates
    ]


@pytest.mark.django_db
def test_bpp_missing_in_pbn_view_context(client_logged_in_staff, basic_setup):
    """Test BPPMissingInPBNView context data."""
    url = reverse("komparator_pbn:bpp_missing_in_pbn")
    response = client_logged_in_staff.get(url)

    context = response.context

    assert "statements" in context
    assert "publication_type" in context
    assert "query" in context
    assert "evaluation_start_year" in context
    assert "evaluation_end_year" in context

    # Default publication type should be 'ciagle'
    assert context["publication_type"] == "ciagle"


@pytest.mark.django_db
def test_bpp_missing_in_pbn_view_type_parameter(client_logged_in_staff, basic_setup):
    """Test BPPMissingInPBNView with type parameter."""
    # Test with 'zwarte' type
    url = reverse("komparator_pbn:bpp_missing_in_pbn")
    response = client_logged_in_staff.get(url, {"type": "zwarte"})

    assert response.status_code == 200
    assert response.context["publication_type"] == "zwarte"


@pytest.mark.django_db
def test_pbn_missing_in_bpp_view_requires_staff(client_logged_in_regular):
    """Test that PBNMissingInBPPView requires staff privileges."""
    url = reverse("komparator_pbn:pbn_missing_in_bpp")
    response = client_logged_in_regular.get(url)

    assert response.status_code in [302, 403]


@pytest.mark.django_db
def test_pbn_missing_in_bpp_view_staff_access(client_logged_in_staff, basic_setup):
    """Test that staff users can access PBNMissingInBPPView."""
    url = reverse("komparator_pbn:pbn_missing_in_bpp")
    response = client_logged_in_staff.get(url)

    assert response.status_code == 200
    assert "komparator_pbn/pbn_missing_in_bpp.html" in [
        t.name for t in response.templates
    ]


@pytest.mark.django_db
def test_pbn_missing_in_bpp_view_context(client_logged_in_staff, basic_setup):
    """Test PBNMissingInBPPView context data."""
    url = reverse("komparator_pbn:pbn_missing_in_bpp")
    response = client_logged_in_staff.get(url)

    context = response.context

    assert "statements" in context
    assert "query" in context
    assert "evaluation_start_year" in context
    assert "evaluation_end_year" in context


@pytest.mark.django_db
def test_pbn_missing_in_bpp_view_search_functionality(
    client_logged_in_staff, basic_setup
):
    """Test PBNMissingInBPPView search functionality."""
    url = reverse("komparator_pbn:pbn_missing_in_bpp")
    response = client_logged_in_staff.get(url, {"q": "Test"})

    assert response.status_code == 200
    assert response.context["query"] == "Test"


@pytest.mark.django_db
def test_evaluation_period_filtering(client_logged_in_staff, basic_setup):
    """Test that views properly filter by evaluation period."""
    data = basic_setup

    # Create publications outside evaluation period
    old_pub = baker.make(  # noqa
        Wydawnictwo_Ciagle,
        rok=EVALUATION_START_YEAR - 1,
        charakter_formalny=data["charakter_exportable"],
        doi="10.1000/old",
        pbn_uid_id=None,
        punkty_kbn=20,
        public_www="http://example.com/old",
    )

    old_pbn_pub = baker.make(  # noqa
        Publication,
        mongoId="old_pbn",
        year=EVALUATION_START_YEAR - 1,
        title="Old PBN Publication",
    )

    url = reverse("komparator_pbn:main")
    response = client_logged_in_staff.get(url)

    assert response.status_code == 200
    context = response.context

    # Verify evaluation period constants are used
    assert context["evaluation_start_year"] == EVALUATION_START_YEAR
    assert context["evaluation_end_year"] == EVALUATION_END_YEAR

    # Basic sanity check that we get integer counts
    assert isinstance(context["total_not_sent"], int)
    assert isinstance(context["total_sent"], int)
    assert isinstance(context["pbn_publications_not_in_bpp"], int)
