"""Log zmian opłat za publikacje."""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

__all__ = ["OplatyPublikacjiLog", "log_oplaty_change"]


class OplatyPublikacjiLog(models.Model):
    """Log of fee-related changes to publications."""

    # GenericForeignKey to publication (Wydawnictwo_Ciagle or Wydawnictwo_Zwarte)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, verbose_name="Typ rekordu"
    )
    object_id = models.PositiveIntegerField(verbose_name="ID obiektu")
    publikacja = GenericForeignKey("content_type", "object_id")

    changed_at = models.DateTimeField(auto_now_add=True, verbose_name="Data zmiany")
    changed_by = models.CharField(
        max_length=100, verbose_name="Zmienione przez"
    )  # command name

    # Previous values
    prev_opl_pub_cost_free = models.BooleanField(
        null=True, blank=True, verbose_name="Poprz. bezkosztowa"
    )
    prev_opl_pub_research_potential = models.BooleanField(
        null=True, blank=True, verbose_name="Poprz. potencjał badawczy"
    )
    prev_opl_pub_research_or_development_projects = models.BooleanField(
        null=True, blank=True, verbose_name="Poprz. projekty badawcze"
    )
    prev_opl_pub_other = models.BooleanField(
        null=True, blank=True, verbose_name="Poprz. inne źródła"
    )
    prev_opl_pub_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Poprz. kwota",
    )

    # New values
    new_opl_pub_cost_free = models.BooleanField(
        null=True, blank=True, verbose_name="Nowa bezkosztowa"
    )
    new_opl_pub_research_potential = models.BooleanField(
        null=True, blank=True, verbose_name="Nowy potencjał badawczy"
    )
    new_opl_pub_research_or_development_projects = models.BooleanField(
        null=True, blank=True, verbose_name="Nowe projekty badawcze"
    )
    new_opl_pub_other = models.BooleanField(
        null=True, blank=True, verbose_name="Nowe inne źródła"
    )
    new_opl_pub_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Nowa kwota",
    )

    rok = models.PositiveIntegerField(null=True, blank=True, verbose_name="Rok")

    source_file = models.CharField(
        max_length=500, blank=True, verbose_name="Plik źródłowy"
    )
    source_row = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Wiersz w pliku"
    )

    class Meta:
        verbose_name = "Log zmian opłat za publikację"
        verbose_name_plural = "Logi zmian opłat za publikacje"
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["changed_at"]),
        ]

    def __str__(self):
        return f"{self.publikacja} - {self.changed_at} by {self.changed_by}"


def log_oplaty_change(
    publikacja, changed_by, source_file="", source_row=None, **new_values
):
    """Helper function to log fee changes.

    Args:
        publikacja: The publication object being modified.
        changed_by: Name of the command/process making the change.
        source_file: Optional filename for import commands.
        source_row: Optional row number for import commands.
        **new_values: New values for opl_ fields (e.g., new_opl_pub_cost_free=True).
    """
    ct = ContentType.objects.get_for_model(publikacja)

    OplatyPublikacjiLog.objects.create(
        content_type=ct,
        object_id=publikacja.pk,
        changed_by=changed_by,
        prev_opl_pub_cost_free=publikacja.opl_pub_cost_free,
        prev_opl_pub_research_potential=publikacja.opl_pub_research_potential,
        prev_opl_pub_research_or_development_projects=publikacja.opl_pub_research_or_development_projects,
        prev_opl_pub_other=publikacja.opl_pub_other,
        prev_opl_pub_amount=publikacja.opl_pub_amount,
        rok=getattr(publikacja, "rok", None),
        source_file=source_file,
        source_row=source_row,
        **new_values,
    )
