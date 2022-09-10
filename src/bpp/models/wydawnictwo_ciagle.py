from denorm import denormalized, depend_on_related
from dirtyfields.dirtyfields import DirtyFieldsMixin
from django.db import models
from django.db.models import CASCADE, SET_NULL, JSONField

from django.contrib.postgres.fields import ArrayField

from bpp.models import (
    BazaModeluStreszczen,
    MaProcentyMixin,
    ModelZKwartylami,
    ModelZOplataZaPublikacje,
    parse_informacje,
    wez_zakres_stron,
)
from bpp.models.abstract import (
    BazaModeluOdpowiedzialnosciAutorow,
    DodajAutoraMixin,
    DwaTytuly,
    ModelOpcjonalnieNieEksportowanyDoAPI,
    ModelPunktowany,
    ModelRecenzowany,
    ModelTypowany,
    ModelWybitny,
    ModelZAbsolutnymUrl,
    ModelZAdnotacjami,
    ModelZCharakterem,
    ModelZDOI,
    ModelZeStatusem,
    ModelZeSzczegolami,
    ModelZeZnakamiWydawniczymi,
    ModelZInformacjaZ,
    ModelZISSN,
    ModelZKonferencja,
    ModelZLiczbaCytowan,
    ModelZMiejscemPrzechowywania,
    ModelZNumeremZeszytu,
    ModelZOpenAccess,
    ModelZPBN_UID,
    ModelZPrzeliczaniemDyscyplin,
    ModelZPubmedID,
    ModelZRokiem,
    ModelZWWW,
    Wydawnictwo_Baza,
)
from bpp.models.system import Zewnetrzna_Baza_Danych
from bpp.models.util import ZapobiegajNiewlasciwymCharakterom


class Wydawnictwo_Ciagle_Autor(
    DirtyFieldsMixin,
    BazaModeluOdpowiedzialnosciAutorow,
):
    """Powiązanie autora do wydawnictwa ciągłego."""

    rekord = models.ForeignKey(
        "Wydawnictwo_Ciagle", CASCADE, related_name="autorzy_set"
    )

    class Meta:
        verbose_name = "powiązanie autora z wyd. ciągłym"
        verbose_name_plural = "powiązania autorów z wyd. ciągłymi"
        app_label = "bpp"
        ordering = ("kolejnosc",)
        unique_together = [
            ("rekord", "autor", "typ_odpowiedzialnosci"),
            # Tu musi być autor, inaczej admin nie pozwoli wyedytować
            ("rekord", "autor", "kolejnosc"),
        ]


class ModelZOpenAccessWydawnictwoCiagle(ModelZOpenAccess):
    openaccess_tryb_dostepu = models.ForeignKey(
        "Tryb_OpenAccess_Wydawnictwo_Ciagle",
        SET_NULL,
        verbose_name="OpenAccess: tryb dostępu",
        blank=True,
        null=True,
    )

    class Meta:
        abstract = True


