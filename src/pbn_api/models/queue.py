import traceback
from enum import Enum

from django.db import models
from django.db.models import PositiveIntegerField
from django.urls import reverse
from sentry_sdk import capture_exception

from pbn_api.exceptions import (
    AccessDeniedException,
    AlreadyEnqueuedError,
    CharakterFormalnyNieobslugiwanyError,
    NeedsPBNAuthorisationException,
    PKZeroExportDisabled,
    PraceSerwisoweException,
    ResourceLockedException,
)

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


class SendStatus(Enum):
    RETRY_SOON = 0  # few seconds, 423 Locked
    RETRY_LATER = 1  # few minutes
    RETRY_MUCH_LATER = 2  # few hours, PraceSerwisoweExecption

    RETRY_AFTER_USER_AUTHORISED = 3  # when user logs in + authorizes

    FINISHED_OKAY = 5
    FINISHED_ERROR = 6


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

    retry_after_user_authorised = models.BooleanField(
        null=True, default=None, db_index=True
    )

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
        res += "\n" + msg + "\n"
        if self.komunikat:
            self.komunikat = "\n" + res + "\n" + self.komunikat
        else:
            self.komunikat = res

    def error(self, msg):
        self.wysylke_zakonczono = timezone.now()
        self.zakonczono_pomyslnie = False
        self.dopisz_komunikat(msg)
        self.save()
        return SendStatus.FINISHED_ERROR

    def send_to_pbn(self):
        """
        :return: (int : SendStatus,)
        """

        if not self.check_if_record_still_exists():
            if self.wysylke_zakonczono is not None:
                raise Exception(
                    "System próbuje ponownie wysyłać rekordy, których wysyłać nie powinien"
                )

            return self.error("Rekord został usunięty nim wysyłka była możliwa.")

        self.wysylke_podjeto = timezone.now()
        if self.retry_after_user_authorised:
            self.retry_after_user_authorised = (
                None  # Zresetuj wartosc tego pola, rekord wysyłany n-ty raz
            )
        self.ilosc_prob += 1
        self.save()

        from bpp.admin.helpers.pbn_api.cli import sprobuj_wyslac_do_pbn_celery

        try:
            sent_data, notificator = sprobuj_wyslac_do_pbn_celery(
                user=self.zamowil.get_pbn_user(),
                obj=self.rekord_do_wysylki,
                force_upload=True,
            )
        except PraceSerwisoweException:
            self.dopisz_komunikat("Prace serwisowe w PBN, spróbuję za kilka godzin")
            self.save()
            return SendStatus.RETRY_MUCH_LATER

        except NeedsPBNAuthorisationException:
            self.dopisz_komunikat(
                "Użytkownik bez autoryzacji w PBN, spróbuję po zalogowaniu do PBN."
            )
            self.retry_after_user_authorised = True
            self.save()
            return SendStatus.RETRY_AFTER_USER_AUTHORISED

        except CharakterFormalnyNieobslugiwanyError:
            self.error(
                "Charakter formalny tego rekordu nie jest ustawiony jako wysyłany do PBN. Zmień konfigurację "
                "bazy BPP, Redagowanie -> Dane systemowe -> Charaktery formalne"
            )
            return SendStatus.FINISHED_ERROR

        except AccessDeniedException:
            return self.error(
                "Brak uprawnień, załączam traceback:\n" + traceback.format_exc()
            )
            return SendStatus.FINISHED_ERROR

        except PKZeroExportDisabled:
            self.error(
                "Eksport prac bez punktów PK wyłączony w konfiguracji, nie wysłano."
            )
            return SendStatus.FINISHED_ERROR

        except ResourceLockedException as e:
            self.dopisz_komunikat(f"{e}, ponowiam wysyłkę za kilka minut...")
            self.save()
            return SendStatus.RETRY_LATER

        except Exception as e:
            capture_exception(e)
            return self.error(
                "Wystąpił nieobsługiwany błąd, załączam traceback:\n"
                + traceback.format_exc()
            )

        if sent_data is None:
            return self.error(
                "Wystąpił błąd, dane nie zostały wysłane, wyjaśnienie poniżej.\n\n"
                + "\n".join(notificator)
            )

        msg = (
            "Wysłano poprawnie. Link do wysłanego kodu JSON <a href="
            + reverse("admin:pbn_api_sentdata_change", args=[sent_data.pk])
            + ">tutaj</a>. "
        )
        extra_info = "\n".join(notificator)
        # Jeżeli notyfikator zawiera cokolwiek, a może zawierać np ostrzeżenia czy uwagi do
        # wysłanego rekordu to dołącz to
        if extra_info:
            msg += "\n\nDodatkowe informacje:\n" + extra_info

        self.wysylke_zakonczono = timezone.now()
        self.dopisz_komunikat(msg)
        self.zakonczono_pomyslnie = True
        self.save()

        return SendStatus.FINISHED_OKAY
