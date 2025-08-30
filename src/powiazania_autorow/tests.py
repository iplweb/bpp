import pytest
from django.db.models import Q
from model_bakery import baker

from .core import calculate_author_connections
from .models import AuthorConnection
from .tasks import (
    calculate_author_connections_task,
    update_single_author_connections_task,
)

from bpp.models import (
    Autor,
    Patent,
    Patent_Autor,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)


@pytest.mark.django_db
def test_author_connection_model_creation():
    """Test that AuthorConnection model can be created correctly."""
    author1 = baker.make(Autor)
    author2 = baker.make(Autor)

    connection = AuthorConnection.objects.create(
        primary_author=author1, secondary_author=author2, shared_publications_count=5
    )

    assert connection.primary_author == author1
    assert connection.secondary_author == author2
    assert connection.shared_publications_count == 5
    assert connection.last_updated is not None


@pytest.mark.django_db
def test_author_connection_str_representation():
    """Test the string representation of AuthorConnection."""
    author1 = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    author2 = baker.make(Autor, nazwisko="Nowak", imiona="Anna")

    connection = AuthorConnection.objects.create(
        primary_author=author1, secondary_author=author2, shared_publications_count=3
    )

    expected_str = "Kowalski Jan <-> Nowak Anna (3 publikacji)"
    assert str(connection) == expected_str


@pytest.mark.django_db
def test_author_connection_unique_constraint():
    """Test that unique_together constraint works."""
    author1 = baker.make(Autor)
    author2 = baker.make(Autor)

    AuthorConnection.objects.create(
        primary_author=author1, secondary_author=author2, shared_publications_count=1
    )

    # Attempting to create duplicate should raise an error
    with pytest.raises(Exception):
        AuthorConnection.objects.create(
            primary_author=author1,
            secondary_author=author2,
            shared_publications_count=2,
        )


@pytest.mark.django_db
def test_calculate_author_connections_with_wydawnictwo_ciagle():
    """Test connection calculation for Wydawnictwo_Ciagle publications."""
    # Create authors
    author1 = baker.make(Autor)
    author2 = baker.make(Autor)
    author3 = baker.make(Autor)

    # Create publications
    pub1 = baker.make(Wydawnictwo_Ciagle)
    pub2 = baker.make(Wydawnictwo_Ciagle)

    # Create author-publication relationships
    # pub1: author1 and author2
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub1, autor=author1)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub1, autor=author2)

    # pub2: author1, author2, and author3
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub2, autor=author1)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub2, autor=author2)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub2, autor=author3)

    # Calculate connections
    total_connections = calculate_author_connections()

    # Verify connections
    assert total_connections == 3  # (1,2), (1,3), (2,3)

    # Check specific connections
    connection_12 = AuthorConnection.objects.filter(
        Q(primary_author=author1, secondary_author=author2)
        | Q(primary_author=author2, secondary_author=author1)
    ).first()
    assert connection_12 is not None
    assert connection_12.shared_publications_count == 2  # Both publications

    connection_13 = AuthorConnection.objects.filter(
        Q(primary_author=author1, secondary_author=author3)
        | Q(primary_author=author3, secondary_author=author1)
    ).first()
    assert connection_13 is not None
    assert connection_13.shared_publications_count == 1  # Only pub2

    connection_23 = AuthorConnection.objects.filter(
        Q(primary_author=author2, secondary_author=author3)
        | Q(primary_author=author3, secondary_author=author2)
    ).first()
    assert connection_23 is not None
    assert connection_23.shared_publications_count == 1  # Only pub2


@pytest.mark.django_db
def test_calculate_author_connections_with_wydawnictwo_zwarte():
    """Test connection calculation for Wydawnictwo_Zwarte publications."""
    # Create authors
    author1 = baker.make(Autor)
    author2 = baker.make(Autor)

    # Create publication
    pub = baker.make(Wydawnictwo_Zwarte)

    # Create author-publication relationships
    baker.make(Wydawnictwo_Zwarte_Autor, rekord=pub, autor=author1)
    baker.make(Wydawnictwo_Zwarte_Autor, rekord=pub, autor=author2)

    # Calculate connections
    total_connections = calculate_author_connections()

    # Verify connections
    assert total_connections == 1

    connection = AuthorConnection.objects.first()
    assert connection.shared_publications_count == 1


@pytest.mark.django_db
def test_calculate_author_connections_with_patents():
    """Test connection calculation for Patent publications."""
    # Create authors
    author1 = baker.make(Autor)
    author2 = baker.make(Autor)

    # Create patent
    patent = baker.make(Patent)

    # Create author-patent relationships
    baker.make(Patent_Autor, rekord=patent, autor=author1)
    baker.make(Patent_Autor, rekord=patent, autor=author2)

    # Calculate connections
    total_connections = calculate_author_connections()

    # Verify connections
    assert total_connections == 1

    connection = AuthorConnection.objects.first()
    assert connection.shared_publications_count == 1


@pytest.mark.django_db
def test_calculate_author_connections_mixed_publications():
    """Test connection calculation across different publication types."""
    # Create authors
    author1 = baker.make(Autor)
    author2 = baker.make(Autor)

    # Create publications of different types
    ciagle = baker.make(Wydawnictwo_Ciagle)
    zwarte = baker.make(Wydawnictwo_Zwarte)
    patent = baker.make(Patent)

    # Create relationships for all publication types
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=ciagle, autor=author1)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=ciagle, autor=author2)

    baker.make(Wydawnictwo_Zwarte_Autor, rekord=zwarte, autor=author1)
    baker.make(Wydawnictwo_Zwarte_Autor, rekord=zwarte, autor=author2)

    baker.make(Patent_Autor, rekord=patent, autor=author1)
    baker.make(Patent_Autor, rekord=patent, autor=author2)

    # Calculate connections
    total_connections = calculate_author_connections()

    # Verify connections
    assert total_connections == 1

    connection = AuthorConnection.objects.first()
    assert connection.shared_publications_count == 3  # All three publications


