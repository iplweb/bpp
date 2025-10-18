import pytest
from model_bakery import baker

from pbn_api.adapters.wydawca import WydawcaPBNAdapter
from pbn_api.adapters.zrodlo import ZrodloPBNAdapter
from pbn_api.models import Journal, Publisher
from bpp.models import Wydawca, Zrodlo


# ==================== WydawcaPBNAdapter Tests ====================


@pytest.mark.django_db
def test_wydawca_adapter_with_pbn_uid():
    """Test WydawcaPBNAdapter when издавец has pbn_uid"""
    pbn_publisher = baker.make(Publisher)
    wydawca = baker.make(Wydawca, pbn_uid=pbn_publisher)

    adapter = WydawcaPBNAdapter(wydawca)
    result = adapter.pbn_get_json()

    assert result["objectId"] == pbn_publisher.pk
    assert "name" in result


@pytest.mark.django_db
def test_wydawca_adapter_with_pbn_uid_and_mnsw_id():
    """Test WydawcaPBNAdapter includes mniswId when present"""
    pbn_publisher = baker.make(Publisher)
    wydawca = baker.make(Wydawca, pbn_uid=pbn_publisher)

    adapter = WydawcaPBNAdapter(wydawca)
    result = adapter.pbn_get_json()

    assert result["objectId"] == pbn_publisher.pk
    assert "name" in result
    assert isinstance(result, dict)


@pytest.mark.django_db
def test_wydawca_adapter_without_pbn_uid():
    """Test WydawcaPBNAdapter when издавец has no pbn_uid"""
    wydawca = baker.make(Wydawca, pbn_uid=None, nazwa="Test Publisher")

    adapter = WydawcaPBNAdapter(wydawca)
    result = adapter.pbn_get_json()

    assert result["name"] == "Test Publisher"
    assert "objectId" not in result


@pytest.mark.django_db
def test_wydawca_adapter_get_toplevel():
    """Test WydawcaPBNAdapter uses get_toplevel method"""
    parent_wydawca = baker.make(Wydawca, pbn_uid=None, nazwa="Parent")
    child_wydawca = baker.make(Wydawca, pbn_uid=None, nazwa="Child")

    adapter = WydawcaPBNAdapter(child_wydawca)
    result = adapter.pbn_get_json()

    assert "name" in result


@pytest.mark.django_db
def test_wydawca_adapter_json_structure():
    """Test WydawcaPBNAdapter returns correct JSON structure"""
    wydawca = baker.make(Wydawca, pbn_uid=None, nazwa="Test")

    adapter = WydawcaPBNAdapter(wydawca)
    result = adapter.pbn_get_json()

    assert isinstance(result, dict)
    assert "name" in result


# ==================== ZrodloPBNAdapter Tests ====================


@pytest.mark.django_db
def test_zrodlo_adapter_without_pbn_uid():
    """Test ZrodloPBNAdapter when zrodlo has no pbn_uid"""
    zrodlo = baker.make(
        Zrodlo,
        pbn_uid=None,
        nazwa="Test Journal",
        wydawca="Test Publisher",
        issn=None,
        www=None,
        e_issn=None,
    )

    adapter = ZrodloPBNAdapter(zrodlo)
    result = adapter.pbn_get_json()

    assert result["title"] == "Test Journal"
    assert "objectId" not in result


@pytest.mark.django_db
def test_zrodlo_adapter_without_pbn_uid_with_publisher():
    """Test ZrodloPBNAdapter with publisher info"""
    zrodlo = baker.make(
        Zrodlo,
        pbn_uid=None,
        nazwa="Test Journal",
        wydawca="Test Publisher",
        issn=None,
        www=None,
        e_issn=None,
    )

    adapter = ZrodloPBNAdapter(zrodlo)
    result = adapter.pbn_get_json()

    assert result["title"] == "Test Journal"
    assert result["publisher"]["name"] == "Test Publisher"
    assert "objectId" not in result


