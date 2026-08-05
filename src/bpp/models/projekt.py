"""Encje projektu badawczego i jego finansowania.

Modele odpowiadają encjom CERIF ``Project`` i ``Funding`` z profilu
OpenAIRE Guidelines for CRIS Managers 1.2.0. Dziedziczenie po
``ModelZAdnotacjami`` nie jest kosmetyczne: daje ``ostatnio_zmieniony``,
na którym ``cerif_export.providers.base.z_datestampem`` buduje keysetowy
kursor przyrostowego harvestu OAI-PMH.
"""

from django.core.exceptions import ValidationError
from django.db import models

from bpp.models.abstract import ModelZAdnotacjami, ModelZeSlowamiKluczowymi
from bpp.util.ror import waliduj as waliduj_ror

__all__ = [
    "Projekt",
    "Projekt_Autor",
    "Instytucja_Finansujaca",
    "Finansowanie",
]


class Projekt(ModelZAdnotacjami, ModelZeSlowamiKluczowymi):
    STATUS_PLANOWANY = "planowany"
    STATUS_W_TRAKCIE = "w-trakcie"
    STATUS_ZAKONCZONY = "zakonczony"
    STATUS_PRZERWANY = "przerwany"

    STATUSY = [
        (STATUS_PLANOWANY, "planowany"),
        (STATUS_W_TRAKCIE, "w trakcie"),
        (STATUS_ZAKONCZONY, "zakończony"),
        (STATUS_PRZERWANY, "przerwany"),
    ]

    tytul = models.TextField(verbose_name="Tytuł")
    tytul_en = models.TextField(
        verbose_name="Tytuł (angielski)", blank=True, default=""
    )
    akronim = models.CharField(
        verbose_name="Akronim", max_length=50, blank=True, default=""
    )
    data_rozpoczecia = models.DateField(
        verbose_name="Data rozpoczęcia", null=True, blank=True
    )
    data_zakonczenia = models.DateField(
        verbose_name="Data zakończenia", null=True, blank=True
    )
    status = models.CharField(
        verbose_name="Status",
        max_length=20,
        choices=STATUSY,
        default=STATUS_W_TRAKCIE,
    )
    abstrakt = models.TextField(verbose_name="Abstrakt", blank=True, default="")
    abstrakt_en = models.TextField(
        verbose_name="Abstrakt (angielski)", blank=True, default=""
    )
    dyscypliny = models.ManyToManyField(
        "bpp.Dyscyplina_Naukowa", blank=True, verbose_name="Dyscypliny"
    )
    # Jednostka jest wymagana, bo jest jedynym nośnikiem przynależności
    # projektu do uczelni (tenanta). Provider CERIF filtruje po
    # ``jednostka__uczelnia``; pole nullable po cichu wypychałoby projekty
    # z eksportu.
    jednostka = models.ForeignKey(
        "bpp.Jednostka",
        models.PROTECT,
        verbose_name="Jednostka realizująca",
    )
    strona_www = models.URLField(verbose_name="Strona WWW", blank=True, default="")

    class Meta:
        verbose_name = "projekt"
        verbose_name_plural = "projekty"
        ordering = ["-data_rozpoczecia", "tytul"]

    def __str__(self):
        if self.akronim:
            return f"{self.akronim} — {self.tytul}"
        return self.tytul

    def clean(self):
        if (
            self.data_rozpoczecia
            and self.data_zakonczenia
            and self.data_zakonczenia < self.data_rozpoczecia
        ):
            raise ValidationError(
                {
                    "data_zakonczenia": "Data zakończenia jest wcześniejsza "
                    "niż data rozpoczęcia."
                }
            )


class Projekt_Autor(models.Model):
    ROLA_KIEROWNIK = "kierownik"
    ROLA_WYKONAWCA = "wykonawca"
    ROLA_WSPOLWYKONAWCA = "wspolwykonawca"

    ROLE = [
        (ROLA_KIEROWNIK, "kierownik"),
        (ROLA_WYKONAWCA, "wykonawca"),
        (ROLA_WSPOLWYKONAWCA, "współwykonawca"),
    ]

    projekt = models.ForeignKey(Projekt, models.CASCADE, verbose_name="Projekt")
    autor = models.ForeignKey("bpp.Autor", models.PROTECT, verbose_name="Autor")
    rola = models.CharField(
        verbose_name="Rola", max_length=20, choices=ROLE, default=ROLA_WYKONAWCA
    )
    od = models.DateField(verbose_name="Od", null=True, blank=True)
    do = models.DateField(verbose_name="Do", null=True, blank=True)

    class Meta:
        verbose_name = "osoba w projekcie"
        verbose_name_plural = "osoby w projekcie"
        unique_together = [("projekt", "autor", "rola")]
        constraints = [
            # Jeden kierownik na projekt — wymuszone w bazie, bo ``clean()``
            # przy dwóch nowych wierszach dodanych naraz w inline widzi
            # wyłącznie stan zapisany, więc drugiego kierownika by przepuścił.
            models.UniqueConstraint(
                fields=["projekt"],
                condition=models.Q(rola="kierownik"),
                name="projekt_jeden_kierownik",
            )
        ]

    def __str__(self):
        return f"{self.autor} ({self.get_rola_display()})"


