from django.db import models
from django.db.models import Q

from .base import BasePBNModel

from django.utils import timezone
from django.utils.functional import cached_property


class DisciplineGroupManager(models.Manager):
    def get_current(self):
        d = timezone.now().date()
        return self.get(
            Q(validityDateFrom__lte=d)
            & (Q(validityDateTo=None) | Q(validityDateTo__gt=d))
        )


class DisciplineGroup(BasePBNModel):
    uuid = models.UUIDField()
    validityDateFrom = models.DateField()
    validityDateTo = models.DateField(null=True, blank=True)

    objects = DisciplineGroupManager()

    class Meta:
        verbose_name = "słownik dyscyplin PBN"
        verbose_name_plural = "słowniki dyscyplin PBN"

    @cached_property
    def is_current(self):
        d = timezone.now().date()

        if d >= self.validityDateFrom and (
            self.validityDateTo is None or d < self.validityDateTo
        ):
            return True
        return False

    def __str__(self):
        ret = "Nieaktualny"
        if self.is_current:
            ret = "Aktualny"

        ret += f" słownik dyscyplin PBN -- ważny od {self.validityDateFrom}"
        if self.validityDateTo is not None:
            ret += f" do {self.validityDateTo}"
        return ret


class Discipline(BasePBNModel):
    parent_group = models.ForeignKey(
        DisciplineGroup, on_delete=models.CASCADE, verbose_name="Słownik dyscyplin"
    )

    uuid = models.UUIDField()
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=200)
    polonCode = models.CharField(max_length=50)
    scientificFieldName = models.CharField(max_length=200, verbose_name="Dziedzina")

    class Meta:
        verbose_name = "Dyscyplina PBN"
        verbose_name_plural = "Dyscypliny PBN"

    def __str__(self):
        ret = f"Dyscyplina {self.name} ("
        if self.parent_group.is_current:
            ret += "słownik: aktualny)"
        else:
            ret += "słownik: nieaktualny)"
        return ret
