from django.db import models

from .base import BasePBNMongoDBModel


class Scientist(BasePBNMongoDBModel):
    from_institution_api = models.NullBooleanField(db_index=True)

    lastName = models.TextField(db_index=True, null=True, blank=True)
    name = models.TextField(db_index=True, null=True, blank=True)
    pbnId = models.TextField(db_index=True, null=True, blank=True)
    qualifications = models.TextField("Tytuł", db_index=True, null=True, blank=True)
    orcid = models.TextField(db_index=True, null=True, blank=True)
    polonUid = models.TextField(db_index=True, null=True, blank=True)

    pull_up_on_save = ["lastName", "name", "qualifications", "orcid", "polonUid"]

    class Meta:
        verbose_name = "Osoba w PBN API"
        verbose_name_plural = "Osoby w PBN API"

        unique_together = [
            "mongoId",
            "lastName",
            "name",
            "orcid",
        ]

    def currentEmploymentsInstitutionDisplayName(self):
        ces = self.value("object", "currentEmployments", return_none=True)
        if ces is not None:
            return ces[0].get("institutionDisplayName")

    def __str__(self):
        ret = (
            f"{self.lastName} {self.name}, {self.qualifications or '-'}, "
            f"{self.currentEmploymentsInstitutionDisplayName() or '-'}, (PBN ID: {self.pk})"
        )
        ret = ret.replace(" ,", ",")
        ret = ret.replace("-, ", "")
        ret = ret.replace(", (", " (")
        return ret
