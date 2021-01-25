# Tu skoczyłem
#
# Plan
# 1) zrobić obiekt 'raport uczelnia', zamawianie raportu -> tworzenie go,
# 2) podstrona 'details' to jest:
# - strona po zamowieniu raportu,
# - oczekiwanie na wygenerowanie
# - zamawianie w alternatywnych formatach
# - przejscie do podgladu
#
# 3) listview: raport jest powieszony /rpaort_uczelnia/ID/ i tam jest ListView ewentualnie z filtrami
#
# 4) zadnego progress baru w javie, chociaz nie wiem w sumie
#
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from bpp.core import zbieraj_sloty
from bpp.fields import YearField
from bpp.models import Cache_Punktacja_Autora_Query, Uczelnia
from bpp.util import year_last_month
from notifications.core import send_redirect
from raport_slotow.models.asgi_notification_mixin import ASGINotificationMixin
from raport_slotow.models.mixins import Report


class RaportSlotowUczelnia(ASGINotificationMixin, Report):
    od_roku = YearField(default=year_last_month)
    do_roku = YearField(default=Uczelnia.objects.do_roku_default)

    slot = models.DecimalField(default=Decimal("1"), decimal_places=4, max_digits=7)

    minimalny_pk = models.DecimalField(default=0, decimal_places=2, max_digits=5)

    dziel_na_jednostki_i_wydzialy = models.BooleanField(
        verbose_name="Dziel na jednostki i wydziały",
        default=True,
    )

    def get_absolute_url(self):
        return reverse(
            "raport_slotow:szczegoly-raport-slotow-uczelnia", args=(self.pk,)
        )

    def clean(self):
        if self.od_roku > self.do_roku:
            raise ValidationError(
                {
                    "od_roku": ValidationError(
                        'Pole musi być większe lub równe jak pole "Do roku".'
                    )
                }
            )

    def create_report(self):
        # lista wszystkich autorow z punktacja z okresu od-do roku
        lst = "autor_id", "dyscyplina_id"
        if self.dziel_na_jednostki_i_wydzialy:
            lst += ("jednostka_id",)

        kombinacje = (
            Cache_Punktacja_Autora_Query.objects.filter(
                rekord__rok__gte=self.od_roku, rekord__rok__lte=self.do_roku
            )
            .values_list(*lst)
            .distinct()
        )

        total = kombinacje.count()

        for n, res in enumerate(kombinacje):
            if self.dziel_na_jednostki_i_wydzialy:
                autor_id, dyscyplina_id, jednostka_id = res
            else:
                autor_id, dyscyplina_id = res
                jednostka_id = None

            maks_punkty, lista, sloty_sum = zbieraj_sloty(
                autor_id,
                self.slot,
                self.od_roku,
                self.do_roku,
                self.minimalny_pk,
                dyscyplina_id=dyscyplina_id,
                jednostka_id=jednostka_id,
            )

            avg = None
            if sloty_sum != 0:
                avg = maks_punkty / sloty_sum

            self.raportslotowuczelniawiersz_set.create(
                autor_id=autor_id,
                jednostka_id=jednostka_id,
                dyscyplina_id=dyscyplina_id,
                slot=sloty_sum,
                pkd_aut_sum=maks_punkty,
                avg=avg,
            )

            if not n % 10:
                self.send_progress(n * 100.0 / total)

    def on_finished_successfully(self):
        send_redirect(str(self.pk), "./details")


class RaportSlotowUczelniaWiersz(models.Model):
    parent = models.ForeignKey(RaportSlotowUczelnia, on_delete=models.CASCADE)
    autor = models.ForeignKey("bpp.Autor", on_delete=models.CASCADE)
    jednostka = models.ForeignKey(
        "bpp.Jednostka", on_delete=models.CASCADE, null=True, blank=True
    )
    dyscyplina = models.ForeignKey("bpp.Dyscyplina_Naukowa", on_delete=models.CASCADE)
    pkd_aut_sum = models.DecimalField(
        "Suma punktów dla autora", max_digits=8, decimal_places=4
    )
    slot = models.DecimalField(max_digits=8, decimal_places=4)
    avg = models.DecimalField(
        "Średnio punktów dla autora na slot",
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
    )
