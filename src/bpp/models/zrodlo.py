"""
Źródła.
"""

from decimal import Decimal

from autoslug import AutoSlugField
from django.contrib.postgres.search import SearchVectorField as VectorField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import CASCADE, SET_NULL, F, Value
from django.db.models.functions import Replace, Upper
from django.urls.base import reverse

from bpp import const
from bpp.fields import DOIField, YearField
from bpp.jezyk_polski import czasownik_byc
from bpp.models import LinkDoPBNMixin, ModelZKwartylami
from bpp.models.abstract import (
    ModelPunktowanyBaza,
    ModelZAdnotacjami,
    ModelZISSN,
    ModelZNazwa,
)
from bpp.models.soft_delete import BppSoftDeleteManager, BppSoftDeleteSlownikMixin
from bpp.models.system import Jezyk
from bpp.util import FulltextSearchMixin


def kwartyl_scopus_z_percentyla(percentyl):
    """Kwartyl Scopus (1–4) dla najwyższego percentyla CiteScore (0–100).

    Q1: 75–100, Q2: 50–74, Q3: 25–49, Q4: 0–24. ``None`` dla braku wartości
    albo wartości spoza zakresu.
    """
    if percentyl is None or not 0 <= percentyl <= 100:
        return None
    if percentyl >= 75:
        return 1
    if percentyl >= 50:
        return 2
    if percentyl >= 25:
        return 3
    return 4


def uzupelnij_punktacje_z_zrodla(rekord, zrodlo, rok):
    """Uzupełnij pola punktacji rekordu na podstawie Punktacja_Zrodla.

    Zwraca True jeśli punktacja została uzupełniona,
    False jeśli brak danych.
    """
    from bpp.models.abstract import POLA_PUNKTACJI

    try:
        pz = Punktacja_Zrodla.objects.get(zrodlo=zrodlo, rok=rok)
    except Punktacja_Zrodla.DoesNotExist:
        return False

    for pole in POLA_PUNKTACJI:
        setattr(rekord, pole, getattr(pz, pole))
    rekord.save()
    return True


class Rodzaj_Zrodla(ModelZNazwa):
    class Meta:
        verbose_name = "rodzaj źródła"
        verbose_name_plural = "rodzaje źródeł"
        app_label = "bpp"


class Zasieg_Zrodla(ModelZNazwa):
    class Meta:
        verbose_name = "zasięg źródła"
        verbose_name_plural = "zasięg źródeł"
        app_label = "bpp"


class Redakcja_Zrodla(models.Model):
    """Informacja o tym, że ktoś jest redaktorem danego źródła - w latach,
    od - do."""

    #: Redakcja żyje ze źródłem: jest „w koszu" razem z nim (nie blokuje
    #: kosza redaktora), a przywrócenie źródła sprawdza, czy redaktor nie
    #: jest w koszu (``bpp.models.soft_delete._pole_rodzica``).
    POLE_RODZICA_KOSZA = "zrodlo"

    zrodlo = models.ForeignKey("bpp.Zrodlo", CASCADE)
    od_roku = YearField()
    do_roku = YearField(null=True, blank=True)
    redaktor = models.ForeignKey("bpp.Autor", CASCADE)

    class Meta:
        app_label = "bpp"
        verbose_name = "redaktor źródła"
        verbose_name_plural = "redaktorzy źródła"

    def __str__(self):
        buf = f"Redaktorem od {self.od_roku} "

        if self.do_roku is not None:
            key = "czas_przeszly"
            buf += f"do {self.do_roku} "
        else:
            key = "czas_terazniejszy"

        if self.redaktor.plec is not None:
            skrot = self.redaktor.plec.skrot
        else:
            skrot = "default"
        buf += czasownik_byc.get(key).get(skrot, czasownik_byc.get(key)["default"])

        buf += " " + str(self.redaktor)
        return buf


