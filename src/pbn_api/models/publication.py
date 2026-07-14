from django.db import models
from django.utils.functional import cached_property
from pbn_client import normalize_author_name

from bpp import const
from bpp.models.abstract import LinkDoPBNMixin
from import_common.core import matchuj_publikacje
from import_common.normalization import normalize_isbn

from .base import BasePBNMongoDBModel

STATUS_ACTIVE = "ACTIVE"


class Publication(LinkDoPBNMixin, BasePBNMongoDBModel):
    url_do_pbn = const.LINK_PBN_DO_PUBLIKACJI
    atrybut_dla_url_do_pbn = "pk"

    class Meta:
        verbose_name = "Publikacja z PBN API"
        verbose_name_plural = "Publikacje z PBN API"
        unique_together = ["mongoId", "title", "isbn", "doi", "publicUri"]

    title = models.TextField(db_index=True, blank=True, default="")
    doi = models.TextField(blank=True, default="")
    publicUri = models.TextField(blank=True, default="")
    isbn = models.TextField(db_index=True, blank=True, default="")
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

    @cached_property
    def book(self):
        """Rodzic (książka) rozdziału, tak jak PBN go osadza w JSON-ie pod
        ``object.book``. Analogiczne do ``journal`` dla artykułów."""
        return self.value_or_none("object", "book")

    @cached_property
    def book_title(self):
        """Tytuł wydawnictwa nadrzędnego z PBN (``object.book.title``),
        wystawiony tak, by szablon opisu bibliograficznego mógł go wyrenderować
        zwykłym ``{{ praca.pbn_uid.book_title }}``."""
        book = self.book
        return book.get("title") if book else None

    def get_pbn_uuid(self):
        """Nazwa tej funkcji to NIE literówka; alias to PBN UID V2

        get_pbn_uid_v2
        get_pbn_uuid_v2

        Ta funkcja próbuje zwrócić PBN UUID, pod warunkiem, że został zaciągnięty z API oświadczeń instytucji
        V2. Oraz, pod warunkiem, że self.pbn_uid_id jest ustawione."""

        if self.mongoId is None:
            return

        from pbn_api.models.publikacja_instytucji import PublikacjaInstytucji_V2

        publicationUuid = PublikacjaInstytucji_V2.objects.filter(
            objectId=self.mongoId
        ).values_list("uuid", flat=True)[:1]

        if publicationUuid:
            return publicationUuid[0]

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

    @staticmethod
    def _normalizuj_autora(autor):
        """Sprowadza pojedynczego autora z PBN do ``{lastName, firstName}``.

        Deleguje wybór pól do ``pbn_client.normalize_author_name`` (jedno
        źródło prawdy dla niespójnych kształtów PBN: ``lastName``/``familyName``
        dla nazwiska, ``firstName``/``givenNames``/``name`` dla imienia; goły
        UID lub inny nie-dict → brak danych). Paczka używa ``None`` jako
        sentinela pustki — tu koerujemy go do ``""``, bo szablon rekordu i
        ``str(autorzy)`` (logi) zakładają puste stringi, nie ``None``.
        """
        normalized = normalize_author_name(autor)
        return {klucz: (wartosc or "") for klucz, wartosc in normalized.items()}

    @cached_property
    def autorzy(self):
        """Autorzy/redaktorzy pogrupowani wg roli, jako listy słowników.

        PBN przechowuje te kolekcje niespójnie: raz jako *dict* kluczowany
        PBN UID-em autora (``{"<uid>": {...}}``), a raz jako *listę*
        słowników. Normalizujemy oba kształty do listy znormalizowanych
        słowników ``{lastName, firstName}``, żeby konsumenci (szablony,
        ``policz_autorow``) nie musieli znać surowych wariantów PBN.
        """
        ret = {}
        for elem in ["authors", "editors", "translators", "translationEditors"]:
            elem_dct = self.value_or_none("object", elem)
            if not elem_dct:
                continue
            kolekcja = elem_dct.values() if isinstance(elem_dct, dict) else elem_dct
            ret[elem] = [self._normalizuj_autora(autor) for autor in kolekcja]
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

    def get_bpp_publication(self):
        """Zwraca rekord BPP powiązany przez PBN UID (bez fuzzy matching)."""
        from bpp.models.cache import Rekord

        try:
            return Rekord.objects.get(pbn_uid_id=self.pk)
        except (Rekord.DoesNotExist, Rekord.MultipleObjectsReturned):
            return None

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
        if self.is_deleted:
            ret = f"[❌ USUNIĘTY] {ret}"
        return ret
