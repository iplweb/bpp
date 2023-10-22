from django.db import models

from import_common.core import matchuj_wydawce
from .base import BasePBNMongoDBModel

from bpp import const
from bpp.models import LinkDoPBNMixin


class PublisherManager(models.Manager):
    def official(self):
        return self.exclude(mniswId=None)


class Publisher(LinkDoPBNMixin, BasePBNMongoDBModel):
    objects = PublisherManager()

    url_do_pbn = const.LINK_PBN_DO_WYDAWCY
    atrybut_dla_url_do_pbn = "pk"

    class Meta:
        verbose_name = "Wydawca w PBN API"
        verbose_name_plural = "Wydawcy w PBN API"
        ordering = ("mniswId", "publisherName")

    pull_up_on_save = ["publisherName", "mniswId"]

    publisherName = models.TextField(null=True, blank=True, db_index=True)
    mniswId = models.IntegerField(null=True, blank=True, db_index=True)

    def __str__(self):
        return f"{self.publisherName}, MNISW ID: {self.mniswId or '-'}"

    @property
    def points(self):
        return self.current_version["object"]["points"]

    def rekord_w_bpp(self):
        from bpp.models import Wydawca

        try:
            return Wydawca.objects.get(pbn_uid_id=self.pk)
        except Wydawca.DoesNotExist:
            pass

    def matchuj_wydawce(self):
        return matchuj_wydawce(self.publisherName, self.pk)
