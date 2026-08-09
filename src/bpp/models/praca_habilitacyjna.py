from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import CASCADE, PROTECT, Q
from django.utils.functional import cached_property

from bpp.models import Autor, Charakter_Formalny, DwaTytuly, ModelZOplataZaPublikacje
from bpp.models.praca_doktorska import Praca_Doktorska_Baza
from bpp.models.soft_delete import BppPublikacjaSoftDeleteMixin


class Publikacja_Habilitacyjna(models.Model):
    # db_index=False: redundantny względem unique_together
    # (praca_habilitacyjna, content_type, object_id) — praca_habilitacyjna
    # jest wiodącą kolumną tego indeksu.
    praca_habilitacyjna = models.ForeignKey(
        "Praca_Habilitacyjna", CASCADE, db_index=False
    )
    kolejnosc = models.IntegerField("Kolejność", default=0)

    limit = (
        models.Q(app_label="bpp", model="wydawnictwo_ciagle")
        | models.Q(app_label="bpp", model="wydawnictwo_zwarte")
        | models.Q(app_label="bpp", model="patent")
    )
    content_type = models.ForeignKey(ContentType, CASCADE, limit_choices_to=limit)
    object_id = models.PositiveIntegerField()
    publikacja = GenericForeignKey()

    class Meta:
        app_label = "bpp"
        verbose_name = "powiązanie publikacji z habilitacją"
        verbose_name_plural = "powiązania publikacji z habilitacją"
        unique_together = [("praca_habilitacyjna", "content_type", "object_id")]
        ordering = ("kolejnosc",)


class _Praca_Habilitacyjna_PropertyCache:
    @cached_property
    def charakter_formalny(self):
        return Charakter_Formalny.objects.get(skrot="H")


_Praca_Habilitacyjna_PropertyCache = _Praca_Habilitacyjna_PropertyCache()


class Praca_Habilitacyjna(BppPublikacjaSoftDeleteMixin, Praca_Doktorska_Baza):
    # ``ForeignKey``, a NIE ``OneToOneField``, wyłącznie po to, żeby dało się
    # zdjąć bezwarunkowy ``UNIQUE (autor_id)`` — Django wymusza `unique=True`
    # w ``OneToOneField.__init__`` i nie ma tego jak wyłączyć. Reguła „jeden
    # autor, jedna habilitacja" nie znika: pilnuje jej warunkowy
    # ``phab_uniq_autor_zywy`` w ``Meta.constraints`` niżej.
    #
    # Twarde UNIQUE nie znało kosza. Duplikat z habilitacją soft-skasowaną
    # + główny autor z żywą wywracał CAŁE scalanie autorów ``IntegrityError``-em
    # (scalanie przenosi wiersze RAZEM Z KOSZEM, żeby nie zostawiać sierot).
    #
    # ⚠️ Akcesor odwrotny to teraz ``autor.praca_habilitacyjna_set`` (manager),
    # a nie ``autor.praca_habilitacyjna`` (obiekt). Ścieżka FILTROWANIA w ORM /
    # DjangoQL się NIE zmienia — ``related_query_name`` domyślnie i tak jest
    # nazwą modelu. Zmiana akcesora to zarazem naprawa: manager relacji używa
    # ``_default_manager`` (filtruje kosz), podczas gdy odwrotne OneToOne szło
    # przez ``_base_manager`` i pokazywało rekordy skasowane.
    autor = models.ForeignKey(Autor, PROTECT)

    publikacje_habilitacyjne = GenericRelation(Publikacja_Habilitacyjna)

    @cached_property
    def charakter_formalny(self):
        return _Praca_Habilitacyjna_PropertyCache.charakter_formalny

    class Meta:
        verbose_name = "praca habilitacyjna"
        verbose_name_plural = "prace habilitacyjne"
        app_label = "bpp"
        indexes = [
            # Indeks CZĘŚCIOWY — uzasadnienie przy `wc_deleted_at_idx`
            # (`wydawnictwo_ciagle.py`, Meta klasy Wydawnictwo_Ciagle).
            models.Index(
                fields=["deleted_at"],
                name="phab_deleted_at_idx",
                condition=Q(deleted_at__isnull=False),
            ),
        ]
        constraints = [
            # Następca bezwarunkowego `UNIQUE (autor_id)` z `OneToOneField`.
            # Ten sam wzorzec, co faza 01 zastosowała do `*_Autor`: reguła
            # obowiązuje TYLKO wśród żywych wierszy, więc habilitacja w koszu
            # nie blokuje ani ponownego wprowadzenia, ani przeniesienia przy
            # scalaniu autorów.
            #
            # ⚠️ To ograniczenie NIE jest samo z siebie widoczne w formularzu.
            # `Model.validate_constraints()` (Django >=4.1) po cichu POMIJA
            # sprawdzenie, gdy pole użyte w `condition` (`deleted_at`) jest
            # wykluczone z walidacji — a admin wyklucza wszystko spoza swoich
            # `fieldsets`. Komunikat dla operatora daje jawne `clean_autor()`
            # w `bpp/admin/praca_habilitacyjna.py`; tutejsze ograniczenie jest
            # ostateczną gwarancją na poziomie bazy.
            models.UniqueConstraint(
                fields=["autor"],
                condition=Q(deleted_at__isnull=True),
                name="phab_uniq_autor_zywy",
                # Bez tego operator zobaczyłby w adminie domyślne
                # „Constraint “phab_uniq_autor_zywy” is violated." — Django nie
                # umie zmapować UniqueConstraint z `condition` na komunikat
                # przy polu, więc trafia to w błędy ogólne formularza.
                violation_error_message="Ten autor ma już pracę habilitacyjną.",
            ),
        ]

    def clean(self):
        DwaTytuly.clean(self)
        ModelZOplataZaPublikacje.clean(self)

    def to_bibtex(self):
        """Export this habilitation thesis to BibTeX format."""
        from bpp.export.bibtex import praca_habilitacyjna_to_bibtex

        return praca_habilitacyjna_to_bibtex(self)
