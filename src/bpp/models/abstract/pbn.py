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

    def link_do_pi(self):
        pbn_uid_id = self.link_do_pbn_wartosc_id()

        if not pbn_uid_id:
            return

        from pbn_api.models import PublikacjaInstytucji_V2

        versionHash = None

        try:
            # For BPP models (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte) use pbn_uid_id
            # For Publication models use pk directly
            if hasattr(self, "pbn_uid"):
                lookup_id = self.pbn_uid_id
            else:
                lookup_id = self.pk

            uuid = PublikacjaInstytucji_V2.objects.get(objectId_id=lookup_id).pk

            from bpp import const
            from bpp.models import Uczelnia

            uczelnia = Uczelnia.objects.get_default()
            if uczelnia is not None:
                return const.LINK_PI_ADD_STATEMENTS.format(
                    pbn_api_root=uczelnia.pbn_api_root,
                    pbn_uid_id=pbn_uid_id,
                    uuid=uuid,
                )

        except PublikacjaInstytucji_V2.DoesNotExist:
            try:
                # bpp.models.Wydawnictwo_Ciagle, bpp.models.Wydawnictwo_Zwarte
                current_version = self.pbn_uid.current_version
                if current_version is not None:
                    # w testach moze tak byc, ze bedzie None
                    versionHash = current_version.get("versionHash", None)
            except AttributeError:
                try:
                    # pbn_api.models.OswiadczenieInstytucji
                    versionHash = self.publicationId.current_version.get(
                        "versionHash", None
                    )
                except AttributeError:
                    # pbn_api.models.Publication
                    versionHash = self.current_version.get("versionHash", None)

        if versionHash is None:
            return

        from bpp import const
        from bpp.models import Uczelnia

        uczelnia = Uczelnia.objects.get_default()
        if uczelnia is not None:
            return const.LINK_PI_WSZYSTKO.format(
                pbn_api_root=uczelnia.pbn_api_root,
                pbn_uid_id=pbn_uid_id,
                versionHash=versionHash,
            )


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
