import logging
import sys
import traceback
from enum import Enum

import rollbar
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, models, transaction
from django.db.models import PositiveIntegerField, Q
from django.urls import reverse
from django.utils import timezone

from bpp.util import zaloguj_polkniety_wyjatek
from django_bpp.settings.base import AUTH_USER_MODEL
from pbn_api.exceptions import (
    AccessDeniedException,
    AlreadyEnqueuedError,
    CharakterFormalnyMissingPBNUID,
    CharakterFormalnyNieobslugiwanyError,
    HttpException,
    NeedsPBNAuthorisationException,
    PKZeroExportDisabled,
    PraceSerwisoweException,
    ResourceLockedException,
    StatementsResendFailedException,
    WillNotExportError,
)

logger = logging.getLogger(__name__)


#: Nazwa częściowego unikatu z Meta.constraints — jedyny IntegrityError,
#: który wolno przetłumaczyć na domenowe „już w kolejce".
NAZWA_UNIKATU_AKTYWNEGO_WPISU = "pbn_export_queue_jeden_aktywny_wpis_na_rekord"


def _to_kolizja_aktywnego_wpisu(exc):
    """Czy ten ``IntegrityError`` NAPRAWDĘ znaczy „już w kolejce"?

    psycopg wystawia nazwę naruszonego ograniczenia w
    ``exc.__cause__.diag.constraint_name``; gdy jej nie ma (inny sterownik
    albo backend) — fallback na tekst wyjątku.

    Tłumaczenie „w ciemno" połykało naruszenie NOT NULL na ``zamowil``
    (operacja systemowa bez użytkownika) i zamieniało brak wycofania
    oświadczeń w PBN w niewinny komunikat „już w kolejce".
    """
    diag = getattr(getattr(exc, "__cause__", None), "diag", None)
    nazwa = getattr(diag, "constraint_name", None)
    if nazwa:
        return nazwa == NAZWA_UNIKATU_AKTYWNEGO_WPISU
    return NAZWA_UNIKATU_AKTYWNEGO_WPISU in str(exc)


class PBN_Export_QueueManager(models.Manager):
    def filter_rekord_do_wysylki(self, rekord):
        return self.filter(
            content_type=ContentType.objects.get_for_model(rekord),
            object_id=rekord.pk,
            wysylke_zakonczono=None,
        )

    def sprobuj_utowrzyc_wpis(self, user, rekord, uczelnia=None, operacja=None):
        # Szybka ścieżka (przyjazny błąd bez trafiania w constraint bazy).
        if self.filter_rekord_do_wysylki(rekord).exists():
            raise AlreadyEnqueuedError("ten rekord jest już w kolejce do wysyłki")

        # Właściwe zabezpieczenie przed wyścigiem: między exists() a create()
        # inny proces mógł dodać aktywny wpis. Częściowy unikat
        # (content_type, object_id) WHERE wysylke_zakonczono IS NULL zamienia
        # ten TOCTOU w twardy IntegrityError, który tłumaczymy na domenowy
        # AlreadyEnqueuedError. savepoint (atomic) izoluje błąd, żeby nie
        # unieważnić ewentualnej otaczającej transakcji.
        kwargs = {
            "rekord_do_wysylki": rekord,
            "zamowil": user,
            "uczelnia": uczelnia,
        }
        if operacja is not None:
            # Pominięcie zostawia default modelu (WYSYLKA), więc wszystkie
            # dotychczasowe wywołania działają bez zmian.
            kwargs["operacja"] = operacja

        try:
            with transaction.atomic():
                return self.create(**kwargs)
        except IntegrityError as e:
            # Tylko kolizja częściowego unikatu znaczy „już w kolejce".
            # Każde inne naruszenie (NOT NULL na `zamowil` przy operacji
            # systemowej, zerwany FK) MUSI polecieć w górę — inaczej
            # zniknęłoby pod komunikatem sugerującym, że wszystko gra.
            if not _to_kolizja_aktywnego_wpisu(e):
                raise
            raise AlreadyEnqueuedError(
                "ten rekord jest już w kolejce do wysyłki"
            ) from e


