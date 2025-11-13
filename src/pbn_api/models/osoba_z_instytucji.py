from django.db import models


class OsobaZInstytucji(models.Model):
    personId = models.OneToOneField(
        "pbn_api.Scientist", on_delete=models.PROTECT, db_index=True
    )
    firstName = models.TextField()
    lastName = models.TextField()
    institutionId = models.ForeignKey("pbn_api.Institution", on_delete=models.PROTECT)
    institutionName = models.TextField()
    title = models.TextField(blank=True, default="")
    polonUuid = models.UUIDField(unique=True)
    phdStudent = models.BooleanField()
    _from = models.DateField(null=True, blank=True)
    _to = models.DateField(null=True, blank=True)

    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.personId_id} {self.firstName} {self.lastName}"
