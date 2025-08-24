from django.db import models
from django.db.models import JSONField


class PublikacjaInstytucji(models.Model):
    insPersonId = models.ForeignKey("pbn_api.Scientist", on_delete=models.CASCADE)
    institutionId = models.ForeignKey("pbn_api.Institution", on_delete=models.CASCADE)
    publicationId = models.ForeignKey("pbn_api.Publication", on_delete=models.CASCADE)
    publicationType = models.CharField(max_length=50, null=True, blank=True)
    userType = models.CharField(max_length=50, null=True, blank=True)
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

    class Meta:
        verbose_name = "Publikacja instytucji V2"
        verbose_name_plural = "Publikacje instytucji V2"
        unique_together = ("uuid", "objectId")

    def __str__(self):
        return self.json_data.get("title")

    uuid = models.UUIDField(primary_key=True)
    # objectId powinno być realnie OneToOne, ale ja za cholerę nie wiem, czy PBN ma realnie to unikalne,
    # potem będzie się mój system wykrzaczał jeżeli oni mają zdublowane, więc:
    objectId = models.ForeignKey("pbn_api.Publication", on_delete=models.CASCADE)
    json_data = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
