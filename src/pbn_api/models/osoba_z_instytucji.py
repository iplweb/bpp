from django.db import models


class OsobaZInstytucji(models.Model):
    personId = models.OneToOneField(
        "pbn_api.Scientist", on_delete=models.PROTECT, db_index=True
    )
    firstName = models.TextField()
    lastName = models.TextField()
    institutionId = models.ForeignKey("pbn_api.Institution", on_delete=models.PROTECT)
    # Multi-hosted (audyt uczelnia 2026-06-04): to lustro danych PBN. FK
    # ``uczelnia`` jest nullable ŚWIADOMIE — wiersz i tak jest jednoznacznie
    # związany z instytucją PBN przez ``institutionId`` (odpowiednik uczelni
    # w PBN, == ``uczelnia.pbn_uid``), więc brak twardego tagu uczelni to
    # brak wygody filtrowania, NIE korupcja danych. Pełne per-uczelnia
    # tagowanie write-side odłożone (integrator nie wpisuje tu uczelni).
    # UWAGA: ``personId`` jest OneToOne — w multi-hosted ostatnia uczelnia
    # nadpisuje wiersz (konflikt strukturalny do rozważenia osobno).
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="osoby_z_instytucji",
    )
    institutionName = models.TextField()
    title = models.TextField(blank=True, default="")
    polonUuid = models.UUIDField(unique=True)
    phdStudent = models.BooleanField()
    _from = models.DateField(null=True, blank=True)
    _to = models.DateField(null=True, blank=True)

    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.personId_id} {self.firstName} {self.lastName}"
