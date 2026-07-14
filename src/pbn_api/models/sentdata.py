from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import JSONField
from django.utils import timezone
from pbn_client.dict_utils import compare_dicts

from bpp import const
from bpp.models import LinkDoPBNMixin


class SentDataManager(models.Manager):
    # Multi-hosted (audyt uczelnia, Track 4): kluczem wysyłki jest trójka
    # ``(object_id, content_type, uczelnia)``. Dwie uczelnie wysyłające ten
    # sam rekord BPP do swoich profili PBN dostają DWA niezależne wiersze.
    # Parametr ``uczelnia`` ma default ``None`` (zachowanie globalne — lookup
    # bez zawężania), ale realni callerzy ZAWSZE go podają (``self.uczelnia``
    # / ``client.uczelnia`` / ``entry.uczelnia``). NULL = legacy/untagged.
    # UWAGA: gdy istnieją ≥2 wiersze dla ``(object_id, content_type)``, lookup
    # BEZ ``uczelnia`` rzuci ``MultipleObjectsReturned`` — dlatego wszystkie
    # call-sites zostały zmienione atomowo.
    def get_for_rec(self, rec, uczelnia=None):
        qs = self.filter(
            object_id=rec.pk, content_type=ContentType.objects.get_for_model(rec)
        )
        if uczelnia is not None:
            qs = qs.filter(uczelnia=uczelnia)
        return qs.get()

    def check_if_needed(self, rec, data: dict, uczelnia=None):
        """Legacy method - kept for backward compatibility"""
        try:
            sd = self.get_for_rec(rec, uczelnia)
        except SentData.DoesNotExist:
            return True

        if sd.data_sent != data:
            return True

        if not sd.uploaded_okay:
            return True

        return False

    def check_if_upload_needed(self, rec, data: dict, uczelnia=None):
        """Check if upload needed based on SUCCESSFUL submissions only"""
        try:
            sd = self.get_for_rec(rec, uczelnia)
            # Only skip if data matches AND was successfully submitted
            if (not compare_dicts(sd.data_sent, data)) and sd.submitted_successfully:
                return False
        except SentData.DoesNotExist:
            pass
        return True

    def create_or_update_before_upload(
        self, rec, data: dict, api_url="", uczelnia=None
    ):
        """Create or update SentData record before API call"""
        try:
            sd = self.get_for_rec(rec, uczelnia)
            # Reset fields for new attempt
            sd.submitted_successfully = False
            sd.submitted_at = timezone.now()
            sd.uploaded_okay = False
            sd.api_response_status = ""
            sd.exception = ""
            sd.data_sent = data  # Update data if changed
            sd.api_url = api_url
            sd.save()
            return sd
        except SentData.DoesNotExist:
            # Create new record if none exists
            return self.create(
                object=rec,
                data_sent=data,
                submitted_successfully=False,
                submitted_at=timezone.now(),
                uploaded_okay=False,
                api_url=api_url,
                uczelnia=uczelnia,
            )

    def mark_as_successful(
        self, rec, pbn_uid_id=None, api_response_status="", uczelnia=None
    ):
        """Mark existing record as successful after API call"""
        sd = self.get_for_rec(rec, uczelnia)
        sd.submitted_successfully = True
        sd.uploaded_okay = True
        sd.pbn_uid_id = pbn_uid_id
        sd.api_response_status = api_response_status
        sd.exception = ""
        sd.save()

    def mark_as_failed(self, rec, exception="", api_response_status="", uczelnia=None):
        """Mark existing record as failed after API call"""
        sd = self.get_for_rec(rec, uczelnia)
        sd.submitted_successfully = False
        sd.uploaded_okay = False
        sd.exception = str(exception) if exception else ""
        sd.api_response_status = api_response_status
        sd.save()

    def updated(
        self,
        rec,
        data: dict,
        pbn_uid_id=None,
        uploaded_okay=True,
        exception="",
        uczelnia=None,
    ):
        """Legacy method - kept for backward compatibility"""
        try:
            sd = self.get_for_rec(rec, uczelnia)
        except SentData.DoesNotExist:
            self.create(
                object=rec,
                data_sent=data,
                uploaded_okay=uploaded_okay,
                pbn_uid_id=pbn_uid_id,
                exception=exception,
                submitted_successfully=uploaded_okay,
                submitted_at=timezone.now() if uploaded_okay else None,
                uczelnia=uczelnia,
            )
            return

        sd.data_sent = data
        sd.uploaded_okay = uploaded_okay
        sd.exception = exception
        sd.pbn_uid_id = pbn_uid_id
        sd.submitted_successfully = uploaded_okay
        if uploaded_okay and not sd.submitted_at:
            sd.submitted_at = timezone.now()
        sd.save()

    def fee_upload_needed(self, rec, fee: dict, uczelnia=None):
        """Czy trzeba wysłać opłatę do PBN?

        Opłata leci osobnym endpointem (institution-profile fee) i — dla
        ścieżki repozytoryjnej — NIE jest częścią payloadu publikacji ani
        jego porównania. Śledzimy ją osobno (``fee_sent``), żeby wykryć
        samą zmianę opłaty (FD#301). True gdy: brak śladu / poprzednia
        wysyłka opłaty nie powiodła się / opłata się zmieniła.
        """
        try:
            sd = self.get_for_rec(rec, uczelnia)
        except SentData.DoesNotExist:
            return True

        if not sd.fee_uploaded_okay:
            return True

        return sd.fee_sent != fee

    def record_fee_sent(self, rec, fee: dict, uczelnia=None, uploaded_okay=True):
        """Zapamiętaj ostatnio wysłaną opłatę (create-or-update).

        Zwykle wiersz ``SentData`` już istnieje (rekord był wcześniej
        wysłany). Gdy nie istnieje — tworzymy go z pustym ``data_sent``
        (sama opłata, bez śladu wysyłki payloadu publikacji).
        """
        try:
            sd = self.get_for_rec(rec, uczelnia)
        except SentData.DoesNotExist:
            return self.create(
                object=rec,
                data_sent={},
                uploaded_okay=False,
                submitted_successfully=False,
                fee_sent=fee,
                fee_uploaded_okay=uploaded_okay,
                uczelnia=uczelnia,
            )

        sd.fee_sent = fee
        sd.fee_uploaded_okay = uploaded_okay
        sd.save(update_fields=["fee_sent", "fee_uploaded_okay", "last_updated_on"])
        return sd

    def ids_for_model(self, model, uczelnia=None):
        qs = self.filter(content_type=ContentType.objects.get_for_model(model))
        if uczelnia is not None:
            qs = qs.filter(uczelnia=uczelnia)
        return qs

    def bad_uploads(self, model, uczelnia=None):
        return (
            self.ids_for_model(model, uczelnia)
            .filter(uploaded_okay=False)
            .values_list("object_id", flat=True)
            .distinct()
        )


