from django.db import models
from django.utils.functional import cached_property

from .base import BasePBNMongoDBModel


class Institution(BasePBNMongoDBModel):
    class Meta:
        verbose_name = "Instytucja w PBN API"
        verbose_name_plural = "Instytucje w PBN API"

    name = models.TextField(blank=True, default="", db_index=True)
    addressCity = models.TextField(blank=True, default="", db_index=True)
    addressStreet = models.TextField(blank=True, default="", db_index=True)
    addressStreetNumber = models.TextField(blank=True, default="", db_index=True)
    addressPostalCode = models.TextField(blank=True, default="", db_index=True)
    polonUid = models.TextField(blank=True, default="", db_index=True)

    pull_up_on_save = [
        "name",
        "addressCity",
        "addressStreet",
        "addressStreetNumber",
        "addressPostalCode",
        "polonUid",
    ]

    def __str__(self):
        parent = self.value_or_none("object", "rootId")
        if parent:
            if parent == self.pk:
                parent = None
            else:
                try:
                    parent = Institution.objects.get(mongoId=parent)
                    parent = parent.name
                except Institution.DoesNotExist:
                    parent = None

        if parent is not None:
            parent = f" => {parent}"
        ret = (
            f"{self.name} {parent or ''}, "
            f"{self.addressCity or ''}, "
            f"{self.addressStreet or ''} {self.addressStreetNumber or ''} "
            f"{self.value_or_none('objects', 'email') or ''} "
            f"{self.value_or_none('objects', 'website') or ''} "
            f"(ID: {self.mongoId})"
        )
        while ret.find("  ") != -1:
            ret = ret.replace("  ", " ")
        ret = ret.replace(" ,", ",")
        while ret.find(",,") != -1:
            ret = ret.replace(",,", ",")
        ret = ret.replace(", (", " (")
        if self.status == "DELETED":
            ret = f"[❌ USUNIĘTY] {ret}"
        return ret

    @cached_property
    def rekord_w_bpp(self):
        from bpp.models import Jednostka, Uczelnia

        try:
            return Jednostka.objects.get(pbn_uid_id=self.pk)
        except Jednostka.DoesNotExist:
            try:
                return Uczelnia.objects.get(pbn_uid_id=self.pk)
            except Uczelnia.DoesNotExist:
                pass
