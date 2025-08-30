"""
Core functionality for calculating author connections.
"""

from collections import defaultdict

from django.db import transaction

from bpp.models import Patent_Autor, Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor


def calculate_author_connections():
    """
    Calculate and update all author connections based on shared publications.
    This function analyzes all publications and creates/updates AuthorConnection records.
    """
    from .models import AuthorConnection

    print("Starting author connections calculation...")

    # Dictionary to store connections: {(author1_id, author2_id): count}
    connections = defaultdict(int)

    # Process Wydawnictwo_Ciagle (continuous publications)
    print("Processing Wydawnictwo_Ciagle...")
    ciagle_authors = Wydawnictwo_Ciagle_Autor.objects.select_related(
        "autor", "rekord"
    ).values_list("rekord_id", "autor_id")

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
    print("Processing Wydawnictwo_Zwarte...")
    zwarte_authors = Wydawnictwo_Zwarte_Autor.objects.select_related(
        "autor", "rekord"
    ).values_list("rekord_id", "autor_id")

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
    print("Processing Patents...")
    patent_authors = Patent_Autor.objects.select_related("autor", "rekord").values_list(
        "rekord_id", "autor_id"
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

    print(f"Found {len(connections)} author connections")

    # Update database
    with transaction.atomic():
        # Clear existing connections
        print("Clearing existing connections...")
        AuthorConnection.objects.all().delete()

        # Create new connections
        print("Creating new connections...")
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
    print(f"Calculation complete. Created {total_connections} author connections.")
    return total_connections