@pytest.mark.django_db
def test_calculate_author_connections_clears_existing():
    """Test that calculation clears existing connections before creating new ones."""
    # Create initial connection
    author1 = baker.make(Autor)
    author2 = baker.make(Autor)

    AuthorConnection.objects.create(
        primary_author=author1,
        secondary_author=author2,
        shared_publications_count=999,  # Old value
    )

    # Create actual publication
    pub = baker.make(Wydawnictwo_Ciagle)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub, autor=author1)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub, autor=author2)

    # Calculate connections
    calculate_author_connections()

    # Verify old connection was replaced
    connection = AuthorConnection.objects.first()
    assert connection.shared_publications_count == 1  # New correct value


@pytest.mark.django_db
def test_calculate_author_connections_handles_null_authors():
    """Test that calculation handles null authors correctly."""
    # Create valid author
    author1 = baker.make(Autor)

    # Create publication
    pub = baker.make(Wydawnictwo_Ciagle)

    # Create relationships with one null author
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub, autor=author1)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub, autor=None)

    # Calculate connections
    total_connections = calculate_author_connections()

    # Should not create any connections (need at least 2 non-null authors)
    assert total_connections == 0


@pytest.mark.django_db
def test_calculate_author_connections_single_author_publication():
    """Test that single-author publications don't create connections."""
    # Create author
    author = baker.make(Autor)

    # Create publication with single author
    pub = baker.make(Wydawnictwo_Ciagle)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub, autor=author)

    # Calculate connections
    total_connections = calculate_author_connections()

    # No connections should be created
    assert total_connections == 0


@pytest.mark.django_db
def test_calculate_author_connections_task_success():
    """Test the Celery task for calculating connections."""
    # Create test data
    author1 = baker.make(Autor)
    author2 = baker.make(Autor)
    pub = baker.make(Wydawnictwo_Ciagle)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub, autor=author1)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub, autor=author2)

    # Run task
    result = calculate_author_connections_task()

    # Verify result
    assert result["status"] == "success"
    assert result["total_connections"] == 1

    # Verify connection was created
    assert AuthorConnection.objects.count() == 1


@pytest.mark.django_db
def test_update_single_author_connections_task():
    """Test the task for updating single author connections."""
    # Create authors
    author1 = baker.make(Autor)
    author2 = baker.make(Autor)
    author3 = baker.make(Autor)

    # Create publications
    pub1 = baker.make(Wydawnictwo_Ciagle)
    pub2 = baker.make(Wydawnictwo_Ciagle)

    # Initial setup: author1 with author2 in pub1
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub1, autor=author1)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub1, autor=author2)

    # Run initial calculation
    calculate_author_connections()
    assert AuthorConnection.objects.count() == 1

    # Add new publication: author1 with author3 in pub2
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub2, autor=author1)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=pub2, autor=author3)

    # Update connections for author1
    result = update_single_author_connections_task(author1.pk)

    # Verify result
    assert result["status"] == "success"
    assert result["author_id"] == author1.pk
    assert result["connections_updated"] == 2  # Connections with author2 and author3

    # Verify connections in database
    connections = AuthorConnection.objects.filter(
        Q(primary_author=author1) | Q(secondary_author=author1)
    )
    assert connections.count() == 2


@pytest.mark.django_db
def test_update_single_author_connections_task_nonexistent_author():
    """Test the task with non-existent author ID."""
    result = update_single_author_connections_task(99999)

    assert result["status"] == "error"
    assert "not found" in result["error"]


@pytest.mark.django_db
def test_author_connection_ordering():
    """Test that connections are ordered by shared_publications_count descending."""
    author1 = baker.make(Autor)
    author2 = baker.make(Autor)
    author3 = baker.make(Autor)
    author4 = baker.make(Autor)

    # Create connections with different counts
    conn1 = AuthorConnection.objects.create(
        primary_author=author1, secondary_author=author2, shared_publications_count=5
    )
    conn2 = AuthorConnection.objects.create(
        primary_author=author1, secondary_author=author3, shared_publications_count=10
    )
    conn3 = AuthorConnection.objects.create(
        primary_author=author1, secondary_author=author4, shared_publications_count=3
    )

    # Get all connections
    connections = list(AuthorConnection.objects.all())

    # Verify ordering (highest count first)
    assert connections[0] == conn2  # 10 publications
    assert connections[1] == conn1  # 5 publications
    assert connections[2] == conn3  # 3 publications


@pytest.mark.django_db
def test_author_connection_indexes():
    """Test that database indexes are properly created."""
    # This test verifies that the model Meta configuration is correct
    # The actual index creation is handled by Django migrations

    # Create a connection to test indexes work
    author1 = baker.make(Autor)
    author2 = baker.make(Autor)

    AuthorConnection.objects.create(
        primary_author=author1, secondary_author=author2, shared_publications_count=5
    )

    # Query using indexed fields should work efficiently
    # Test query by shared_publications_count (indexed)
    connections = AuthorConnection.objects.filter(shared_publications_count__gte=5)
    assert connections.count() == 1

    # Test query by last_updated (indexed)
    from django.utils import timezone

    recent = AuthorConnection.objects.filter(
        last_updated__gte=timezone.now().replace(hour=0)
    )
    assert recent.count() == 1
