from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.functional import cached_property

from .base import BasePBNModel


class DisciplineGroupManager(models.Manager):
    def get_current(self):
        d = timezone.now().date()
        return self.get(
            Q(validityDateFrom__lte=d)
            & (Q(validityDateTo=None) | Q(validityDateTo__gt=d))
        )


class DisciplineGroup(BasePBNModel):
    # unique=True: ``PBNClient.download_disciplines`` robi lookup po samym
    # ``uuid``. Bez unikalności dwa równoległe importy tworzyły duplikat, a od
    # tego momentu KAŻDY kolejny ``update_or_create(uuid=...)`` rzucał
    # ``MultipleObjectsReturned`` — import dyscyplin blokował się na twardo.
    uuid = models.UUIDField(unique=True)
    validityDateFrom = models.DateField()
    validityDateTo = models.DateField(null=True, blank=True)

    objects = DisciplineGroupManager()

    class Meta:
        verbose_name = "słownik dyscyplin PBN"
        verbose_name_plural = "słowniki dyscyplin PBN"
        ordering = ("validityDateFrom",)

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
        ordering = ("name", "code")
        constraints = [
            # UWAGA: ``uuid`` dyscypliny NIE jest w PBN unikalny globalnie —
            # ta sama dyscyplina występuje pod tym samym ``uuid`` w wielu
            # słownikach (w fixture 44 z 59 uuid-ów powtarza się między
            # słownikiem 2018-2022 a 2022-teraz). Unikalna jest dopiero para
            # (słownik, uuid) — i dokładnie po takiej parze robi lookup
            # ``PBNClient.download_disciplines``.
            models.UniqueConstraint(
                fields=["parent_group", "uuid"],
                name="pbn_api_discipline_uuid_unikalny_w_slowniku",
            )
        ]

    def __str__(self):
        ret = f"Dyscyplina {self.name} ("
        if self.parent_group.is_current:
            ret += "słownik: aktualny)"
        else:
            ret += f"słownik: {self.parent_group.validityDateFrom.year}-{self.parent_group.validityDateTo.year})"
        return ret
