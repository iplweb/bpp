from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import CASCADE, PositiveSmallIntegerField
from model_utils import Choices

# bpp=# select distinct substr(id, 1, 2), dziedzina from import_dbf_ldy;
#  substr |                 dziedzina
# --------+--------------------------------------------
#  01     | Dziedzina nauk humanistycznych
#  02     | Dziedzina nauk inżynieryjno-technicznych
#  03     | Dziedzina nauk medycznych i nauk o zdrowiu
#  04     | Dziedzina nauk rolniczych
#  05     | Dziedzina nauk społecznych
#  06     | Dziedzina nauk ścisłych i przyrodniczych
#  07     | Dziedzina nauk teologicznych
#  08     | Dziedzina sztuki
# (8 rows)
from import_common.normalization import normalize_kod_dyscypliny

from bpp.models import const


def mnoznik_dla_monografii(kod_dziedziny, tryb_kalkulacji, punktacja_monografii):
    """
    § 12.
    5. W przypadku działalności naukowej prowadzonej w ramach dyscyplin naukowych
    należących do dziedziny nauk humanistycznych, dziedziny nauk społecznych i
    dziedziny nauk teologicznych całkowitą wartość punktową:

    1) monografii naukowej wynoszącą – zgodnie z przepisem ust. 2 pkt 1:
        a) 200 pkt, zwiększa się o 50%,
        b) 80 pkt, zwiększa się o 25%;

    2) redakcji naukowej monografii naukowej wynoszącą – zgodnie z przepisem ust. 3
        pkt 1 – 100 pkt, zwiększa się o 50%;

    3) rozdziału w monografii naukowej wynoszącą – zgodnie z przepisem ust. 4 pkt 1
        – 50 pkt, zwiększa się o 50%.

    :return:
    """
    if kod_dziedziny in const.WYZSZA_PUNKTACJA:

        if tryb_kalkulacji == const.TRYB_KALKULACJI.AUTORSTWO_MONOGRAFII:
            if punktacja_monografii == 200:
                return 1.5
            elif punktacja_monografii == 80:
                return 1.25

        elif tryb_kalkulacji == const.TRYB_KALKULACJI.REDAKCJA_MONOGRAFI:
            if punktacja_monografii == 100:
                return 1.5

        elif tryb_kalkulacji == const.TRYB_KALKULACJI.ROZDZIAL_W_MONOGRAFI:
            if punktacja_monografii == 50:
                return 1.5

        else:
            raise NotImplementedError(
                f"Nieobsługiwany tryb kalkulacji: {tryb_kalkulacji}"
            )

    return 1


def waliduj_format_kodu_numer(value):
    try:
        val1, val2 = [int(x) for x in value.split(".")]
    except (TypeError, ValueError):
        raise ValidationError("Poprawny kod ma format LICZBA[kropka]LICZBA")

    msg = (
        "Pierwsza cyfra dziedziny nie ma odwzorowania w słowniku dziedzin w systemie BPP. "
        "Jeżeli jesteś pewny/a że ta wartośc jest poprawna, skontaktuj się z administratorem "
        "systemu. "
    )
    try:
        dziedzina = const.DZIEDZINA(val1)
    except ValueError:
        raise ValidationError(msg)

    if dziedzina not in const.DZIEDZINY:
        raise ValidationError(msg)


class KodDyscyplinyField(models.CharField):
    def __init__(self, *args, **kw):
        super(KodDyscyplinyField, self).__init__(*args, **kw)
        self.validators.append(waliduj_format_kodu_numer)

    def to_python(self, value):
        return normalize_kod_dyscypliny(value)


class Dyscyplina_Naukowa(models.Model):
    kod = KodDyscyplinyField(max_length=20, unique=True)
    nazwa = models.CharField(max_length=200, unique=True)
    widoczna = models.BooleanField(default=True)

    def kod_dla_pbn(self):
        a, b = [int(x) for x in self.kod.split(".", 1)]
        return int("%i%.2i" % (a, b))

    def __str__(self):
        return f"{self.nazwa} ({self.kod})"

    class Meta:
        verbose_name_plural = "dyscypliny naukowe"
        verbose_name = "dyscyplina naukowa"

    def kod_dziedziny(self):
        try:
            return int(self.kod.lstrip("0").strip().split(".")[0])
        except (ValueError, TypeError, KeyError):
            pass

    def dziedzina(self):
        kod_dziedziny = self.kod_dziedziny()
        if kod_dziedziny is not None:
            try:
                return const.DZIEDZINY.get(const.DZIEDZINA(kod_dziedziny))
            except ValueError:
                return "[niepoprawny kod]"

    def mnoznik_dla_monografi(self, tryb_kalkulacji, punktacja_monografi):
        return mnoznik_dla_monografii(
            self.kod_dziedziny(), tryb_kalkulacji, punktacja_monografi
        )


class Autor_DyscyplinaManager(models.Manager):
    @transaction.atomic
    def ukryj_nieuzywane(self):
        # Ukryj dyscypliny nieużywane
        for elem in Dyscyplina_Naukowa.objects.all():
            elem.widoczna = False
            elem.save()

        for attr in "dyscyplina_naukowa", "subdyscyplina_naukowa":
            for elem in self.all().values(attr).distinct():
                if elem[attr] is None:
                    continue

                elem = Dyscyplina_Naukowa.objects.get(pk=elem[attr])
                elem.widoczna = True
                elem.save()


class Autor_Dyscyplina(models.Model):
    rok = PositiveSmallIntegerField()
    autor = models.ForeignKey("bpp.Autor", CASCADE)

    RODZAJE_AUTORA = Choices(
        (" ", "brak danych"),
        ("N", "pracownik zaliczany do liczby N"),
        ("D", "doktorant"),
        ("Z", "inny zatrudniony"),
    )

    rodzaj_autora = models.CharField(
        max_length=1,
        choices=RODZAJE_AUTORA,
        default=" ",
    )

    wymiar_etatu = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=3
    )

    dyscyplina_naukowa = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa", models.PROTECT, related_name="dyscyplina"
    )
    procent_dyscypliny = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    subdyscyplina_naukowa = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        models.PROTECT,
        related_name="subdyscyplina",
        blank=True,
        null=True,
    )
    procent_subdyscypliny = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    objects = Autor_DyscyplinaManager()

    def __str__(self):
        ret = f"przypisanie {self.autor} na rok {self.rok} do dyscypliny {self.dyscyplina_naukowa}"
        if self.subdyscyplina_naukowa_id is not None:
            ret += f" oraz {self.subdyscyplina_naukowa}"
        return ret

    class Meta:
        unique_together = [("rok", "autor")]
        verbose_name = "powiązanie autora z dyscypliną naukową"
        verbose_name_plural = "powiązania autorów z dyscyplinami naukowymi"

    def clean(self):
        p1 = self.procent_dyscypliny or Decimal("0.00")
        p2 = self.procent_subdyscypliny or Decimal("0.00")

        if p1 + p2 > Decimal("100.00"):
            raise ValidationError(
                {"procent_dyscypliny": "Suma procentów przekracza 100."}
            )

        if hasattr(self, "dyscyplina_naukowa") and hasattr(
            self, "subdyscyplina_naukowa"
        ):
            if self.dyscyplina_naukowa_id == self.subdyscyplina_naukowa_id:
                raise ValidationError(
                    {"subdyscyplina_naukowa": "Wpisano tą samą dyscyplinę dwukrotnie."}
                )
