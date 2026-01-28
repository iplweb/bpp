import logging

from django.core.exceptions import MultipleObjectsReturned
from django.db import models, transaction

from bpp.models import LinkDoPBNMixin, Typ_Odpowiedzialnosci

from ..exceptions import (
    BPPAutorNotFound,
    BPPAutorPublicationLinkNotFound,
    BPPPublicationNotFound,
    HttpException,
    StatementDeletionError,
)

logger = logging.getLogger(__name__)


class OswiadczenieInstytucji(LinkDoPBNMixin, models.Model):
    atrybut_dla_url_do_pbn = "publicationId_id"

    primary_key = models.AutoField(primary_key=True, editable=False)
    id = models.UUIDField("UID w PBN", null=True, blank=True)
    addedTimestamp = models.DateField()
    statedTimestamp = models.DateField(null=True, blank=True)
    area = models.PositiveSmallIntegerField(null=True, blank=True)
    inOrcid = models.BooleanField()
    institutionId = models.ForeignKey("pbn_api.Institution", on_delete=models.CASCADE)
    personId = models.ForeignKey("pbn_api.Scientist", on_delete=models.CASCADE)
    publicationId = models.ForeignKey("pbn_api.Publication", on_delete=models.CASCADE)
    type = models.CharField(max_length=50)
    disciplines = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name = "Oświadczenie instytucji"
        verbose_name_plural = "Oświadczenia instytucji"

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
        from import_common.normalization import normalize_nazwisko_do_porownania

        # 1. Próba po pbn_uid_id
        try:
            return Autor.objects.get(pbn_uid_id=self.personId_id)
        except Autor.DoesNotExist:
            pass

        # 2. Próba po ORCID (jeśli naukowiec PBN ma ORCID)
        if self.personId.orcid:
            try:
                return Autor.objects.get(orcid=self.personId.orcid)
            except (Autor.DoesNotExist, Autor.MultipleObjectsReturned):
                pass

        # 3. Próba po imieniu i nazwisku (case-insensitive)
        try:
            return Autor.objects.get(
                nazwisko__iexact=self.personId.lastName,
                imiona__iexact=self.personId.name,
            )
        except (Autor.DoesNotExist, Autor.MultipleObjectsReturned):
            pass

        # 4. Znormalizowane porównanie (polskie znaki diakrytyczne, myślniki)
        pbn_nazwisko_norm = normalize_nazwisko_do_porownania(self.personId.lastName)
        pbn_imiona_norm = normalize_nazwisko_do_porownania(self.personId.name)

        matching_autorzy = []
        for autor in Autor.objects.all().iterator():
            if (
                normalize_nazwisko_do_porownania(autor.nazwisko) == pbn_nazwisko_norm
                and normalize_nazwisko_do_porownania(autor.imiona) == pbn_imiona_norm
            ):
                matching_autorzy.append(autor)

        if len(matching_autorzy) == 1:
            autor = matching_autorzy[0]
            logger.warning(
                f"NORMALIZED MATCH: PBN '{self.personId.lastName} "
                f"{self.personId.name}' -> BPP '{autor.nazwisko} {autor.imiona}'"
            )
            return autor

        if len(matching_autorzy) > 1:
            logger.warning(
                f"NORMALIZED MATCH AMBIGUOUS: PBN '{self.personId.lastName} "
                f"{self.personId.name}' matches {len(matching_autorzy)} authors"
            )

        return None

    def get_bpp_wa_raises(self):
        """Zwróć Wydawnictwo_*_Autor lub podnieś wyjątek z informacją co zawiodło."""
        pub = self.get_bpp_publication()
        if pub is None:
            raise BPPPublicationNotFound(
                f"Publikacja PBN {self.publicationId_id} nie ma odpowiednika w BPP"
            )

        aut = self.get_bpp_autor()
        if aut is None:
            raise BPPAutorNotFound(
                f"Naukowiec PBN {self.personId_id} nie ma odpowiednika w BPP"
            )

        try:
            return pub.autorzy_set.get(autor=aut)
        except pub.autorzy_set.model.DoesNotExist as err:
            raise BPPAutorPublicationLinkNotFound(
                f"Autor {aut} nie jest powiązany z publikacją {pub}"
            ) from err
        except MultipleObjectsReturned:
            return pub.autorzy_set.get(
                autor=aut,
                typ_odpowiedzialnosci=self.get_typ_odpowiedzialnosci(),
            )

    def get_bpp_wa(self):
        """Zwróć Wydawnictwo_*_Autor lub None (kompatybilność wsteczna)."""
        try:
            return self.get_bpp_wa_raises()
        except (
            BPPPublicationNotFound,
            BPPAutorNotFound,
            BPPAutorPublicationLinkNotFound,
        ):
            return None

    def get_bpp_discipline(self):
        from bpp.models import Dyscyplina_Naukowa

        if self.disciplines is None:
            return

        return Dyscyplina_Naukowa.objects.get(nazwa=self.disciplines["name"])

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
            raise StatementDeletionError(e.status_code, e.url, e.content) from e

    @transaction.atomic
    def delete(self, *args, **kw):
        # Jeżeli usunięte zostało jakiekolwiek oświadczenie to automatycznie dane SentData przestają
        # być aktualne, a system się na nich opiera. Zatem w tej sytuacji, kasujemy również
        # wysłane dane:
        from pbn_api.models import SentData

        SentData.objects.filter(pbn_uid_id=self.publicationId_id).delete(*args, **kw)
        return super().delete(*args, **kw)