class Instytucja_Finansujaca(ModelZAdnotacjami):
    """Grantodawca. Eksportowana jako CERIF ``OrgUnit`` (rola Funder)."""

    nazwa = models.TextField(verbose_name="Nazwa")
    nazwa_en = models.TextField(
        verbose_name="Nazwa (angielska)", blank=True, default=""
    )
    akronim = models.CharField(
        verbose_name="Akronim", max_length=50, blank=True, default=""
    )
    kraj = models.CharField(
        verbose_name="Kraj",
        max_length=2,
        default="PL",
        help_text="Kod ISO 3166-1 alpha-2. Pole wewnętrzne — profil "
        "OpenAIRE nie ma elementu Country w encji OrgUnit.",
    )
    ror_id = models.CharField(
        verbose_name="Identyfikator ROR",
        max_length=64,
        blank=True,
        default="",
        validators=[waliduj_ror],
        help_text="Identyfikator w Research Organization Registry (ROR), "
        "np. https://ror.org/016f61126 — ma wbudowaną sumę kontrolną, więc "
        "literówka zostanie odrzucona. Gdy pusty, nie zostanie "
        "wyeksportowany.",
    )
    fundref_id = models.CharField(
        verbose_name="Crossref Funder ID",
        max_length=50,
        blank=True,
        default="",
        help_text="Identyfikator z Crossref Funder Registry, np. 501100004281.",
    )
    strona_www = models.URLField(verbose_name="Strona WWW", blank=True, default="")

    class Meta:
        verbose_name = "instytucja finansująca"
        verbose_name_plural = "instytucje finansujące"
        ordering = ["nazwa"]

    def __str__(self):
        if self.akronim:
            return f"{self.akronim} — {self.nazwa}"
        return self.nazwa


class Finansowanie(ModelZAdnotacjami):
    """Źródło finansowania projektu. Encja CERIF ``Funding``."""

    TYP_FUNDING_PROGRAMME = "FundingProgramme"
    TYP_CALL = "Call"
    TYP_TENDER = "Tender"
    TYP_GIFT = "Gift"
    TYP_INTERNAL_FUNDING = "InternalFunding"
    TYP_CONTRACT = "Contract"
    TYP_AWARD = "Award"
    TYP_GRANT = "Grant"

    TYPY = [
        (TYP_FUNDING_PROGRAMME, "program finansowania"),
        (TYP_CALL, "konkurs"),
        (TYP_TENDER, "przetarg"),
        (TYP_GIFT, "darowizna"),
        (TYP_INTERNAL_FUNDING, "finansowanie wewnętrzne"),
        (TYP_CONTRACT, "umowa"),
        (TYP_AWARD, "nagroda"),
        (TYP_GRANT, "grant"),
    ]

    projekt = models.ForeignKey(Projekt, models.CASCADE, verbose_name="Projekt")
    typ = models.CharField(
        verbose_name="Typ", max_length=30, choices=TYPY, default=TYP_GRANT
    )
    instytucja = models.ForeignKey(
        Instytucja_Finansujaca, models.PROTECT, verbose_name="Instytucja finansująca"
    )
    nazwa_programu = models.CharField(
        verbose_name="Nazwa programu",
        max_length=200,
        blank=True,
        default="",
        help_text="Nazwa programu lub konkursu, np. „OPUS 24”.",
    )
    numer_umowy = models.CharField(
        verbose_name="Numer umowy", max_length=200, blank=True, default=""
    )
    kwota = models.DecimalField(
        verbose_name="Kwota", max_digits=14, decimal_places=2, null=True, blank=True
    )
    waluta = models.CharField(
        verbose_name="Waluta", max_length=3, blank=True, default="PLN"
    )
    grant_doi = models.CharField(
        verbose_name="DOI grantu", max_length=200, blank=True, default=""
    )

    class Meta:
        verbose_name = "finansowanie"
        verbose_name_plural = "finansowania"

    def __str__(self):
        return f"{self.instytucja} — {self.get_typ_display()}"

    def clean(self):
        if self.kwota is not None and not self.waluta:
            raise ValidationError({"waluta": "Kwota bez waluty jest niejednoznaczna."})
