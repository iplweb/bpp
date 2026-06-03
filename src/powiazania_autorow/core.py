"""
Core functionality for calculating author connections.
"""

import logging
from collections import defaultdict

from django.db import transaction

from bpp.models import Patent_Autor, Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

logger = logging.getLogger(__name__)


def calculate_author_connections():  # noqa: C901
    """
    Calculate and update all author connections based on shared publications.
    This function analyzes all publications and creates/updates AuthorConnection records.
    """
    from .models import AuthorConnection

    logger.info("Starting author connections calculation...")

    # Dictionary to store connections: {(author1_id, author2_id): count}
    connections = defaultdict(int)

    # Process Wydawnictwo_Ciagle (continuous publications)
    logger.info("Processing Wydawnictwo_Ciagle...")
    # Bez select_related — przy .values_list selektujemy tylko kolumny FK
    # z tabeli bazowej, więc join był martwy. .iterator() strumieniuje
    # wiersze zamiast ładować wszystkie do RAM naraz.
    ciagle_authors = Wydawnictwo_Ciagle_Autor.objects.values_list(
        "rekord_id", "autor_id"
    ).iterator(chunk_size=2000)

    # Group authors by publication
    publications_ciagle = defaultdict(list)
    for rekord_id, autor_id in ciagle_authors:
        if autor_id:  # Skip null authors
            publications_ciagle[rekord_id].append(autor_id)

    # Count connections
    for authors in publications_ciagle.values():
        if len(authors) > 1:
            for i in range(len(authors)):
                for j in range(i + 1, len(authors)):
                    # Always store with smaller ID first to avoid duplicates
                    author_pair = tuple(sorted([authors[i], authors[j]]))
                    connections[author_pair] += 1

    # Process Wydawnictwo_Zwarte (monographs)
    logger.info("Processing Wydawnictwo_Zwarte...")
    # Patrz wyżej — bez martwego select_related, ze strumieniowaniem.
    zwarte_authors = Wydawnictwo_Zwarte_Autor.objects.values_list(
        "rekord_id", "autor_id"
    ).iterator(chunk_size=2000)

    publications_zwarte = defaultdict(list)
    for rekord_id, autor_id in zwarte_authors:
        if autor_id:
            publications_zwarte[rekord_id].append(autor_id)

    for authors in publications_zwarte.values():
        if len(authors) > 1:
            for i in range(len(authors)):
                for j in range(i + 1, len(authors)):
                    author_pair = tuple(sorted([authors[i], authors[j]]))
                    connections[author_pair] += 1

    # Process Patents
    logger.info("Processing Patents...")
    # Patrz wyżej — bez martwego select_related, ze strumieniowaniem.
    patent_authors = Patent_Autor.objects.values_list("rekord_id", "autor_id").iterator(
        chunk_size=2000
    )

    publications_patent = defaultdict(list)
    for rekord_id, autor_id in patent_authors:
        if autor_id:
            publications_patent[rekord_id].append(autor_id)

    for authors in publications_patent.values():
        if len(authors) > 1:
            for i in range(len(authors)):
                for j in range(i + 1, len(authors)):
                    author_pair = tuple(sorted([authors[i], authors[j]]))
                    connections[author_pair] += 1

    logger.info(f"Found {len(connections)} author connections")

    # Update database
    with transaction.atomic():
        # Clear existing connections
        logger.info("Clearing existing connections...")
        AuthorConnection.objects.all().delete()

        # Create new connections
        logger.info("Creating new connections...")
        batch_size = 1000
        connections_to_create = []

        for (author1_id, author2_id), count in connections.items():
            if count > 0:  # Only create connections with at least 1 shared publication
                connections_to_create.append(
                    AuthorConnection(
                        primary_author_id=author1_id,
                        secondary_author_id=author2_id,
                        shared_publications_count=count,
                    )
                )

                if len(connections_to_create) >= batch_size:
                    AuthorConnection.objects.bulk_create(connections_to_create)
                    connections_to_create = []

        # Create remaining connections
        if connections_to_create:
            AuthorConnection.objects.bulk_create(connections_to_create)

    total_connections = AuthorConnection.objects.count()
    logger.info(
        f"Calculation complete. Created {total_connections} author connections."
    )
    return total_connections
