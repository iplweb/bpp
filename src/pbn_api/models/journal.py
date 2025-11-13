from django.db import models

from bpp import const
from bpp.models import LinkDoPBNMixin

from .base import BasePBNMongoDBModel


class Journal(LinkDoPBNMixin, BasePBNMongoDBModel):
    url_do_pbn = const.LINK_PBN_DO_ZRODLA
    atrybut_dla_url_do_pbn = "pk"

    class Meta:
        verbose_name = "Zródło w PBN API"
        verbose_name_plural = "Zródła w PBN API"

    title = models.TextField(blank=True, default="", db_index=True)
    websiteLink = models.TextField(blank=True, default="", db_index=True)
    issn = models.TextField(blank=True, default="", db_index=True)
    eissn = models.TextField(blank=True, default="", db_index=True)
    mniswId = models.IntegerField(null=True, blank=True, db_index=True)

    pull_up_on_save = ["title", "websiteLink", "issn", "eissn", "mniswId"]

    def __str__(self):
        ret = (
            f"{self.title}, ISSN: {self.issn or '-'}, "
            f"EISSN: {self.eissn or '-'}, MNISW ID: {self.mniswId or '-'}"
        )
        if self.status == "DELETED":
            ret = f"[❌ USUNIĘTY] {ret}"
        return ret

    def rekord_w_bpp(self):
        from bpp.models import Zrodlo

        try:
            return Zrodlo.objects.filter(pbn_uid_id=self.pk).first()
        except Zrodlo.DoesNotExist:
            return