class Wydawnictwo_Ciagle(
    ZapobiegajNiewlasciwymCharakterom,
    Wydawnictwo_Baza,
    DwaTytuly,
    ModelZRokiem,
    ModelZeStatusem,
    ModelZAbsolutnymUrl,
    ModelZWWW,
    ModelZPubmedID,
    ModelZDOI,
    ModelRecenzowany,
    ModelPunktowany,
    ModelTypowany,
    ModelZeSzczegolami,
    ModelZISSN,
    ModelZInformacjaZ,
    ModelZAdnotacjami,
    ModelZCharakterem,
    ModelZOpenAccessWydawnictwoCiagle,
    ModelZeZnakamiWydawniczymi,
    ModelZNumeremZeszytu,
    ModelZKonferencja,
    ModelWybitny,
    ModelZPBN_UID,
    ModelZOplataZaPublikacje,
    ModelZLiczbaCytowan,
    ModelZMiejscemPrzechowywania,
    ModelOpcjonalnieNieEksportowanyDoAPI,
    MaProcentyMixin,
    DodajAutoraMixin,
    DirtyFieldsMixin,
    ModelZPrzeliczaniemDyscyplin,
    ModelZKwartylami,
):
    """Wydawnictwo ciągłe, czyli artykuły z czasopism, komentarze, listy
    do redakcji, publikacje w suplemencie, etc."""

    autor_rekordu_klass = Wydawnictwo_Ciagle_Autor
    autorzy = models.ManyToManyField("Autor", through=autor_rekordu_klass)

    zrodlo = models.ForeignKey(
        "Zrodlo", null=True, verbose_name="Źródło", on_delete=models.SET_NULL
    )

    # To pole nie służy w bazie danych do niczego - jedyne co, to w adminie
    # w wygodny sposób chcemy wyświetlić przycisk 'uzupelnij punktacje', jak
    # się okazuje, przy używaniu standardowych procedur w Django jest to
    # z tego co na dziś dzień umiem, mocno utrudnione.
    uzupelnij_punktacje = models.BooleanField(default=False)

    class Meta:
        verbose_name = "wydawnictwo ciągłe"
        verbose_name_plural = "wydawnictwa ciągłe"
        app_label = "bpp"

    def punktacja_zrodla(self):
        """Funkcja - skrót do użycia w templatkach, zwraca punktację zrodla
        za rok z tego rekordu (self)"""

        from bpp.models.zrodlo import Punktacja_Zrodla

        if hasattr(self, "zrodlo_id") and self.zrodlo_id is not None:
            try:
                return self.zrodlo.punktacja_zrodla_set.get(rok=self.rok)
            except Punktacja_Zrodla.DoesNotExist:
                pass

    def numer_wydania(self):  # issue
        if hasattr(self, "nr_zeszytu"):
            if self.nr_zeszytu:
                return self.nr_zeszytu.strip()

        res = parse_informacje(self.informacje, "numer")
        if res is not None:
            return res.strip()

        return

    def numer_tomu(self):
        if hasattr(self, "tom"):
            if self.tom:
                return self.tom
        return parse_informacje(self.informacje, "tom")

    def zakres_stron(self):
        if self.strony:
            return self.strony
        else:
            strony = wez_zakres_stron(self.szczegoly)
            if strony:
                return strony

    #
    # Cache framework by django-denorm-iplweb
    #

    denorm_always_skip = ("ostatnio_zmieniony",)

    @denormalized(JSONField, blank=True, null=True)
    @depend_on_related(
        "bpp.Wydawnictwo_Ciagle_Autor",
        only=(
            "autor_id",
            "jednostka_id",
            "typ_odpowiedzialnosci_id",
            "afiliuje",
            "dyscyplina_naukowa_id",
            "upowaznienie_pbn",
            "przypieta",
        ),
    )
    def cached_punkty_dyscyplin(self):
        # TODO: idealnie byłoby uzależnić zmiane od pola 'rok' które by było identyczne
        # dla bpp.Poziom_Wydawcy, rok i id z nadrzędnego. Składnia SQLowa ewentualnie
        # jakis zapis django-podobny mile widziany.
        return self.przelicz_punkty_dyscyplin()

    @denormalized(models.TextField, default="")
    @depend_on_related(
        "bpp.Wydawnictwo_Ciagle_Autor",
        only=("zapisany_jako", "typ_odpowiedzialnosci_id", "kolejnosc"),
    )
    @depend_on_related("bpp.Zrodlo", only=("nazwa", "skrot"))
    @depend_on_related("bpp.Charakter_Formalny")
    @depend_on_related("bpp.Typ_KBN")
    @depend_on_related("bpp.Status_Korekty")
    def opis_bibliograficzny_cache(self):
        return self.opis_bibliograficzny()

    @denormalized(ArrayField, base_field=models.TextField(), blank=True, null=True)
    @depend_on_related(
        "bpp.Autor",
        only=(
            "nazwisko",
            "imiona",
        ),
    )
    @depend_on_related("bpp.Wydawnictwo_Ciagle_Autor", only=("kolejnosc",))
    def opis_bibliograficzny_autorzy_cache(self):
        return [
            f"{x.autor.nazwisko} {x.autor.imiona}" for x in self.autorzy_dla_opisu()
        ]

    @denormalized(models.TextField, blank=True, null=True)
    @depend_on_related(
        "bpp.Wydawnictwo_Ciagle_Autor",
        only=("zapisany_jako", "kolejnosc"),
    )
    def opis_bibliograficzny_zapisani_autorzy_cache(self):
        return ", ".join([x.zapisany_jako for x in self.autorzy_dla_opisu()])

    @denormalized(
        models.SlugField,
        max_length=400,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
    )
    @depend_on_related(
        "bpp.Wydawnictwo_Ciagle_Autor",
        only=("zapisany_jako", "kolejnosc"),
    )
    @depend_on_related(
        "bpp.Autor",
        only=("nazwisko", "imiona"),
    )
    @depend_on_related("bpp.Zrodlo", only=("nazwa", "skrot"))
    def slug(self):
        return self.get_slug()

    def clean(self):
        DwaTytuly.clean(self)
        ModelZOplataZaPublikacje.clean(self)


class Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych(models.Model):
    rekord = models.ForeignKey(
        Wydawnictwo_Ciagle, CASCADE, related_name="zewnetrzna_baza_danych"
    )
    baza = models.ForeignKey(Zewnetrzna_Baza_Danych, CASCADE)
    info = models.CharField(
        verbose_name="Informacje dodatkowe", max_length=512, blank=True, null=True
    )

    def __str__(self):
        return f"{self.baza}"

    class Meta:
        verbose_name = "powiązanie wyd. ciągłego z zewn. bazą danych"
        verbose_name_plural = "powiązania wyd. ciągłych z zewn. bazami danych"


class Wydawnictwo_Ciagle_Streszczenie(BazaModeluStreszczen):
    rekord = models.ForeignKey(Wydawnictwo_Ciagle, CASCADE, related_name="streszczenia")

    class Meta:
        verbose_name = "streszczenie wydawnictwa ciągłego"
        verbose_name_plural = "streszczenia wydawnictw ciągłych"

    def __str__(self):
        if self.jezyk_streszczenia_id is not None:
            return (
                f"Streszczenie rekordu {self.rekord} w języku {self.jezyk_streszczenia}"
            )
        return f"Streszczenie rekordu {self.rekord}"
