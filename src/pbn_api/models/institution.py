from django.core.exceptions import MultipleObjectsReturned
from django.db import models, transaction
from django.db.models import JSONField

from ..exceptions import HttpException, StatementDeletionError
from .base import BasePBNMongoDBModel

from django.utils.functional import cached_property

from bpp.models import Typ_Odpowiedzialnosci


class Institution(BasePBNMongoDBModel):
    class Meta:
        verbose_name = "Instytucja w PBN API"
        verbose_name_plural = "Instytucje w PBN API"

    name = models.TextField(null=True, blank=True, db_index=True)
    addressCity = models.TextField(null=True, blank=True, db_index=True)
    addressStreet = models.TextField(null=True, blank=True, db_index=True)
    addressStreetNumber = models.TextField(null=True, blank=True, db_index=True)
    addressPostalCode = models.TextField(null=True, blank=True, db_index=True)
    polonUid = models.TextField(null=True, blank=True, db_index=True)

    pull_up_on_save = [
        "name",
        "addressCity",
        "addressStreet",
        "addressStreetNumber",
        "addressPostalCode",
        "polonUid",
    ]

    def __str__(self):
        parent = self.value_or_none("object", "rootId")
        if parent:
            if parent == self.pk:
                parent = None
            else:
                try:
                    parent = Institution.objects.get(mongoId=parent)
                    parent = parent.name
                except Institution.DoesNotExist:
                    parent = None

        if parent is not None:
            parent = f" => {parent}"
        ret = (
            f"{self.name} {parent or ''}, "
            f"{self.addressCity or ''}, "
            f"{self.addressStreet or ''} {self.addressStreetNumber or ''} "
            f"{self.value_or_none('objects', 'email') or ''} "
            f"{self.value_or_none('objects', 'website') or ''} "
            f"(ID: {self.mongoId})"
        )
        while ret.find("  ") != -1:
            ret = ret.replace("  ", " ")
        ret = ret.replace(" ,", ",")
        while ret.find(",,") != -1:
            ret = ret.replace(",,", ",")
        ret = ret.replace(", (", " (")
        return ret

    @cached_property
    def rekord_w_bpp(self):
        from bpp.models import Jednostka, Uczelnia

        try:
            return Jednostka.objects.get(pbn_uid_id=self.pk)
        except Jednostka.DoesNotExist:
            try:
                return Uczelnia.objects.get(pbn_uid_id=self.pk)
            except Uczelnia.DoesNotExist:
                pass


class PublikacjaInstytucji(models.Model):
    insPersonId = models.ForeignKey("pbn_api.Scientist", on_delete=models.CASCADE)
    institutionId = models.ForeignKey(Institution, on_delete=models.CASCADE)
    publicationId = models.ForeignKey("pbn_api.Publication", on_delete=models.CASCADE)
    publicationType = models.CharField(max_length=50, null=True, blank=True)
    userType = models.CharField(max_length=50, null=True, blank=True)
    publicationVersion = models.UUIDField(null=True, blank=True)
    publicationYear = models.PositiveSmallIntegerField(null=True, blank=True)
    snapshot = JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "Publikacja instytucji"
        verbose_name_plural = "Publikacje instytucji"


class OswiadczenieInstytucji(models.Model):
    primary_key = models.AutoField(primary_key=True, editable=False)
    id = models.UUIDField("UID w PBN", null=True, blank=True)
    addedTimestamp = models.DateField()
    statedTimestamp = models.DateField(null=True, blank=True)
    area = models.PositiveSmallIntegerField(null=True, blank=True)
    inOrcid = models.BooleanField()
    institutionId = models.ForeignKey(Institution, on_delete=models.CASCADE)
    personId = models.ForeignKey("pbn_api.Scientist", on_delete=models.CASCADE)
    publicationId = models.ForeignKey("pbn_api.Publication", on_delete=models.CASCADE)
    type = models.CharField(max_length=50)
    disciplines = models.JSONField(blank=True, null=True)

    def get_bpp_publication(self):
        from bpp.models import (
            Praca_Doktorska,
            Praca_Habilitacyjna,
            Wydawnictwo_Ciagle,
            Wydawnictwo_Zwarte,
        )

        for klass in (
            Wydawnictwo_Ciagle,
            Wydawnictwo_Zwarte,
            Praca_Doktorska,
            Praca_Habilitacyjna,
        ):
            try:
                return klass.objects.get(pbn_uid_id=self.publicationId_id)
            except klass.MultipleObjectsReturned:
                ret = klass.objects.filter(pbn_uid_id=self.publicationId_id).first()
                print(
                    f"XXX DUPLIKAT! Dwie prace mają PBN UID {self.publicationId_id}, "
                    f"zwracam pierwszą {ret.tytul_oryginalny}!"
                )
            except klass.DoesNotExist:
                pass

    def get_typ_odpowiedzialnosci(self):
        if self.type == "EDITOR":
            return Typ_Odpowiedzialnosci.objects.get(nazwa="redaktor")
        elif self.type == "AUTHOR":
            return Typ_Odpowiedzialnosci.objects.get(nazwa="autor")
        else:
            raise NotImplementedError(self.type)

    def get_bpp_autor(self):
        from bpp.models import Autor

        try:
            return Autor.objects.get(pbn_uid_id=self.personId_id)
        except Autor.DoesNotExist:
            return

    def get_bpp_wa(self):
        """Zwróć Wydawnictwo_*_Autor"""
        pub = self.get_bpp_publication()
        if pub is None:
            return

        aut = self.get_bpp_autor()
        if aut is None:
            return

        try:
            return pub.autorzy_set.get(autor=aut)
        except MultipleObjectsReturned:
            return pub.autorzy_set.get(
                autor=aut,
                typ_odpowiedzialnosci=self.get_typ_odpowiedzialnosci(),
            )

    def get_bpp_discipline(self):
        from bpp.models import Dyscyplina_Naukowa

        if self.disciplines is None:
            return

        return Dyscyplina_Naukowa.objects.get(nazwa=self.disciplines["name"])

    class Meta:
        verbose_name = "Oświadczenie instytucji"
        verbose_name_plural = "Oświadczenia instytucji"

    def sprobuj_skasowac_z_pbn(self, request=None, pbn_client=None):
        from bpp.models import Uczelnia

        if pbn_client is None:
            uczelnia = Uczelnia.objects.get_for_request(request)
            if uczelnia is None:
                raise Uczelnia.DoesNotExist

            pbn_client = uczelnia.pbn_client(request.user.pbn_token)

        try:
            pbn_client.delete_publication_statement(
                self.publicationId_id, self.personId_id, self.type
            )
        except HttpException as e:
            raise StatementDeletionError(e.status_code, e.url, e.content)

    @transaction.atomic
    def delete(self, *args, **kw):
        # Jeżeli usunięte zostało jakiekolwiek oświadczenie to automatycznie dane SentData przestają
        # być aktualne, a system się na nich opiera. Zatem w tej sytuacji, kasujemy również
        # wysłane dane:
        from pbn_api.models import SentData

        SentData.objects.filter(pbn_uid_id=self.publicationId_id).delete(*args, **kw)
        return super().delete(*args, **kw)