# TODO: sprawdzanie dla redakcja_zrodla, czy rok od jest > niz rok do <
class Punktacja_Zrodla(ModelPunktowanyBaza, ModelZKwartylami, models.Model):
    """Informacja o punktacji danego źródła w danym roku"""

    # db_index=False: redundantny względem unique_together (zrodlo, rok) —
    # zrodlo jest wiodącą kolumną tego złożonego indeksu.
    zrodlo = models.ForeignKey("Zrodlo", CASCADE, db_index=False)
    rok = YearField()

    # Wskaźniki Scopus (FD#370). Tylko przy źródle — publikacje ich nie mają,
    # więc celowo NIE należą do ``POLA_PUNKTACJI`` (lista pól kopiowanych
    # między źródłem a pracą).
    citescore = models.DecimalField(
        "CiteScore",
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Wskaźnik CiteScore (Scopus) — liczba nieujemna z jednym "
        "miejscem po przecinku.",
    )
    citescore_percentyl = models.PositiveSmallIntegerField(
        "CiteScore (najwyższy percentyl)",
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Najwyższy percentyl CiteScore (Scopus), od 0 do 100. Gdy "
        "kwartyl w SCOPUS jest pusty, zostanie uzupełniony na jego podstawie.",
    )

    class Meta:
        verbose_name = "punktacja źródła"
        verbose_name_plural = "punktacja źródła"
        ordering = ["zrodlo__nazwa", "rok"]
        unique_together = [("zrodlo", "rok")]
        app_label = "bpp"

    def __str__(self):
        return f'Punktacja źródła "{self.zrodlo}" za rok {self.rok}'

    def save(self, *args, **kwargs):
        if self.uzupelnij_kwartyl_scopus_z_percentyla():
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "kwartyl_w_scopus"}
        super().save(*args, **kwargs)

    def uzupelnij_kwartyl_scopus_z_percentyla(self) -> bool:
        """Wpisuje kwartyl Scopus wynikający z percentyla CiteScore — ale
        tylko gdy kwartyl jest pusty (wartości wpisanej ręcznie nie rusza).

        Zwraca True, jeżeli kwartyl został ustawiony.
        """
        if self.kwartyl_w_scopus is not None:
            return False
        kwartyl = kwartyl_scopus_z_percentyla(self.citescore_percentyl)
        if kwartyl is None:
            return False
        self.kwartyl_w_scopus = kwartyl
        return True


class Dyscyplina_Zrodla(models.Model):
    rok = YearField()
    # db_index=False: redundantny względem unique_together
    # (zrodlo, dyscyplina, rok) — zrodlo jest wiodącą kolumną tego indeksu.
    zrodlo = models.ForeignKey("Zrodlo", on_delete=CASCADE, db_index=False)
    dyscyplina = models.ForeignKey("Dyscyplina_Naukowa", on_delete=CASCADE)

    class Meta:
        verbose_name = "przypisanie dyscypliny do źródła"
        verbose_name_plural = "przypisanie dyscyplin do źródła"
        ordering = ["zrodlo__nazwa", "rok", "dyscyplina__nazwa"]
        unique_together = [("zrodlo", "dyscyplina", "rok")]
        app_label = "bpp"

    def __str__(self):
        return f'Przypisanie dyscypliny "{self.dyscyplina}" do źródła "{self.zrodlo}" dla roku {self.rok}'


class ZrodloManager(FulltextSearchMixin, BppSoftDeleteManager):
    pass


def issn_norm_expr(field: str):
    """SQL expression normalising an ISSN field: no hyphens/spaces, upper case.

    Shared by the functional indexes on ``Zrodlo`` and the ISSN matcher in
    ``import_common.core.zrodlo`` -- PostgreSQL uses an expression index only
    when the query expression is identical, so keep a single definition.
    """
    return Upper(
        Replace(Replace(F(field), Value("-"), Value("")), Value(" "), Value(""))
    )


