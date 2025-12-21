import sys
import traceback
from enum import Enum

import rollbar
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import PositiveIntegerField
from django.urls import reverse
from django.utils import timezone

from django_bpp.settings.base import AUTH_USER_MODEL
from pbn_api.exceptions import (
    AccessDeniedException,
    AlreadyEnqueuedError,
    CharakterFormalnyNieobslugiwanyError,
    HttpException,
    NeedsPBNAuthorisationException,
    PKZeroExportDisabled,
    PraceSerwisoweException,
    ResourceLockedException,
    WillNotExportError,
)


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


class RodzajBledu(models.TextChoices):
    TECHNICZNY = "TECH", "Techniczny"
    MERYTORYCZNY = "MERYT", "Merytoryczny"


def model_table_exists(model):
    """Check if a model's table exists"""
    from django.db import connection

    table_name = model._meta.db_table
    return table_name in connection.introspection.table_names()


class PBN_Export_Queue(models.Model):
    object_id = PositiveIntegerField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    rekord_do_wysylki = GenericForeignKey()

    zamowil = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    zamowiono = models.DateTimeField(auto_now_add=True, db_index=True)

    wysylke_podjeto = models.DateTimeField(null=True, blank=True)
    wysylke_zakonczono = models.DateTimeField(null=True, blank=True, db_index=True)

    ilosc_prob = models.PositiveSmallIntegerField(default=0)
    zakonczono_pomyslnie = models.BooleanField(null=True, default=None, db_index=True)
    komunikat = models.TextField(null=True, blank=True)  # noqa: DJ001

    retry_after_user_authorised = models.BooleanField(
        null=True, default=None, db_index=True
    )

    rodzaj_bledu = models.CharField(  # noqa: DJ001
        max_length=5,
        choices=RodzajBledu.choices,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Rodzaj błędu",
    )

    objects = PBN_Export_QueueManager()

    class Meta:
        verbose_name = "Kolejka eksportu do PBN"
        verbose_name_plural = "Kolejka eksportu do PBN"
        ordering = ("-zamowiono", "zamowil")

    def __str__(self):
        return f"Zlecenie wysyłki do PBN dla {self.rekord_do_wysylki}"

    @property
    def ostatnia_aktualizacja(self):
        """Returns the most recent update timestamp"""
        if self.wysylke_zakonczono:
            return self.wysylke_zakonczono
        elif self.wysylke_podjeto:
            return self.wysylke_podjeto
        else:
            return self.zamowiono

    def check_if_record_still_exists(self):
        if not self.content_type_id:
            return False

        try:
            # Check iftable exists for that model...
            if not model_table_exists(self.content_type.model_class()):
                return False

            try:
                if self.content_type.get_object_for_this_type(pk=self.object_id):
                    return True

            except ObjectDoesNotExist:
                return False
        except self.content_type.model_class().DoesNotExist:
            return False

    def prepare_for_resend(self, user=None, message_suffix=""):
        """Przygotowuje obiekt do ponownej wysyłki."""
        self.refresh_from_db()
        self.wysylke_zakonczono = None
        self.zakonczono_pomyslnie = None
        self.retry_after_user_authorised = None
        self.rodzaj_bledu = None

        msg = "Ponownie wysłano"
        if user is not None:
            self.zamowil = user
            msg += f" przez użytkownika: {user}"
        if message_suffix is not None:
            msg += f"{message_suffix}"
        msg += ". "
        self.dopisz_komunikat(msg)

        self.save()

    def sprobuj_wyslac_do_pbn(self):
        from pbn_export_queue.tasks import task_sprobuj_wyslac_do_pbn

        task_sprobuj_wyslac_do_pbn.delay(self.pk)

    def dopisz_komunikat(self, msg):
        res = str(timezone.now())
        res += "\n" + "==============================================================="
        res += "\n" + msg + "\n"
        if self.komunikat:
            self.komunikat = "\n" + res + "\n" + self.komunikat
        else:
            self.komunikat = res

    def error(self, msg, rodzaj=None):
        self.wysylke_zakonczono = timezone.now()
        self.zakonczono_pomyslnie = False
        self.rodzaj_bledu = rodzaj
        self.dopisz_komunikat(msg)
        self.save()
        return SendStatus.FINISHED_ERROR

    def _is_pbn_validation_error(self, exc):
        """Sprawdza czy HttpException zawiera błąd walidacji z PBN."""
        if not exc.json:
            return False

        # Format 1: {"details": {...}} - obiekt z niepustym details
        if isinstance(exc.json, dict) and "details" in exc.json and exc.json["details"]:
            return True

        # Format 2: [{"code": "NOT_UNIQUE_PUBLICATION", ...}] - tablica z kodem błędu
        if (
            isinstance(exc.json, list)
            and exc.json
            and isinstance(exc.json[0], dict)
            and "code" in exc.json[0]
        ):
            return True

        return False

    def _handle_pbn_exception(self, exc):
        """Obsługuje wyjątki z wysyłki do PBN. Zwraca SendStatus lub None."""
        if isinstance(exc, PraceSerwisoweException):
            self.dopisz_komunikat("Prace serwisowe w PBN, spróbuję za kilka godzin")
            self.save()
            return SendStatus.RETRY_MUCH_LATER

        if isinstance(exc, NeedsPBNAuthorisationException):
            self.dopisz_komunikat(
                "Użytkownik bez autoryzacji w PBN, spróbuję po zalogowaniu do PBN."
            )
            self.retry_after_user_authorised = True
            self.save()
            return SendStatus.RETRY_AFTER_USER_AUTHORISED

        if isinstance(exc, CharakterFormalnyNieobslugiwanyError):
            return self.error(
                "Charakter formalny tego rekordu nie jest ustawiony jako wysyłany do "
                "PBN. Zmień konfigurację bazy BPP, Redagowanie -> Dane systemowe -> "
                "Charaktery formalne",
                rodzaj=RodzajBledu.MERYTORYCZNY,
            )

        if isinstance(exc, AccessDeniedException):
            return self.error(
                "Brak uprawnień, załączam traceback:\n" + traceback.format_exc(),
                rodzaj=RodzajBledu.TECHNICZNY,
            )

        if isinstance(exc, PKZeroExportDisabled):
            return self.error(
                "Eksport prac bez punktów PK wyłączony w konfiguracji, nie wysłano.",
                rodzaj=RodzajBledu.MERYTORYCZNY,
            )

        if isinstance(exc, ResourceLockedException):
            self.dopisz_komunikat(f"{exc}, ponowiam wysyłkę za kilka minut...")
            self.save()
            return SendStatus.RETRY_LATER

        # WillNotExportError i podklasy (DOIorWWWMissing, LanguageMissingPBNUID, etc.)
        # PKZeroExportDisabled jest obsłużony wcześniej osobno
        if isinstance(exc, WillNotExportError):
            return self.error(
                f"Rekord nie może być wysłany do PBN: {exc}\n\n"
                + traceback.format_exc(),
                rodzaj=RodzajBledu.MERYTORYCZNY,
            )

        # HttpException - sprawdź czy to błąd walidacji (MERYTORYCZNY) czy techniczny
        if isinstance(exc, HttpException):
            if self._is_pbn_validation_error(exc):
                return self.error(
                    "Błąd walidacji po stronie PBN, załączam traceback:\n"
                    + traceback.format_exc(),
                    rodzaj=RodzajBledu.MERYTORYCZNY,
                )

            # Inny HttpException bez walidacji - błąd techniczny
            return self.error(
                "Wystąpił błąd HTTP z PBN, załączam traceback:\n"
                + traceback.format_exc(),
                rodzaj=RodzajBledu.TECHNICZNY,
            )

        # Nieobsługiwany wyjątek
        rollbar.report_exc_info(sys.exc_info())
        return self.error(
            "Wystąpił nieobsługiwany błąd, załączam traceback:\n"
            + traceback.format_exc(),
            rodzaj=RodzajBledu.TECHNICZNY,
        )

    def _handle_successful_send(self, sent_data, notificator):
        """Obsługuje pomyślną wysyłkę do PBN."""
        msg = (
            "Wysłano poprawnie. Link do wysłanego kodu JSON <a href="
            + reverse("admin:pbn_api_sentdata_change", args=[sent_data.pk])
            + ">tutaj</a>. "
        )
        extra_info = "\n".join(notificator)
        if extra_info:
            msg += "\n\nDodatkowe informacje:\n" + extra_info

        self.wysylke_zakonczono = timezone.now()
        self.dopisz_komunikat(msg)
        self.zakonczono_pomyslnie = True
        self.save()
        return SendStatus.FINISHED_OKAY

    def send_to_pbn(self):
        """:return: SendStatus"""
        self.refresh_from_db()

        if self.wysylke_zakonczono is not None:
            return SendStatus.FINISHED_OKAY

        if not self.check_if_record_still_exists():
            return self.error(
                "Rekord został usunięty nim wysyłka była możliwa.",
                rodzaj=RodzajBledu.TECHNICZNY,
            )

        self.wysylke_podjeto = timezone.now()
        if self.retry_after_user_authorised:
            self.retry_after_user_authorised = None
        self.ilosc_prob += 1
        self.save()

        from bpp.admin.helpers.pbn_api.cli import sprobuj_wyslac_do_pbn_celery

        try:
            sent_data, notificator = sprobuj_wyslac_do_pbn_celery(
                user=self.zamowil.get_pbn_user(),
                obj=self.rekord_do_wysylki,
                force_upload=True,
            )
        except Exception as exc:
            return self._handle_pbn_exception(exc)

        if sent_data is None:
            return self.error(
                "Wystąpił błąd, dane nie zostały wysłane, wyjaśnienie poniżej.\n\n"
                + "\n".join(notificator),
                rodzaj=RodzajBledu.MERYTORYCZNY,
            )

        return self._handle_successful_send(sent_data, notificator)
