from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import CASCADE, SET_NULL


class RozbieznoscDyscyplinPBN(models.Model):
    """
    Model przechowujący rozbieżności między dyscyplinami w BPP a oświadczeniami w PBN.
    Porównuje dyscypliny z Wydawnictwo_Ciagle_Autor lub Wydawnictwo_Zwarte_Autor
    z dyscyplinami w OswiadczenieInstytucji z PBN.
    """

    # GenericForeignKey do Wydawnictwo_Ciagle_Autor lub Wydawnictwo_Zwarte_Autor
    content_type = models.ForeignKey(
        ContentType,
        on_delete=CASCADE,
        limit_choices_to=models.Q(
            app_label="bpp",
            model__in=["wydawnictwo_ciagle_autor", "wydawnictwo_zwarte_autor"],
        ),
    )
    object_id = models.PositiveIntegerField()
    wydawnictwo_autor = GenericForeignKey("content_type", "object_id")

    # Odniesienie do oświadczenia PBN
    oswiadczenie_instytucji = models.ForeignKey(
        "pbn_api.OswiadczenieInstytucji",
        on_delete=CASCADE,
        related_name="rozbieznosci_dyscyplin",
    )

    # Przechowywanie dyscyplin do porównania
    dyscyplina_bpp = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        null=True,
        blank=True,
        on_delete=SET_NULL,
        related_name="rozbieznosci_bpp",
        verbose_name="Dyscyplina w BPP",
    )

    dyscyplina_pbn = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        null=True,
        blank=True,
        on_delete=SET_NULL,
        related_name="rozbieznosci_pbn",
        verbose_name="Dyscyplina w PBN",
    )

    # Metadane
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rozbieżność dyscyplin BPP-PBN"
        verbose_name_plural = "Rozbieżności dyscyplin BPP-PBN"
        unique_together = [["content_type", "object_id", "oswiadczenie_instytucji"]]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["oswiadczenie_instytucji"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        autor_str = ""
        publikacja_str = ""

        if self.wydawnictwo_autor:
            autor_str = str(self.wydawnictwo_autor.autor)
            publikacja_str = str(self.wydawnictwo_autor.rekord)

        return f"Rozbieżność: {autor_str} - {publikacja_str}"

    def get_wydawnictwo_autor(self):
        """Zwraca instancję Wydawnictwo_*_Autor."""
        return self.wydawnictwo_autor

    def get_autor(self):
        """Zwraca autora z rekordu wydawnictwo_autor."""
        if self.wydawnictwo_autor:
            return self.wydawnictwo_autor.autor
        return None

    def get_publikacja(self):
        """Zwraca publikację z rekordu wydawnictwo_autor."""
        if self.wydawnictwo_autor:
            return self.wydawnictwo_autor.rekord
        return None

    def get_jednostka(self):
        """Zwraca jednostkę z rekordu wydawnictwo_autor."""
        if self.wydawnictwo_autor:
            return self.wydawnictwo_autor.jednostka
        return None

    @property
    def dyscypliny_rozne(self):
        """Sprawdza czy dyscypliny są różne."""
        if self.dyscyplina_bpp_id is None and self.dyscyplina_pbn_id is None:
            return False
        return self.dyscyplina_bpp_id != self.dyscyplina_pbn_id