class Zrodlo(BppSoftDeleteSlownikMixin, LinkDoPBNMixin, ModelZAdnotacjami, ModelZISSN):
    """Źródło (czasopismo). Kosz: tylko źródło bez żywych publikacji
    (publikacje z kosza nie blokują); punktacja, dyscypliny i redakcja
    zostają przy nim."""

    #: Dane „przy źródle", logi, wiersze importów, deduplikacja.
    pomijane_relacje_kosza = frozenset(
        {
            "bpp.Redakcja_Zrodla.zrodlo",
            "bpp.Punktacja_Zrodla.zrodlo",
            "bpp.Dyscyplina_Zrodla.zrodlo",
            "import_list_if.ImportListIfRow.zrodlo",
            "pbn_komparator_zrodel.RozbieznoscZrodlaPBN.zrodlo",
            "pbn_komparator_zrodel.LogAktualizacjiZrodla.zrodlo",
            "integrator2.ListaMinisterialnaElement.zrodlo",
            "rozbieznosci.RozbieznoscLog.zrodlo",
            "import_list_ministerialnych.WierszImportuListyMinisterialnej.zrodlo",
            "import_punktacji_zrodel.WierszImportuPunktacjiZrodel.zrodlo",
            "deduplikator_zrodel.NotADuplicate.zrodlo",
            "deduplikator_zrodel.NotADuplicate.duplikat",
            "deduplikator_zrodel.IgnoredSource.zrodlo",
            "deduplikator_zrodel.SourceDuplicateCandidate.main_zrodlo",
            "deduplikator_zrodel.SourceDuplicateCandidate.duplicate_zrodlo",
            "przemapuj_zrodla_pbn.PrzeMapowanieZrodla.zrodlo_stare",
            "przemapuj_zrodla_pbn.PrzeMapowanieZrodla.zrodlo_nowe",
            "przemapuj_zrodlo.PrzemapowaZrodla.zrodlo_z",
            "przemapuj_zrodlo.PrzemapowaZrodla.zrodlo_do",
            "importer_publikacji.ImportSession.zrodlo",
        }
    )

    url_do_pbn = const.LINK_PBN_DO_ZRODLA

    nazwa = models.CharField(max_length=1024, db_index=True)
    skrot = models.CharField("Skrót", max_length=512, db_index=True)

    rodzaj = models.ForeignKey(Rodzaj_Zrodla, CASCADE)

    nazwa_alternatywna = models.CharField(  # noqa: DJ001
        max_length=1024, db_index=True, blank=True, null=True
    )
    skrot_nazwy_alternatywnej = models.CharField(  # noqa: DJ001
        max_length=512, blank=True, null=True, db_index=True
    )

    zasieg = models.ForeignKey(
        Zasieg_Zrodla, SET_NULL, null=True, blank=True, default=None
    )

    www = models.URLField(  # noqa: DJ001
        "WWW", max_length=1024, blank=True, null=True, db_index=True
    )

    doi = DOIField("DOI", blank=True, null=True, db_index=True)

    poprzednia_nazwa = models.CharField(  # noqa: DJ001
        "Poprzedni tytuł",
        max_length=1024,
        db_index=True,
        blank=True,
        null=True,
    )

    openaccess_tryb_dostepu = models.CharField(
        verbose_name="OpenAccess: tryb dostępu",
        max_length=50,
        db_index=True,
        blank=True,
        choices=[("FULL", "pełny"), ("PARTIAL", "częściowy")],
    )

    openaccess_licencja = models.ForeignKey(
        "Licencja_OpenAccess",
        CASCADE,
        verbose_name="OpenAccess: licencja",
        blank=True,
        null=True,
    )

    jezyk = models.ForeignKey(Jezyk, CASCADE, null=True, blank=True)
    wydawca = models.CharField(max_length=250, blank=True)

    search = VectorField()

    objects = ZrodloManager()

    pbn_uid = models.ForeignKey(
        "pbn_api.Journal",
        verbose_name="Odpowiednik w PBN",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    slug = AutoSlugField(
        populate_from="nazwa", unique=True, manager_name="global_objects"
    )

    def get_absolute_url(self):
        return reverse("bpp:browse_zrodlo", args=(self.slug,))

    def __str__(self):
        ret = f"{self.nazwa}"

        # if self.nazwa_alternatywna:
        #     ret += " (%s)" % self.nazwa_alternatywna
        #
        if self.poprzednia_nazwa:
            ret += f" (d. {self.poprzednia_nazwa})"

        return ret

    class Meta:
        verbose_name = "źródło"
        verbose_name_plural = "źródła"
        ordering = ["nazwa"]
        app_label = "bpp"
        # ISSN matching ignoring hyphens/spaces/case (FD#451).
        indexes = [
            models.Index(issn_norm_expr("issn"), name="zrodlo_issn_norm"),
            models.Index(issn_norm_expr("e_issn"), name="zrodlo_e_issn_norm"),
        ]

    def prace_w_latach(self):
        from bpp.models import Wydawnictwo_Ciagle

        return (
            Wydawnictwo_Ciagle.objects.filter(zrodlo=self)
            .values_list("rok", flat=True)
            .distinct()
            .order_by("rok")
        )

    def dyscypliny_aktualna_ewaluacja(
        self,
        min_year=const.PBN_AKTUALNA_EWALUACJA_START,
        max_year=None,
    ):
        # max_year=None => bez górnego ograniczenia: pokazujemy dyscypliny aż
        # do najnowszego roku obecnego w bazie (Freshdesk 296). Wcześniej górną
        # granicą był na sztywno const.PBN_AKTUALNA_EWALUACJA_STOP, przez co
        # świeżo wgrane lata (np. 2026) nie pojawiały się na podstronie źródła.
        qs = self.dyscyplina_zrodla_set.filter(
            rok__gte=min_year, dyscyplina__widoczna=True
        )
        if max_year is not None:
            qs = qs.filter(rok__lte=max_year)
        return qs.select_related().order_by("rok", "dyscyplina__kod")
