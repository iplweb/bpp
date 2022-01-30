from django.db import models

from import_common.core import matchuj_publikacje
from import_common.normalization import normalize_isbn
from .base import BasePBNMongoDBModel

from django.utils.functional import cached_property

from bpp import const
from bpp.models.abstract import LinkDoPBNMixin

STATUS_ACTIVE = "ACTIVE"


class Publication(LinkDoPBNMixin, BasePBNMongoDBModel):
    url_do_pbn = const.LINK_PBN_DO_PUBLIKACJI
    atrybut_dla_url_do_pbn = "pk"

    class Meta:
        verbose_name = "Publikacja z PBN API"
        verbose_name_plural = "Publikacje z PBN API"
        unique_together = ["mongoId", "title", "isbn", "doi", "publicUri"]

    title = models.TextField(db_index=True, null=True, blank=True)
    doi = models.TextField(db_index=True, null=True, blank=True)
    publicUri = models.TextField(db_index=True, null=True, blank=True)
    isbn = models.TextField(db_index=True, null=True, blank=True)
    year = models.IntegerField(db_index=True, null=True, blank=True)

    # Nazwy pól wyciaganych "na wierzch" do pól obiektu
    # ze słownika JSONa (pole 'values')
    pull_up_on_save = ["title", "doi", "publicUri", "isbn", "year"]

    def type(self):
        return self.value("object", "type", return_none=True)

    def volume(self):
        return self.value("object", "volume", return_none=True)

    @cached_property
    def journal(self):
        return self.value_or_none("object", "journal")

    def pull_up_year(self):
        year = self.value_or_none("object", "year")
        if year is None:
            year = self.value_or_none("object", "book", "year")
        return year

    def pull_up_isbn(self):
        isbn = self.value_or_none("object", "isbn")
        if isbn is None:
            isbn = self.value_or_none("object", "book", "isbn")
        return normalize_isbn(isbn)

    def pull_up_publicUri(self):
        publicUri = self.value_or_none("object", "publicUri")
        if publicUri is None:
            publicUri = self.value_or_none("object", "book", "publicUri")
        return publicUri

    def policz_autorow(self):
        ret = 0

        for elem in self.autorzy:
            ret += len(self.autorzy[elem])
        return ret

    @cached_property
    def autorzy(self):
        ret = {}
        for elem in ["authors", "editors", "translators", "translationEditors"]:
            elem_dct = self.value_or_none("object", elem)
            if elem_dct:
                ret[elem] = elem_dct
        return ret

    @cached_property
    def journal_id(self):
        return self.value_or_none("object", "journal", "id")

    def matchuj_zrodlo_do_rekordu_bpp(self):
        if self.journal_id is not None:
            from bpp.models.zrodlo import Zrodlo

            return Zrodlo.objects.filter(pbn_uid_id=self.journal_id).first()

    def matchuj_do_rekordu_bpp(self):
        from bpp.models.cache import Rekord

        return matchuj_publikacje(
            Rekord,
            title=self.title,
            year=self.year,
            doi=self.doi,
            public_uri=self.publicUri,
            isbn=self.isbn,
            zrodlo=self.matchuj_zrodlo_do_rekordu_bpp(),
        )

    @cached_property
    def rekord_w_bpp(self):
        from bpp.models.cache import Rekord

        try:
            return Rekord.objects.get(pbn_uid_id=self.pk)
        except Rekord.MultipleObjectsReturned:
            return ";; ".join(
                [x.tytul_oryginalny for x in Rekord.objects.filter(pbn_uid_id=self.pk)]
            )
        except Rekord.DoesNotExist:
            pass

        return self.matchuj_do_rekordu_bpp()

    def __str__(self):
        ret = f"{self.title or self.value_or_none('object', 'title')}"
        if self.year:
            ret += f", {self.year}"
        if self.doi:
            ret += f", {self.doi}"
        return ret
