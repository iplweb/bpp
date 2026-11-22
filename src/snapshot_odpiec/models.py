from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import connection, models, transaction

from snapshot_odpiec.core import (
    przypiecia_apply_to_database_queries,
    przypiecia_copy_from_database_queries,
)


class SnapshotOdpiecManager(models.Manager):
    @transaction.atomic
    def create(self, *args, **kw):
        obj = super().create(*args, **kw)

        with connection.cursor() as cursor:
            [
                cursor.execute(query)
                for query in przypiecia_copy_from_database_queries(parent_obj=obj)
            ]

        return obj


class SnapshotOdpiec(models.Model):
    created_on = models.DateTimeField(auto_now_add=True, editable=False)
    owner = models.ForeignKey(
        "bpp.BppUser", on_delete=models.PROTECT, null=True, blank=True
    )
    # null=True historycznie (zmiana wymagałaby migracji danych bez zysku)
    comment = models.TextField(null=True, blank=True)  # noqa: DJ001
    okres = models.ForeignKey(
        "ewaluacja_common.OkresEwaluacji",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="okres ewaluacji",
        help_text="Snapshot obejmuje tylko prace z lat tego okresu. Puste = "
        "snapshot sprzed podziału na okresy (wszystkie lata).",
    )

    objects = SnapshotOdpiecManager()

    def apply(self):
        with connection.cursor() as cursor:
            for elem in przypiecia_apply_to_database_queries(parent_obj=self):
                cursor.execute(elem)

    def przypiete(self):
        return self.wartoscsnapshotu_set.filter(przypieta=True).count()

    def odpiete(self):
        return self.wartoscsnapshotu_set.filter(przypieta=False).count()

    def calosc(self):
        return self.wartoscsnapshotu_set.count()


class WartoscSnapshotu(models.Model):
    parent = models.ForeignKey(SnapshotOdpiec, on_delete=models.CASCADE)

    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.PROTECT
    )
    object_id = models.PositiveIntegerField()
    rekord = GenericForeignKey()

    przypieta = models.BooleanField()
