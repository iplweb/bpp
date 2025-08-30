from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(name="powiazania_autorow.calculate_author_connections")
def calculate_author_connections_task():
    """
    Celery task to calculate author connections in the background.
    This task can be scheduled to run periodically.
    """
    from .core import calculate_author_connections

    logger.info("Starting author connections calculation task...")

    try:
        total_connections = calculate_author_connections()
        logger.info(f"Successfully calculated {total_connections} author connections")
        return {"status": "success", "total_connections": total_connections}
    except Exception as e:
        logger.error(f"Error calculating author connections: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}


@shared_task(name="powiazania_autorow.update_single_author_connections")
def update_single_author_connections_task(author_id):
    """
    Update connections for a single author.
    Useful when an author's publications are modified.
    """
    from collections import defaultdict

    from django.db import transaction
    from django.db.models import Q

    from .models import AuthorConnection

    from bpp.models import (
        Autor,
        Patent_Autor,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )

    logger.info(f"Updating connections for author ID: {author_id}")

    try:
        # Get the author
        author = Autor.objects.get(pk=author_id)

        # Remove existing connections for this author
        AuthorConnection.objects.filter(
            Q(primary_author=author) | Q(secondary_author=author)
        ).delete()

        # Dictionary to store connections
        connections = defaultdict(int)

        # Find all publications for this author
        # Process Wydawnictwo_Ciagle
        ciagle_pubs = Wydawnictwo_Ciagle_Autor.objects.filter(autor=author).values_list(
            "rekord_id", flat=True
        )
        for pub_id in ciagle_pubs:
            coauthors = (
                Wydawnictwo_Ciagle_Autor.objects.filter(rekord_id=pub_id)
                .exclude(autor=author)
                .values_list("autor_id", flat=True)
            )

            for coauthor_id in coauthors:
                if coauthor_id:
                    connections[coauthor_id] += 1

        # Process Wydawnictwo_Zwarte
        zwarte_pubs = Wydawnictwo_Zwarte_Autor.objects.filter(autor=author).values_list(
            "rekord_id", flat=True
        )
        for pub_id in zwarte_pubs:
            coauthors = (
                Wydawnictwo_Zwarte_Autor.objects.filter(rekord_id=pub_id)
                .exclude(autor=author)
                .values_list("autor_id", flat=True)
            )

            for coauthor_id in coauthors:
                if coauthor_id:
                    connections[coauthor_id] += 1

        # Process Patents
        patent_pubs = Patent_Autor.objects.filter(autor=author).values_list(
            "rekord_id", flat=True
        )
        for pub_id in patent_pubs:
            coauthors = (
                Patent_Autor.objects.filter(rekord_id=pub_id)
                .exclude(autor=author)
                .values_list("autor_id", flat=True)
            )

            for coauthor_id in coauthors:
                if coauthor_id:
                    connections[coauthor_id] += 1

        # Create new connections
        with transaction.atomic():
            connections_to_create = []
            for coauthor_id, count in connections.items():
                if count > 0:
                    # Determine primary and secondary (smaller ID is primary)
                    if author_id < coauthor_id:
                        primary_id, secondary_id = author_id, coauthor_id
                    else:
                        primary_id, secondary_id = coauthor_id, author_id

                    connections_to_create.append(
                        AuthorConnection(
                            primary_author_id=primary_id,
                            secondary_author_id=secondary_id,
                            shared_publications_count=count,
                        )
                    )

            AuthorConnection.objects.bulk_create(
                connections_to_create, ignore_conflicts=True
            )

        logger.info(f"Updated {len(connections)} connections for author {author}")
        return {
            "status": "success",
            "author_id": author_id,
            "connections_updated": len(connections),
        }

    except Autor.DoesNotExist:
        logger.error(f"Author with ID {author_id} not found")
        return {"status": "error", "error": f"Author with ID {author_id} not found"}
    except Exception as e:
        logger.error(
            f"Error updating connections for author {author_id}: {str(e)}",
            exc_info=True,
        )
        return {"status": "error", "error": str(e)}
