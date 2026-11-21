from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import DO_NOTHING
from django.utils.html import strip_tags
from django.utils.text import Truncator

from bpp.fields import YearField
from bpp.models import BazaModeluOdpowiedzialnosciAutorow, TupleField

DLUGOSC_TYTULU = 80


def _opis(obj, pole, tekst, brak):
    """Text for a related object of a DB-view row, or ``brak`` when it is gone.

    The views use DO_NOTHING foreign keys, so the related row may have been
    deleted after the view row was read.
    """
    try:
        powiazany = getattr(obj, pole)
    except ObjectDoesNotExist:
        return brak
    return tekst(powiazany)


def _tytul(rekord):
    return Truncator(strip_tags(rekord.tytul_oryginalny or "").strip()).chars(
        DLUGOSC_TYTULU
    )


def _autor(autor):
    return f"{autor.nazwisko} {autor.imiona}"


class RozbieznosciViewBase(models.Model):
    id = TupleField(models.IntegerField(), size=3, primary_key=True)
    rekord = models.ForeignKey("bpp.Rekord", DO_NOTHING, related_name="+")
    rok = YearField()
    autor = models.ForeignKey("bpp.Autor", DO_NOTHING, related_name="+")
    dyscyplina_rekordu = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa", DO_NOTHING, related_name="+", null=True, blank=True
    )
    # NULL when the author has no discipline for that year — such rows must
    # stay visible, so this has to be a LEFT JOIN in select_related().
    dyscyplina_autora = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa", DO_NOTHING, related_name="+", null=True, blank=True
    )
    subdyscyplina_autora = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa", DO_NOTHING, related_name="+", null=True, blank=True
    )

    class Meta:
        managed = False
        abstract = True
        ordering = ["id"]

    def __str__(self):
        tytul = _opis(self, "rekord", _tytul, f"rekord #{self.rekord_id}")
        autor = _opis(self, "autor", _autor, f"autor #{self.autor_id}")
        return f"{tytul} — {autor} ({self.rok})"


class BrakPrzypisaniaView(RozbieznosciViewBase):
    class Meta:
        managed = False


class RozbieznePrzypisaniaView(RozbieznosciViewBase):
    class Meta:
        managed = False


class RozbieznosciView(RozbieznosciViewBase):
    # Uwaga: w sytuacji, gdy praca będzie miała jednego i tego samego autora (np w roli redaoktora
    # oraz autora) to ten model i funkcja get_wydawnictwo_autor_obj zawiedzie.
    class Meta:
        managed = False
        ordering = ["id"]
        verbose_name = "rozbieżność rekordu i dyscyplin"
        verbose_name_plural = "rozbieżności rekordów i dyscyplin"

    def get_wydawnictwo_autor_obj(self) -> BazaModeluOdpowiedzialnosciAutorow:
        # Uwaga: w sytuacji, gdy praca będzie miała jednego i tego samego autora (np w roli redaoktora
        # oraz autora) to ten model i funkcja get_wydawnictwo_autor_obj zawiedzie (zwraca wyłacznie pierwszy
        # rekord z powiazaniem autora + rekordu)
        return self.rekord.original.autorzy_set.filter(autor=self.autor).first()


class RozbieznosciZrodelView(models.Model):
    id = TupleField(models.IntegerField(), size=4, primary_key=True)
    zrodlo = models.ForeignKey(
        "bpp.Zrodlo", on_delete=DO_NOTHING, related_name="+", verbose_name="źródło"
    )
    rok = YearField()
    wydawnictwo_ciagle = models.ForeignKey(
        "bpp.Wydawnictwo_Ciagle",
        on_delete=DO_NOTHING,
        related_name="+",
        verbose_name="wydawnictwo ciągłe",
    )
    autor = models.ForeignKey("bpp.Autor", on_delete=DO_NOTHING, related_name="+")
    dyscyplina_naukowa = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        on_delete=DO_NOTHING,
        related_name="+",
        verbose_name="dyscyplina naukowa",
    )
    punkty_kbn = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="punkty MNiSW",
    )
    charakter_formalny = models.ForeignKey(
        "bpp.Charakter_Formalny",
        on_delete=DO_NOTHING,
        related_name="+",
        null=True,
        blank=True,
        verbose_name="charakter formalny",
    )

    class Meta:
        managed = False
        verbose_name = "rozbieżność dyscyplin źródeł"
        verbose_name_plural = "rozbieżności dyscyplin źródeł"

    def __str__(self):
        tytul = _opis(
            self,
            "wydawnictwo_ciagle",
            _tytul,
            f"wydawnictwo ciągłe #{self.wydawnictwo_ciagle_id}",
        )
        zrodlo = _opis(self, "zrodlo", lambda z: z.nazwa, f"źródło #{self.zrodlo_id}")
        return f"{tytul} — {zrodlo} ({self.rok})"