class SendStatus(Enum):
    RETRY_SOON = 0  # few seconds, 423 Locked
    RETRY_LATER = 1  # few minutes
    RETRY_MUCH_LATER = 2  # few hours, PraceSerwisoweExecption

    RETRY_AFTER_USER_AUTHORISED = 3  # when user logs in + authorizes

    WYKLUCZONE = 4  # intentionally excluded from export (design reasons, not errors)

    FINISHED_OKAY = 5
    FINISHED_ERROR = 6

    # Inny worker trzyma wiersz (select_for_update skip_locked) — on go
    # obsłuży; bieżące zadanie kończy bez ponawiania.
    LOCKED_ELSEWHERE = 7


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

    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="pbn_export_queue",
    )

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

    wykluczone = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Wykluczone z eksportu",
        help_text="Publikacja wykluczona z eksportu z przyczyn projektowych (nie błąd)",
    )

    class Operacja(models.TextChoices):
        WYSYLKA = "wysylka", "Wysyłka"
        WYCOFANIE = "wycofanie", "Wycofanie oświadczeń"

    operacja = models.CharField(
        max_length=16,
        choices=Operacja.choices,
        default=Operacja.WYSYLKA,
        db_index=True,
        verbose_name="Operacja",
        help_text="Wycofanie usuwa oświadczenia dyscyplin publikacji z profilu "
        "instytucji w PBN (soft-delete rekordu). Nie kasuje samego obiektu "
        "publikacji w PBN — ten jest współdzielony między instytucjami.",
    )

    objects = PBN_Export_QueueManager()

    class Meta:
        verbose_name = "Kolejka eksportu do PBN"
        verbose_name_plural = "Kolejka eksportu do PBN"
        ordering = ("-zamowiono", "zamowil")
        constraints = [
            # Co najwyżej JEDEN aktywny (niezakończony) wpis na dany rekord.
            # Warunek pokrywa się z filter_rekord_do_wysylki() — dzięki temu
            # równoległe zlecenia wysyłki nie tworzą duplikatów w kolejce.
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                condition=Q(wysylke_zakonczono__isnull=True),
                name="pbn_export_queue_jeden_aktywny_wpis_na_rekord",
            ),
        ]

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
                obiekt = self.content_type.get_object_for_this_type(pk=self.object_id)
            except ObjectDoesNotExist:
                return False

            # ⚠️ `get_object_for_this_type` pyta `_base_manager`, który z
            # definicji NIE filtruje (Django wymaga, żeby zwracał wszystkie
            # wiersze). Rekord soft-skasowany jest więc tą drogą nadal
            # znajdowany, mimo że `objects` go nie pokazuje. Dla WYSYŁKI
            # „w koszu" ma znaczyć „nie ma go" — inaczej wysyłalibyśmy do PBN
            # publikację, którą operator usunął.
            #
            # Dla WYCOFANIA ta sama przesłanka prowadzi do wniosku
            # przeciwnego: oświadczenia wycofujemy WŁAŚNIE dlatego, że rekord
            # trafił do kosza, więc soft-delete jest tu stanem oczekiwanym,
            # a nie powodem przerwania. Bez tego warunku gałąź WYCOFANIE
            # w `send_to_pbn()` byłaby martwym kodem, a sprzątaczka kolejki
            # (`kolejka_wyczysc_wpisy_bez_rekordow`) po cichu kasowałaby
            # zlecenia wycofania, zostawiając oświadczenia w PBN.
            #
            # Rekord skasowany TWARDO (wiersza nie ma) nadal daje False dla
            # obu operacji — bez wiersza nie odczytamy `pbn_uid`, więc nie ma
            # czego wycofywać. To świadoma, głośna porażka.
            if (
                self.operacja != self.Operacja.WYCOFANIE
                and getattr(obiekt, "deleted_at", None) is not None
            ):
                return False

            if obiekt:
                return True
        except self.content_type.model_class().DoesNotExist:
            return False

    def prepare_for_resend(self, user=None, message_suffix=""):
        """Przygotowuje obiekt do ponownej wysyłki.

        :raises AlreadyEnqueuedError: gdy wpis jest już zakończony, a dla tego
            samego rekordu istnieje INNY aktywny wpis — uaktywnienie tego
            złamałoby częściowy unikat (jeden aktywny wpis na rekord). Rekord
            i tak czeka w kolejce, więc nie dublujemy.
        """
        self.refresh_from_db()

        if self.wysylke_zakonczono is not None:
            istnieje_inny_aktywny = (
                type(self)
                .objects.filter_rekord_do_wysylki(self.rekord_do_wysylki)
                .exclude(pk=self.pk)
                .exists()
            )
            if istnieje_inny_aktywny:
                raise AlreadyEnqueuedError(
                    "dla tego rekordu istnieje już aktywny wpis w kolejce"
                )

        self.wysylke_zakonczono = None
        self.zakonczono_pomyslnie = None
        self.retry_after_user_authorised = None
        self.rodzaj_bledu = None
        self.wykluczone = False

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

    def exclude(self, msg):
        """Oznacza element jako wykluczone z eksportu (WYKLUCZONE).

        Używane dla publikacji, które z przyczyn projektowych nie mogą być eksportowane
        (np. nieobsługiwany charakter formalny, wyłączony eksport PK=0).
        To nie jest błąd - to zamierzone zachowanie systemu.
        """
        self.wysylke_zakonczono = timezone.now()
        self.zakonczono_pomyslnie = False
        self.wykluczone = True
        self.rodzaj_bledu = None  # To nie jest błąd
        self.dopisz_komunikat(msg)
        self.save()
        return SendStatus.WYKLUCZONE

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

    def _handle_retry_exception(self, exc):
        """Obsługuje wyjątki wymagające ponowienia. Zwraca SendStatus lub None."""
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

        if isinstance(exc, ResourceLockedException):
            self.dopisz_komunikat(f"{exc}, ponowiam wysyłkę za kilka minut...")
            self.save()
            return SendStatus.RETRY_LATER

        if isinstance(exc, HttpException) and exc.status_code == 423:
            # 423 = Locked (RFC 4918), blokada przejściowa — zawsze ponawiamy.
            # Pas bezpieczeństwa na wypadek, gdy pbn-client nie rozpozna
            # kształtu odpowiedzi i nie podniesie ResourceLockedException.
            self.dopisz_komunikat(
                "Zasób zablokowany w PBN (HTTP 423), ponawiam wysyłkę za kilka minut..."
            )
            self.save()
            return SendStatus.RETRY_LATER

        if isinstance(exc, StatementsResendFailedException):
            # Publikacja została wysłana do PBN (POST /repositorium OK),
            # ale synchronizacja oświadczeń (GET/DELETE/POST /v2) wyczerpała
            # retry w sync_publication. Ponawiamy po kilku minutach —
            # zwykle chwilowa niedostępność PBN.
            self.dopisz_komunikat(
                f"Synchronizacja oświadczeń nie powiodła się po wyczerpaniu prób "
                f"(PBN UID={exc.pbn_uid}): {exc.last_error}. "
                f"Ponowię wysyłkę za kilka minut..."
            )
            self.save()
            return SendStatus.RETRY_LATER

        return None

    def _handle_exclude_exception(self, exc):
        """Obsługuje wyjątki prowadzące do wykluczenia. Zwraca SendStatus lub None."""
        if isinstance(exc, CharakterFormalnyNieobslugiwanyError):
            return self.exclude(
                "Wykluczone: Charakter formalny tego rekordu nie jest ustawiony jako "
                "wysyłany do PBN. Zmień konfigurację bazy BPP, Redagowanie -> Dane "
                "systemowe -> Charaktery formalne"
            )

        if isinstance(exc, PKZeroExportDisabled):
            return self.exclude(
                "Wykluczone: Eksport prac bez punktów PK wyłączony w konfiguracji."
            )

        # CharakterFormalnyMissingPBNUID - wykluczone (brak mapowania PBN dla typu)
        if isinstance(exc, CharakterFormalnyMissingPBNUID):
            return self.exclude(
                f"Wykluczone: Charakter formalny nie ma przypisanego rodzaju PBN. {exc}"
            )

        return None

    def _handle_pbn_exception(self, exc):
        """Obsługuje wyjątki z wysyłki do PBN. Zwraca SendStatus lub None."""
        # Sprawdź wyjątki wymagające ponowienia
        result = self._handle_retry_exception(exc)
        if result is not None:
            return result

        # Sprawdź wyjątki prowadzące do wykluczenia
        result = self._handle_exclude_exception(exc)
        if result is not None:
            return result

        if isinstance(exc, AccessDeniedException):
            return self.error(
                "Brak uprawnień, załączam traceback:\n" + traceback.format_exc(),
                rodzaj=RodzajBledu.TECHNICZNY,
            )

        # WillNotExportError i podklasy (DOIorWWWMissing, LanguageMissingPBNUID, etc.)
        # PKZeroExportDisabled i CharakterFormalnyMissingPBNUID są obsłużone wcześniej
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

    def _pozyskaj_klienta_pbn(self):
        """Buduje klienta PBN dla TEGO wpisu kolejki.

        Uczelnia z FK wpisu (``self.uczelnia``) — nigdy „pierwsza z brzegu":
        dawne API uczelni domyślnej zostało trwale usunięte i jest pilnowane
        guardem ``bpp/tests/test_multihosted_get_default_guard.py``. Dla
        wpisów legacy (``uczelnia_id is None``, sprzed migracji ``0009``)
        jedyny dozwolony fallback to „jedyna-albo-głośny-błąd".

        Token: z konta PBN zamawiającego — ``get_pbn_user()`` respektuje
        ``przedstawiaj_w_pbn_jako``, więc konto techniczne (operacje
        systemowe) można podpiąć pod konto z ważnym tokenem bez zmiany kodu.
        """
        from bpp.models import Uczelnia

        pbn_user = self.zamowil.get_pbn_user()
        uczelnia = self.uczelnia or Uczelnia.objects.get_single_uczelnia_or_fail()
        return uczelnia.pbn_client(pbn_user.pbn_token)

    def withdraw_from_pbn(self):
        """Gałąź WYCOFANIE — cienkie wywołanie prymitywu.

        NIE woła klienta PBN bezpośrednio i NIE dotyka ``SentData`` — robi
        to ``wycofaj_oswiadczenia()``, wspólne z wejściem synchronicznym.
        Tu wyłącznie: pozyskanie klienta, wywołanie prymitywu i tłumaczenie
        wyniku/wyjątku na ``SendStatus``. Klasyfikacja wyjątków PBN idzie
        przez wspólne ``_handle_pbn_exception`` (ResourceLocked →
        RETRY_LATER, PraceSerwisowe → RETRY_MUCH_LATER, HTTP 423 →
        RETRY_LATER, …), czyli DOKŁADNIE tę samą tabelę co wysyłka.

        :return: SendStatus
        """
        from pbn_api.wycofanie import wycofaj_oswiadczenia

        try:
            client = self._pozyskaj_klienta_pbn()
        except Exception as exc:
            zaloguj_polkniety_wyjatek(
                "Nie udało się zbudować klienta PBN do wycofania oświadczeń "
                f"(PBN_Export_Queue pk={self.pk})",
                logger=logger,
                do_rollbar=False,  # Rollbar w _handle_pbn_exception
            )
            return self._handle_pbn_exception(exc)

        try:
            wynik = wycofaj_oswiadczenia(
                self.rekord_do_wysylki, client, uczelnia=self.uczelnia
            )
        except Exception as exc:
            zaloguj_polkniety_wyjatek(
                "Błąd podczas wycofywania oświadczeń z PBN z kolejki eksportu "
                f"(PBN_Export_Queue pk={self.pk})",
                logger=logger,
                do_rollbar=False,  # Rollbar w _handle_pbn_exception
            )
            return self._handle_pbn_exception(exc)

        # POMINIETO (rekord bez PBN UID) też kończy wpis sukcesem: nic nie
        # poszło do PBN, więc stan docelowy jest osiągnięty. To gate
        # obronny — `zakolejkuj_wycofanie` takich wpisów w ogóle nie tworzy.
        self.wysylke_zakonczono = timezone.now()
        self.zakonczono_pomyslnie = True
        self.dopisz_komunikat(wynik.komunikat)
        self.save()
        return SendStatus.FINISHED_OKAY

    def _zajmij_atomowo(self):
        """Atomowo zajmij wpis do wysyłki (zabezpieczenie przed dwoma workerami).

        ``select_for_update(skip_locked=True)`` blokuje wiersz na czas
        krótkiej transakcji (sama zmiana statusu, NIE długi request HTTP do
        PBN). Gdy inny worker już trzyma wiersz — pomijamy (``skip_locked``),
        zwracając ``False``. To działa niezależnie od backendu cache (w prod
        Redis-owy ``cache.add`` już serializuje po pk, ale na testach cache to
        no-op DummyCache — wtedy to jedyny realny zamek).

        :return: True gdy zajęto wpis, False gdy trzyma go ktoś inny albo
            został w międzyczasie zakończony.
        """
        with transaction.atomic():
            zablokowany = (
                type(self)
                .objects.select_for_update(skip_locked=True)
                .filter(pk=self.pk, wysylke_zakonczono__isnull=True)
                .first()
            )
            if zablokowany is None:
                return False

            zablokowany.wysylke_podjeto = timezone.now()
            if zablokowany.retry_after_user_authorised:
                zablokowany.retry_after_user_authorised = None
            zablokowany.ilosc_prob += 1
            zablokowany.save(
                update_fields=[
                    "wysylke_podjeto",
                    "retry_after_user_authorised",
                    "ilosc_prob",
                ]
            )
        self.refresh_from_db()
        return True

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

        if not self._zajmij_atomowo():
            # Inny worker zdążył zająć ten wiersz (row lock) albo go zakończył.
            # On dokończy — bieżące zadanie kończymy bez ponawiania.
            return SendStatus.LOCKED_ELSEWHERE

        # Rozgałęzienie PO zajęciu wiersza: wycofanie dziedziczy za darmo
        # licznik `ilosc_prob`, znacznik `wysylke_podjeto` i ochronę przed
        # dwoma workerami. Ścieżka WYSYLKA niżej — bez zmian.
        if self.operacja == self.Operacja.WYCOFANIE:
            return self.withdraw_from_pbn()

        from bpp.admin.helpers.pbn_api.cli import sprobuj_wyslac_do_pbn_celery

        try:
            sent_data, notificator = sprobuj_wyslac_do_pbn_celery(
                user=self.zamowil.get_pbn_user(),
                obj=self.rekord_do_wysylki,
                force_upload=True,
                uczelnia=self.uczelnia,
            )
        except Exception as exc:
            zaloguj_polkniety_wyjatek(
                "Błąd podczas wysyłki rekordu do PBN z kolejki eksportu "
                f"(PBN_Export_Queue pk={self.pk})",
                logger=logger,
                do_rollbar=False,  # Rollbar dla nieobsłużonych w _handle_pbn_exception
            )
            return self._handle_pbn_exception(exc)

        if sent_data is None:
            return self.error(
                "Wystąpił błąd, dane nie zostały wysłane, wyjaśnienie poniżej.\n\n"
                + "\n".join(notificator),
                rodzaj=RodzajBledu.MERYTORYCZNY,
            )

        return self._handle_successful_send(sent_data, notificator)
