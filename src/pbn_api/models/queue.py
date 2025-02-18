import traceback

from django.db import models
from django.db.models import PositiveIntegerField
from django.urls import reverse
from sentry_sdk import capture_exception

from pbn_api.exceptions import AlreadyEnqueuedError
from pbn_api.tasks import task_sprobuj_wyslac_do_pbn

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from django.utils import timezone

from django_bpp.settings.base import AUTH_USER_MODEL


class PBN_Export_QueueManager(models.Manager):
    def filter_rekord_do_wysylki(self, rekord):
        return self.filter(
            content_type=ContentType.objects.get_for_model(rekord),
            object_id=rekord.pk,
            wysylke_zakonczono=None,
        )

    def sprobuj_utowrzyc_wpis(self, user, rekord):
        if self.filter_rekord_do_wysylki(rekord).exists():
            raise AlreadyEnqueuedError("ten rekord jest już w kolejce do wysyłki")

        return self.create(
            rekord_do_wysylki=rekord,
            zamowil=user,
        )


class PBN_Export_Queue(models.Model):
    objects = PBN_Export_QueueManager()

    object_id = PositiveIntegerField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    rekord_do_wysylki = GenericForeignKey()

    zamowil = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    zamowiono = models.DateTimeField(auto_now_add=True, db_index=True)

    wysylke_podjeto = models.DateTimeField(null=True, blank=True)
    wysylke_zakonczono = models.DateTimeField(null=True, blank=True, db_index=True)

    ilosc_prob = models.PositiveSmallIntegerField(default=0)
    zakonczono_pomyslnie = models.BooleanField(null=True, default=None, db_index=True)
    komunikat = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Kolejka eksportu do PBN"
        verbose_name_plural = "Kolejka eksportu do PBN"
        ordering = ("-zamowiono", "zamowil")

    def __str__(self):
        return f"Zlecenie wysyłki do PBN dla {self.rekord_do_wysylki}"

    def check_if_record_still_exists(self):
        if self.rekord_do_wysylki is None:
            return False
        return True

    def dopisz_komunikat(self, msg):
        res = str(timezone.now())
        res += "\n" + "==============================================================="
        res += "\n" + msg
        if self.komunikat:
            self.komunikat = "\n" + res + "\n" + self.komunikat
        else:
            self.komunikat = res

    def error(self, msg):
        self.wysylke_zakonczono = timezone.now()
        self.zakonczono_pomyslnie = False
        self.dopisz_komunikat(msg)
        self.save()

    def send_to_pbn(self):
        if not self.check_if_record_still_exists():
            if self.wysylke_zakonczono is not None:
                raise Exception(
                    "System próbuje ponownie wysyłać rekordy, których wysyłać nie powinien"
                )

            self.wysylke_zakonczono = timezone.now()
            self.zakonczono_pomyslnie = False
            msg = "Rekord został usunięty nim wysyłka była możliwa."
            self.dopisz_komunikat(msg)
            self.save()
            return msg

        self.wysylke_podjeto = timezone.now()
        self.ilosc_prob += 1
        self.save()

        from bpp.admin.helpers import sprobuj_wgrac_do_pbn_celery

        try:
            sent_data, notificator = sprobuj_wgrac_do_pbn_celery(
                user=self.zamowil,
                obj=self.rekord_do_wysylki,
                force_upload=True,
            )
        except Exception as e:
            self.error(
                "Wystąpił nieobsługiwany błąd, załączam traceback:\n"
                + traceback.format_exc()
            )
            capture_exception(e)
            return (
                "Wystąpił nieobsługiwany błąd, załączam traceback:\n"
                + traceback.format_exc()
            )

        if sent_data is None:
            log = notificator.as_text()
            if log.find("HttpException(423, '/api/v1/publications', 'Locked')"):
                self.dopisz_komunikat("Http423 Locked, ponowie wysylke za 5 miunt...")
                self.save()
                task_sprobuj_wyslac_do_pbn.apply_async(args=[self.pk], countdown=5 * 60)
                return "Http423 Locked, ponowie wysylke za 5 miunt..."

            self.dopisz_komunikat(
                "Rekord nie wysłany -- załączam log z próby. Zapewne zostaną podjęte kolejne.\n"
                + log
            )
            self.save()

            return (
                "Rekord nie wysłany -- załączam log z próby. Zapewne zostaną podjęte kolejne.\n"
                + log
            )

        msg = (
            "Wysłano poprawnie. Link do wysłanego kodu JSON <a href="
            + reverse("admin:pbn_api_sentdata_change", args=[sent_data.pk])
            + ">tutaj</a>"
        )
        self.wysylke_zakonczono = timezone.now()
        self.dopisz_komunikat(msg)
        self.zakonczono_pomyslnie = True
        self.save()
        return msg