class SentData(LinkDoPBNMixin, models.Model):
    url_do_pbn = const.LINK_PBN_DO_PUBLIKACJI
    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField(db_index=True)

    object = GenericForeignKey()

    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sent_data",
    )

    data_sent = JSONField("Wysłane dane")
    last_updated_on = models.DateTimeField("Data operacji", auto_now=True)

    # Ślad ostatnio wysłanej opłaty (institution-profile fee). Opłata leci
    # osobnym endpointem i dla ścieżki repozytoryjnej wypada z payloadu
    # publikacji, więc jej zmiany nie wykryłoby porównanie ``data_sent``.
    # Osobny ślad pozwala wykryć samą zmianę opłaty i ją ponowić (FD#301).
    fee_sent = JSONField("Wysłane dane o opłacie", null=True, blank=True)
    fee_uploaded_okay = models.BooleanField(
        "Opłatę wysłano poprawnie", default=False, db_index=True
    )

    uploaded_okay = models.BooleanField(
        "Wysłano poprawnie", default=True, db_index=True
    )
    exception = models.TextField("Kod błędu", max_length=65535, blank=True, default="")

    # New fields for success tracking
    submitted_successfully = models.BooleanField(
        "Wysłano pomyślnie",
        default=False,
        db_index=True,
        help_text="True gdy API call zakończył się sukcesem",
    )
    submitted_at = models.DateTimeField(
        "Data wysyłki",
        null=True,
        blank=True,
        help_text="Kiedy dane zostały wysłane do PBN",
    )
    api_response_status = models.TextField(
        "Status odpowiedzi API",
        blank=True,
        default="",
        help_text="Odpowiedź z PBN API",
    )
    api_url = models.CharField(
        "URL endpointu PBN",
        max_length=512,
        blank=True,
        default="",
        help_text="Pełny URL (domena + ścieżka), do którego wysłano dane",
    )

    pbn_uid = models.ForeignKey(
        "pbn_api.Publication",
        verbose_name="Publikacja z PBN",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    typ_rekordu = models.CharField(max_length=50, blank=True, default="")

    objects = SentDataManager()

    class Meta:
        verbose_name = "Informacja o wysłanych danych"
        verbose_name_plural = "Informacje o wysłanych danych"

    object.verbose_name = "Rekord"

    def __str__(self):
        return (
            f"Informacja o wysłanych do PBN danych dla rekordu ({self.content_type_id},{self.object_id}) "
            f"z dnia {self.last_updated_on} (status: {'OK' if self.uploaded_okay else 'ERR'})"
        )

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if update_fields and "data_sent" in update_fields:
            if self.typ_rekordu != self.data_sent.get("type"):
                update_fields.append("typ_rekordu")

        self.typ_rekordu = self.data_sent.get("type") or ""
        return super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def link_do_pbn_wartosc_id(self):
        return self.pbn_uid_id

    def rekord_w_bpp(self):
        try:
            return self.object
        except ObjectDoesNotExist:
            pass