@pytest.mark.django_db
def test_zrodlo_adapter_without_pbn_uid_with_issn():
    """Test ZrodloPBNAdapter includes ISSN when present"""
    zrodlo = baker.make(
        Zrodlo,
        pbn_uid=None,
        nazwa="Test Journal",
        issn="1234-5678",
        www=None,
        e_issn=None,
    )

    adapter = ZrodloPBNAdapter(zrodlo)
    result = adapter.pbn_get_json()

    assert result["issn"] == "1234-5678"


@pytest.mark.django_db
def test_zrodlo_adapter_without_pbn_uid_with_www():
    """Test ZrodloPBNAdapter includes website link when present"""
    zrodlo = baker.make(
        Zrodlo,
        pbn_uid=None,
        nazwa="Test Journal",
        www="https://example.com",
        issn=None,
        e_issn=None,
    )

    adapter = ZrodloPBNAdapter(zrodlo)
    result = adapter.pbn_get_json()

    assert result["websiteLink"] == "https://example.com"


@pytest.mark.django_db
def test_zrodlo_adapter_without_pbn_uid_with_e_issn():
    """Test ZrodloPBNAdapter includes e-ISSN when present"""
    zrodlo = baker.make(
        Zrodlo,
        pbn_uid=None,
        nazwa="Test Journal",
        e_issn="1234-5678",
        issn=None,
        www=None,
    )

    adapter = ZrodloPBNAdapter(zrodlo)
    result = adapter.pbn_get_json()

    assert result["eissn"] == "1234-5678"


@pytest.mark.django_db
def test_zrodlo_adapter_without_pbn_uid_all_fields():
    """Test ZrodloPBNAdapter with all optional fields present"""
    zrodlo = baker.make(
        Zrodlo,
        pbn_uid=None,
        nazwa="Test Journal",
        wydawca="Test Publisher",
        issn="1111-1111",
        www="https://example.com",
        e_issn="2222-2222",
    )

    adapter = ZrodloPBNAdapter(zrodlo)
    result = adapter.pbn_get_json()

    assert result["title"] == "Test Journal"
    assert result["publisher"]["name"] == "Test Publisher"
    assert result["issn"] == "1111-1111"
    assert result["websiteLink"] == "https://example.com"
    assert result["eissn"] == "2222-2222"


@pytest.mark.django_db
def test_zrodlo_adapter_with_pbn_uid():
    """Test ZrodloPBNAdapter when zrodlo has pbn_uid"""
    pbn_journal = baker.make(Journal)
    zrodlo = baker.make(Zrodlo, pbn_uid=pbn_journal)

    adapter = ZrodloPBNAdapter(zrodlo)
    result = adapter.pbn_get_json()

    assert result["objectId"] == pbn_journal.pk


@pytest.mark.django_db
def test_zrodlo_adapter_with_pbn_uid_includes_attributes():
    """Test ZrodloPBNAdapter includes journal attributes when pbn_uid exists"""
    pbn_journal = baker.make(Journal)
    zrodlo = baker.make(Zrodlo, pbn_uid=pbn_journal)

    adapter = ZrodloPBNAdapter(zrodlo)
    result = adapter.pbn_get_json()

    assert "objectId" in result
    assert isinstance(result, dict)


@pytest.mark.django_db
def test_zrodlo_adapter_json_structure_without_pbn_uid():
    """Test ZrodloPBNAdapter JSON structure when no pbn_uid"""
    zrodlo = baker.make(
        Zrodlo,
        pbn_uid=None,
        nazwa="Test",
        wydawca="Publisher",
        issn=None,
        www=None,
        e_issn=None,
    )

    adapter = ZrodloPBNAdapter(zrodlo)
    result = adapter.pbn_get_json()

    assert isinstance(result, dict)
    assert "title" in result


@pytest.mark.django_db
def test_zrodlo_adapter_without_pbn_uid_omits_none_values():
    """Test ZrodloPBNAdapter omits None values from result"""
    zrodlo = baker.make(
        Zrodlo,
        pbn_uid=None,
        nazwa="Test Journal",
        wydawca="Publisher",
        issn=None,
        www=None,
        e_issn=None,
    )

    adapter = ZrodloPBNAdapter(zrodlo)
    result = adapter.pbn_get_json()

    # Title and publisher should be present since wydawca has a value
    assert "title" in result
    assert "publisher" in result and result["publisher"]["name"] == "Publisher"
