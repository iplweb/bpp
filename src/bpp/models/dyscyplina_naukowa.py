from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import CASCADE, PositiveSmallIntegerField
from model_utils import Choices

from import_common.normalization import normalize_kod_dyscypliny

from bpp import const


def waliduj_format_kodu_numer(value):
    try:
        val1, val2 = (int(x) for x in value.split("."))
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
        super().__init__(*args, **kw)
        self.validators.append(waliduj_format_kodu_numer)

    def to_python(self, value):
        return normalize_kod_dyscypliny(value)


class Dyscyplina_Naukowa(models.Model):
    kod = KodDyscyplinyField(max_length=20, unique=True)
    nazwa = models.CharField(max_length=200, unique=True)
    widoczna = models.BooleanField(default=True)

    def kod_dla_pbn(self):
        a, b = (int(x) for x in self.kod.split(".", 1))
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
                return const.NIEPOPRAWNY_KOD

    @property
    def dyscyplina_hst(self):
        return self.kod_dziedziny() in const.DZIEDZINY_HST


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
        default="N",
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

    #
    # Te pola są importowane przez import_polon, ale nie są nigdzie wyświetlane na UI
    # na ten moment (mpasternak, 18.03.2025)
    #
    zatrudnienie_od = models.DateTimeField(blank=True, null=True)
    zatrudnienie_do = models.DateTimeField(blank=True, null=True)

    objects = Autor_DyscyplinaManager()

    def __str__(self):
        ret = f"przypisanie {self.autor} na rok {self.rok} do dyscypliny {self.dyscyplina_naukowa}"
        if self.subdyscyplina_naukowa_id is not None:
            ret += f" oraz {self.subdyscyplina_naukowa}"
        return ret

    class Meta:
        unique_together = [("rok", "autor")]
        verbose_name = "powiązanie autor-dyscyplina"
        verbose_name_plural = "powiązania autor-dyscyplina"

        ordering = ("rok",)

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

    def dwie_dyscypliny(self):
        # Zwraca True, jezeli rekord zawiera dwie rozne dyscypliny
        if (
            self.dyscyplina_naukowa_id is not None
            and self.subdyscyplina_naukowa_id is not None
            and self.dyscyplina_naukowa_id != self.subdyscyplina_naukowa_id
        ):
            return True
        return False

    def policz_udzialy(self):
        if self.wymiar_etatu is None:
            return

        if (
            self.dyscyplina_naukowa_id is not None
            and self.procent_dyscypliny is not None
        ):
            yield (
                self.dyscyplina_naukowa,
                self.wymiar_etatu * self.procent_dyscypliny / Decimal("100.0"),
            )

        if (
            self.subdyscyplina_naukowa_id is not None
            and self.procent_subdyscypliny is not None
        ):
            yield (
                self.subdyscyplina_naukowa,
                self.wymiar_etatu * self.procent_subdyscypliny / Decimal("100.0"),
            )


class Autor_Absencja(models.Model):
    autor = models.ForeignKey("bpp.Autor", CASCADE)

    rok = PositiveSmallIntegerField()
    ile_dni = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = [("rok", "autor")]
        verbose_name = "absencja autora za rok"
        verbose_name_plural = "absencje autora za lata"


def przebuduj_prace_autora_po_udanej_transakcji(autor_id, rok):
    # Zaznacz wszystkie rekordy z tym autorem z danego roku po zakończeniu
    # transakcji jako "brudne" aby prawidłowo przekalkulować ich punktacje.
    #
    # W tej chwili nie ma prostej możliwości połączenia zależności bazodanowych
    # za pomocą django_denorm, a niespecjalnie jestem zainteresowany rozbudowywaniem
    # tej biblioteki (chociaż byłoby to do zrobienia, myślę, ale nie w tym momencie).
    #
    # Zatem, zlecamy przekalkulowanie wszystkich instancji prac tego autora
    # po zapisaniu danych do bazy.
    #
    # Nie mam lepszych pomysłów na ten moment + po ręcznej zmianie typu autora dla
    # powiązania autor+dyscyplina automatyczna rekalkulacja NIE będzie wykonana;
    # będzie trzeba czekać na rekalkulację wieczorna bądź otworzyć/zapisać dany rekord.
    #
    # ... chyba, że uruchomię tą funkcję po zapisaniu (zmianie) wartości rodzaj_autora
    # przez admina, ale to jest TODO:
    #
    # -- mpasternak, 16.03.2025

    from denorm.denorms import rebuild_instances_of

    from bpp.models import Patent, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    def _(autor_id=autor_id, rok=rok):
        for klass in [Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Patent]:
            rebuild_instances_of(klass, rok=rok, autorzy_set__autor_id=autor_id)

    transaction.on_commit(_)
