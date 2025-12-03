"""
Modele abstrakcyjne związane z PBN (Polska Bibliografia Naukowa).
"""

from django.db import models

from bpp import const


class LinkDoPBNMixin:
    url_do_pbn = None
    atrybut_dla_url_do_pbn = "pbn_uid_id"

    def link_do_pbn_wartosc_id(self):
        return getattr(self, self.atrybut_dla_url_do_pbn)

    def link_do_pbn(self):
        assert self.url_do_pbn, "Określ parametr self.url_do_pbn"

        from bpp.models import Uczelnia

        uczelnia = Uczelnia.objects.get_default()
        if uczelnia is not None:
            return self.url_do_pbn.format(
                pbn_api_root=uczelnia.pbn_api_root,
                pbn_uid_id=self.link_do_pbn_wartosc_id(),
            )

    def _get_lookup_id(self):
        """Get the lookup ID for PublikacjaInstytucji_V2 query.

        For BPP models (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte) use pbn_uid_id.
        For Publication models use pk directly.
        """
        if hasattr(self, "pbn_uid"):
            return self.pbn_uid_id
        return self.pk

    def _report_and_get_first_duplicate(self, lookup_id, duplicates):
        """Report duplicate PublikacjaInstytucji_V2 records and return the first UUID."""
        msg = (
            f"Znaleziono duplikaty PublikacjaInstytucji_V2 dla "
            f"objectId_id={lookup_id}. Duplikaty: {duplicates}. Obiekt: {self}"
        )
        import rollbar
        from django.core.mail import mail_admins

        rollbar.report_message(
            msg,
            level="warning",
            extra_data={
                "lookup_id": str(lookup_id),
                "self_class": self.__class__.__name__,
                "self_pk": getattr(self, "pk", None),
                "duplicates": duplicates,
            },
        )
        mail_admins("Duplikaty PublikacjaInstytucji_V2", msg, fail_silently=True)
        return duplicates[0][0]

    def _get_version_hash_from_fallback(self):
        """Get versionHash from various model attributes as fallback."""
        try:
            # bpp.models.Wydawnictwo_Ciagle, bpp.models.Wydawnictwo_Zwarte
            current_version = self.pbn_uid.current_version
            if current_version is not None:
                # w testach moze tak byc, ze bedzie None
                return current_version.get("versionHash", None)
            # Publication exists but has no current version (empty versions list)
            return None
        except AttributeError:
            pass

        try:
            # pbn_api.models.OswiadczenieInstytucji
            return self.publicationId.current_version.get("versionHash", None)
        except AttributeError:
            pass

        # pbn_api.models.Publication
        return self.current_version.get("versionHash", None)

    def _format_link_pi(self, pbn_uid_id, uuid=None, versionHash=None):
        """Format the link to PI based on available data."""
        from bpp.models import Uczelnia

        uczelnia = Uczelnia.objects.get_default()
        if uczelnia is None:
            return None

        if uuid is not None:
            return const.LINK_PI_ADD_STATEMENTS.format(
                pbn_api_root=uczelnia.pbn_api_root,
                pbn_uid_id=pbn_uid_id,
                uuid=uuid,
            )

        if versionHash is not None:
            return const.LINK_PI_WSZYSTKO.format(
                pbn_api_root=uczelnia.pbn_api_root,
                pbn_uid_id=pbn_uid_id,
                versionHash=versionHash,
            )

        return None

    def link_do_pi(self):
        pbn_uid_id = self.link_do_pbn_wartosc_id()

        if not pbn_uid_id:
            return

        from pbn_api.models import PublikacjaInstytucji_V2

        lookup_id = self._get_lookup_id()

        try:
            uuid = PublikacjaInstytucji_V2.objects.get(objectId_id=lookup_id).pk
            return self._format_link_pi(pbn_uid_id, uuid=uuid)
        except PublikacjaInstytucji_V2.MultipleObjectsReturned:
            duplicates = list(
                PublikacjaInstytucji_V2.objects.filter(
                    objectId_id=lookup_id
                ).values_list("pk", "created_on")
            )
            uuid = self._report_and_get_first_duplicate(lookup_id, duplicates)
            return self._format_link_pi(pbn_uid_id, uuid=uuid)
        except PublikacjaInstytucji_V2.DoesNotExist:
            versionHash = self._get_version_hash_from_fallback()
            return self._format_link_pi(pbn_uid_id, versionHash=versionHash)


class ModelZPBN_UID(LinkDoPBNMixin, models.Model):
    pbn_uid = models.OneToOneField(
        "pbn_api.Publication",
        verbose_name=const.PBN_UID_FIELD_LABEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        unique=True,
    )

    url_do_pbn = const.LINK_PBN_DO_PUBLIKACJI

    class Meta:
        abstract = True

    def get_pbn_uuid(self):
        """Nazwa tej funkcji to NIE literówka; alias to PBN UID V2

        get_pbn_uid_v2
        get_pbn_uuid_v2

        Ta funkcja próbuje zwrócić PBN UUID, pod warunkiem, że został zaciągnięty z API oświadczeń instytucji
        V2. Oraz, pod warunkiem, że self.pbn_uid_id jest ustawione."""

        if self.pbn_uid_id is None:
            return

        from pbn_api.models.publikacja_instytucji import PublikacjaInstytucji_V2

        publicationUuid = PublikacjaInstytucji_V2.objects.filter(
            objectId=self.pbn_uid_id
        ).values_list("uuid", flat=True)[:1]

        if publicationUuid:
            return publicationUuid[0]
