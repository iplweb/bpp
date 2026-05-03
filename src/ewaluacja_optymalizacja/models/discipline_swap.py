"""Model przechowujący wyniki analizy możliwości zamiany dyscyplin.

Identyfikuje publikacje, dla których zamiana dyscypliny autora (z głównej na
subdyscyplinę lub odwrotnie) zwiększa całkowitą punktację publikacji.
"""

from django.db import models

from bpp.models import Autor
from bpp.models.fields import TupleField


class DisciplineSwapOpportunity(models.Model):
    """
    Przechowuje wyniki analizy możliwości zamiany dyscyplin.

    Identyfikuje publikacje gdzie:
    - Autor ma przypisane dwie dyscypliny (dyscyplina + subdyscyplina) w Autor_Dyscyplina
    - Zamiana dyscypliny z głównej na subdyscyplinę (lub odwrotnie) zwiększa punktację
    """

    # Metadane
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Data utworzenia analizy"
    )

    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.CASCADE,
        verbose_name="Uczelnia",
    )

    # Informacje o publikacji
    rekord_id = TupleField(
        models.IntegerField(),
        size=2,
        db_index=True,
        verbose_name="ID rekordu (content_type_id, object_id)",
    )

    rekord_tytul = models.TextField(
        verbose_name="Tytuł pracy", help_text="Cache tytułu do wyświetlania"
    )

    rekord_rok = models.PositiveSmallIntegerField(
        verbose_name="Rok publikacji",
        null=True,
        blank=True,
    )

    rekord_typ = models.CharField(
        max_length=50,
        verbose_name="Typ publikacji",
        help_text="Ciagle/Zwarte",
        default="",
    )

    # Autor do zamiany dyscypliny
    autor = models.ForeignKey(
        Autor,
        on_delete=models.CASCADE,
        related_name="discipline_swap_opportunities",
        verbose_name="Autor do zamiany dyscypliny",
    )

    # Dyscypliny - obecna i docelowa
    current_discipline = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        on_delete=models.CASCADE,
        related_name="swap_from",
        verbose_name="Obecna dyscyplina",
    )

    target_discipline = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        on_delete=models.CASCADE,
        related_name="swap_to",
        verbose_name="Docelowa dyscyplina",
    )

    # Punktacja przed i po zamianie
    points_before = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name="Punkty przed zamianą",
        help_text="Całkowita punktacja publikacji przed zamianą dyscypliny",
    )

    points_after = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name="Punkty po zamianie",
        help_text="Całkowita punktacja publikacji po zamianie dyscypliny",
    )

    point_improvement = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name="Poprawa punktów",
        help_text="points_after - points_before",
    )

    # Dla Wydawnictwo_Ciagle: czy docelowa dyscyplina pasuje do dyscyplin źródła
    zrodlo_discipline_match = models.BooleanField(
        default=False,
        verbose_name="Dyscyplina pasuje do źródła",
        help_text=(
            "True jeśli docelowa dyscyplina jest w Dyscyplina_Zrodla "
            "dla tego źródła i roku"
        ),
    )

    # Wynik analizy
    makes_sense = models.BooleanField(
        default=False,
        verbose_name="Czy zamiana ma sens",
        help_text="True jeśli zamiana zwiększa całkowitą punktację",
    )

    class Meta:
        app_label = "ewaluacja_optymalizacja"
        verbose_name = "Możliwość zamiany dyscypliny"
        verbose_name_plural = "Możliwości zamiany dyscyplin"
        ordering = ["-makes_sense", "-point_improvement", "rekord_tytul"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["uczelnia"]),
            models.Index(fields=["makes_sense"]),
            models.Index(fields=["-point_improvement"]),
            models.Index(fields=["current_discipline"]),
            models.Index(fields=["target_discipline"]),
            models.Index(fields=["zrodlo_discipline_match"]),
            models.Index(fields=["rekord_rok"]),
        ]

    def __str__(self):
        return (
            f"{self.rekord_tytul[:50]}... - "
            f"{self.autor}: {self.current_discipline} -> {self.target_discipline} "
            f"(+{self.point_improvement})"
        )

    @property
    def rekord(self):
        """Pobierz obiekt Rekord dla tej publikacji."""
        if hasattr(self, "_cached_rekord") and self._cached_rekord is not None:
            return self._cached_rekord
        from bpp.models import Rekord

        return Rekord.objects.get(pk=self.rekord_id)
