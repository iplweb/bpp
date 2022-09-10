from django.db import models

from .base import BasePBNMongoDBModel

from django.utils.functional import cached_property

from bpp import const
from bpp.models import LinkDoPBNMixin


class Scientist(LinkDoPBNMixin, BasePBNMongoDBModel):
    url_do_pbn = const.LINK_PBN_DO_AUTORA
    atrybut_dla_url_do_pbn = "pk"

    from_institution_api = models.BooleanField(
        "Rekord z API instytucji", db_index=True, null=True
    )

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

    @cached_property
    def rekord_w_bpp(self):
        from bpp.models.autor import Autor

        try:
            return Autor.objects.filter(pbn_uid_id=self.pk).first()
        except Autor.DoesNotExist:
            pass
