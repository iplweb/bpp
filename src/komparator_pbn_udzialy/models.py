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


class BrakAutoraWPublikacji(models.Model):
    """
    Model przechowujący przypadki, gdzie w PBN jest oświadczenie dla autora,
    ale w BPP nie znaleziono odpowiedniego powiązania autora z publikacją.
    """

    # Stałe dla typów problemów
    TYP_BRAK_AUTORA_W_BPP = "brak_autora"
    TYP_BRAK_POWIAZANIA = "brak_powiazania"
    TYP_BRAK_PUBLIKACJI = "brak_publikacji"

    TYP_CHOICES = [
        (TYP_BRAK_AUTORA_W_BPP, "Autor nie istnieje w BPP"),
        (TYP_BRAK_POWIAZANIA, "Autor nie jest powiązany z publikacją"),
        (TYP_BRAK_PUBLIKACJI, "Publikacja nie istnieje w BPP"),
    ]

    # Oświadczenie PBN, które spowodowało wykrycie problemu
    oswiadczenie_instytucji = models.ForeignKey(
        "pbn_api.OswiadczenieInstytucji",
        on_delete=CASCADE,
        related_name="brakujace_autorzy",
    )

    # Naukowiec z PBN
    pbn_scientist = models.ForeignKey(
        "pbn_api.Scientist",
        on_delete=CASCADE,
        related_name="brakujace_powiazania_bpp",
    )

    # Autor w BPP (jeśli został znaleziony)
    autor = models.ForeignKey(
        "bpp.Autor",
        null=True,
        blank=True,
        on_delete=CASCADE,
        related_name="brakujace_powiazania_pbn",
    )

    # GenericForeignKey do publikacji (jeśli została znaleziona)
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=CASCADE,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    publikacja = GenericForeignKey("content_type", "object_id")

    # Typ problemu
    typ = models.CharField(max_length=20, choices=TYP_CHOICES)

    # Dyscyplina z PBN
    dyscyplina_pbn = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        null=True,
        blank=True,
        on_delete=SET_NULL,
        related_name="brakujacy_autorzy_pbn",
    )

    # Metadane
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Brak autora w publikacji"
        verbose_name_plural = "Brakujący autorzy w publikacjach"
        unique_together = [["oswiadczenie_instytucji"]]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["typ"]),
            models.Index(fields=["autor"]),
            models.Index(fields=["pbn_scientist"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        osw = self.oswiadczenie_instytucji
        scientist_name = str(self.pbn_scientist) if self.pbn_scientist else "?"
        pub_title = osw.publicationId.title[:50] if osw.publicationId else "?"
        typ_display = self.get_typ_display()
        return f"{typ_display}: {scientist_name} - '{pub_title}...'"

    def get_typ_display_css_class(self):
        """Zwraca klasę CSS dla typu."""
        return {
            "brak_autora": "alert",
            "brak_powiazania": "warning",
            "brak_publikacji": "secondary",
        }.get(self.typ, "")


class ProblemWrapper:
    """Wrapper zapewniający jednolity interfejs dla problemów PBN.

    Pozwala wyświetlać RozbieznoscDyscyplinPBN i BrakAutoraWPublikacji
    w jednej tabeli z jednolitym interfejsem.
    """

    TYP_ROZNE_DYSCYPLINY = "rozne_dyscypliny"

    def __init__(self, obj):
        self.obj = obj
        self.is_discrepancy = isinstance(obj, RozbieznoscDyscyplinPBN)

    @property
    def pk(self):
        return self.obj.pk

    @property
    def typ(self):
        if self.is_discrepancy:
            return self.TYP_ROZNE_DYSCYPLINY
        return self.obj.typ

    @property
    def typ_display(self):
        if self.is_discrepancy:
            return "Różne dyscypliny"
        return self.obj.get_typ_display()

    @property
    def typ_css_class(self):
        return {
            self.TYP_ROZNE_DYSCYPLINY: "info",
            BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP: "alert",
            BrakAutoraWPublikacji.TYP_BRAK_POWIAZANIA: "warning",
            BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI: "secondary",
        }.get(self.typ, "")

    @property
    def autor_display(self):
        if self.is_discrepancy:
            autor = self.obj.get_autor()
            return str(autor) if autor else None
        scientist = self.obj.pbn_scientist
        if scientist:
            return f"{scientist.name} {scientist.lastName} [PBN]"
        return None

    @property
    def publikacja_display(self):
        if self.is_discrepancy:
            pub = self.obj.get_publikacja()
            return str(pub)[:50] if pub else None
        osw = self.obj.oswiadczenie_instytucji
        if osw and osw.publicationId:
            return osw.publicationId.title[:50] if osw.publicationId.title else None
        return None

    @property
    def rok(self):
        if self.is_discrepancy:
            osw = self.obj.oswiadczenie_instytucji
            if osw and osw.publicationId:
                return osw.publicationId.year
            return None
        osw = self.obj.oswiadczenie_instytucji
        if osw and osw.publicationId:
            return osw.publicationId.year
        return None

    @property
    def dyscyplina_bpp(self):
        if self.is_discrepancy:
            return self.obj.dyscyplina_bpp
        return None  # Brakujący nie mają dyscypliny BPP

    @property
    def dyscyplina_pbn(self):
        if self.is_discrepancy:
            return self.obj.dyscyplina_pbn
        return self.obj.dyscyplina_pbn

    @property
    def created_at(self):
        return self.obj.created_at

    @property
    def detail_url_name(self):
        if self.is_discrepancy:
            return "komparator_pbn_udzialy:detail"
        return "komparator_pbn_udzialy:missing_autor_detail"
