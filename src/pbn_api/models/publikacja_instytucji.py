from django.db import models
from django.db.models import JSONField


class PublikacjaInstytucji(models.Model):
    insPersonId = models.ForeignKey("pbn_api.Scientist", on_delete=models.CASCADE)
    institutionId = models.ForeignKey("pbn_api.Institution", on_delete=models.CASCADE)
    publicationId = models.ForeignKey("pbn_api.Publication", on_delete=models.CASCADE)
    # Multi-hosted (audyt uczelnia 2026-06-04): lustro danych PBN. FK nullable
    # ŚWIADOMIE — wiersz wiąże się z instytucją przez ``institutionId``
    # (== ``uczelnia.pbn_uid``), więc brak tagu uczelni to brak wygody
    # filtrowania, nie korupcja. Write-side tagowanie odłożone.
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="publikacje_instytucji",
    )
    publicationType = models.CharField(max_length=50, null=True, blank=True)  # noqa: DJ001
    userType = models.CharField(max_length=50, null=True, blank=True)  # noqa: DJ001
    publicationVersion = models.UUIDField(null=True, blank=True)
    publicationYear = models.PositiveSmallIntegerField(null=True, blank=True)
    snapshot = JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "Publikacja instytucji"
        verbose_name_plural = "Publikacje instytucji"


class PublikacjaInstytucji_V2(models.Model):
    """Jedyny sens istnienia tego obiektu jest taki, że PBN zamarzyło sobie
    używać UUID publikacji a nie MongoID publikacji przy wysyłaniu informacji
    o oświadczeniach instytucji.
    """

    # Multi-hosted (audyt uczelnia 2026-06-04): lustro danych PBN, FK nullable
    # świadomie — wiązanie z instytucją przez ``objectId``/PBN. Patrz
    # ``PublikacjaInstytucji.uczelnia``.
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="publikacje_instytucji_v2",
    )

    class Meta:
        verbose_name = "Publikacja instytucji V2"
        verbose_name_plural = "Publikacje instytucji V2"
        unique_together = ("uuid", "objectId")

    def __str__(self):
        return self.json_data.get("title")

    uuid = models.UUIDField(primary_key=True)  # noqa: DJ012
    # objectId powinno być realnie OneToOne, ale ja za cholerę nie wiem, czy PBN ma realnie to unikalne,
    # potem będzie się mój system wykrzaczał jeżeli oni mają zdublowane, więc:
    objectId = models.ForeignKey("pbn_api.Publication", on_delete=models.CASCADE)
    json_data = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def link_do_pi(self):
        pbn_uid_id = self.objectId_id

        uuid = self.json_data.get("uuid", None)
        if not uuid:
            return

        from bpp import const
        from bpp.models import Uczelnia

        # Multi-hosted: wiersz lustrzany nie ma requestu. Gdy brak własnego
        # taga uczelni, próbujemy JEDYNEJ w systemie (single → ona; 0/>1 →
        # None → link się nie wyrenderuje). NIE ma „uczelni domyślnej" i nie
        # zgadujemy pierwszej-z-brzegu (dawne ``Uczelnia.objects.get()``
        # wybuchało MultipleObjectsReturned przy >1 uczelni).
        uczelnia = self.uczelnia or Uczelnia.objects.get_single_uczelnia_or_none()
        if uczelnia is not None:
            return const.LINK_PI_ADD_STATEMENTS.format(
                pbn_api_root=uczelnia.pbn_api_root, pbn_uid_id=pbn_uid_id, uuid=uuid
            )
