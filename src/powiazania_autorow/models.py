from django.db import models

from bpp.models import Autor


class AuthorConnection(models.Model):
    """
    Model representing connection between two authors based on shared publications.
    """

    primary_author = models.ForeignKey(
        Autor,
        on_delete=models.CASCADE,
        related_name="+",
        db_index=True,
        verbose_name="Autor główny",
    )
    secondary_author = models.ForeignKey(
        Autor,
        on_delete=models.CASCADE,
        related_name="+",
        db_index=True,
        verbose_name="Autor powiązany",
    )
    shared_publications_count = models.IntegerField(
        default=0,
        verbose_name="Liczba wspólnych publikacji",
        help_text="Liczba publikacji, w których obaj autorzy występują razem",
    )
    last_updated = models.DateTimeField(
        auto_now=True, verbose_name="Ostatnia aktualizacja"
    )

    class Meta:
        verbose_name = "Powiązanie autorów"
        verbose_name_plural = "Powiązania autorów"
        unique_together = [["primary_author", "secondary_author"]]
        indexes = [
            models.Index(fields=["shared_publications_count"]),
            models.Index(fields=["last_updated"]),
        ]
        ordering = ["-shared_publications_count"]

    def __str__(self):
        return f"{self.primary_author} <-> {self.secondary_author} ({self.shared_publications_count} publikacji)"
