import re
import warnings

from denorm import denormalized, depend_on_related
from dirtyfields.dirtyfields import DirtyFieldsMixin
from django.db import models
from django.db.models import CASCADE, PROTECT, JSONField
from django.db.models.expressions import RawSQL

from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField

from bpp.models import (
    BazaModeluStreszczen,
    DodajAutoraMixin,
    ManagerModeliZOplataZaPublikacjeMixin,
    MaProcentyMixin,
    ModelOpcjonalnieNieEksportowanyDoAPI,
    ModelZMiejscemPrzechowywania,
    ModelZOplataZaPublikacje,
    ModelZPBN_UID,
)
from bpp.models.abstract import (
    BazaModeluOdpowiedzialnosciAutorow,
    DwaTytuly,
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
    ModelZISBN,
    ModelZISSN,
    ModelZKonferencja,
    ModelZLiczbaCytowan,
    ModelZOpenAccess,
    ModelZPrzeliczaniemDyscyplin,
    ModelZPubmedID,
    ModelZRokiem,
    ModelZSeria_Wydawnicza,
    ModelZWWW,
    Wydawnictwo_Baza,
)
from bpp.models.autor import Autor
from bpp.models.nagroda import Nagroda
from bpp.models.system import Zewnetrzna_Baza_Danych
from bpp.models.util import ZapobiegajNiewlasciwymCharakterom
from bpp.models.wydawca import Wydawca


class Wydawnictwo_Zwarte_Autor(
    DirtyFieldsMixin,
    BazaModeluOdpowiedzialnosciAutorow,
):
    """Model zawierający informację o przywiązaniu autorów do wydawnictwa
    zwartego."""

    rekord = models.ForeignKey(
        "Wydawnictwo_Zwarte", CASCADE, related_name="autorzy_set"
    )

    class Meta:
        verbose_name = "powiązanie autora z wyd. zwartym"
        verbose_name_plural = "powiązania autorów z wyd. zwartymi"
        app_label = "bpp"
        ordering = ("kolejnosc",)
        unique_together = [
            ("rekord", "autor", "typ_odpowiedzialnosci"),
            # Tu musi być autor, inaczej admin nie pozwoli wyedytować
            ("rekord", "autor", "kolejnosc"),
        ]


MIEJSCE_I_ROK_MAX_LENGTH = 256


class Wydawnictwo_Zwarte_Baza(
    Wydawnictwo_Baza,
    DwaTytuly,
    ModelZRokiem,
    ModelZeStatusem,
    ModelZWWW,
    ModelZPubmedID,
    ModelZDOI,
    ModelRecenzowany,
    ModelPunktowany,
    ModelTypowany,
    ModelZeSzczegolami,
    ModelZInformacjaZ,
    ModelZISBN,
    ModelZAdnotacjami,
    ModelZAbsolutnymUrl,
    ModelZLiczbaCytowan,
    ModelZMiejscemPrzechowywania,
    ModelOpcjonalnieNieEksportowanyDoAPI,
):
    """Baza dla klas Wydawnictwo_Zwarte oraz Praca_Doktorska_Lub_Habilitacyjna"""

    miejsce_i_rok = models.CharField(
        max_length=MIEJSCE_I_ROK_MAX_LENGTH,
        blank=True,
        null=True,
        help_text="""Przykładowo:
        Warszawa 2012. Wpisz proszę najpierw miejsce potem rok; oddziel
        spacją.""",
    )

    wydawca = models.ForeignKey(Wydawca, PROTECT, null=True, blank=True)
    wydawca_opis = models.CharField(
        "Wydawca - szczegóły", max_length=256, null=True, blank=True
    )

    oznaczenie_wydania = models.CharField(max_length=400, null=True, blank=True)

    def get_wydawnictwo(self):
        # Zwróć nazwę wydawcy + pole wydawca_opis lub samo pole wydawca_opis, jeżeli
        # wydawca (indeksowany) nie jest ustalony
        if self.wydawca_id is None:
            return self.wydawca_opis

        opis = self.wydawca_opis or ""
        try:
            if opis[0] in ".;-/,":
                # Nie wstawiaj spacji między wydawcę a opis jeżeli zaczyna się od kropki, przecinka itp
                return f"{self.wydawca.nazwa}{opis}".strip()
        except IndexError:
            pass

        return f"{self.wydawca.nazwa} {opis}".strip()

    def set_wydawnictwo(self, value):
        warnings.warn("W przyszlosci uzyj 'wydawca_opis'", DeprecationWarning)
        self.wydawca_opis = value

    wydawnictwo = property(get_wydawnictwo, set_wydawnictwo)

    redakcja = models.TextField(null=True, blank=True)

    class Meta:
        abstract = True


class ModelZOpenAccessWydawnictwoZwarte(ModelZOpenAccess):
    openaccess_tryb_dostepu = models.ForeignKey(
        "Tryb_OpenAccess_Wydawnictwo_Zwarte", CASCADE, blank=True, null=True
    )

    class Meta:
        abstract = True


rok_regex = re.compile(r"\s[12]\d\d\d")


class Wydawnictwo_Zwarte_Manager(ManagerModeliZOplataZaPublikacjeMixin, models.Manager):
    def wydawnictwa_nadrzedne_dla_innych(self):
        return (
            self.exclude(wydawnictwo_nadrzedne_id=None)
            .values_list("wydawnictwo_nadrzedne_id", flat=True)
            .distinct()
        )


class Wydawnictwo_Zwarte(
    ZapobiegajNiewlasciwymCharakterom,
    Wydawnictwo_Zwarte_Baza,
    ModelZCharakterem,
    ModelZOpenAccessWydawnictwoZwarte,
    ModelZeZnakamiWydawniczymi,
    ModelZKonferencja,
    ModelZSeria_Wydawnicza,
    ModelZISSN,
    ModelWybitny,
    ModelZPBN_UID,
    ModelZOplataZaPublikacje,
    MaProcentyMixin,
    DodajAutoraMixin,
    DirtyFieldsMixin,
    ModelZPrzeliczaniemDyscyplin,
):
    """Wydawnictwo zwarte, czyli: książki, broszury, skrypty, fragmenty,
    doniesienia zjazdowe."""

    objects = Wydawnictwo_Zwarte_Manager()

    autor_rekordu_klass = Wydawnictwo_Zwarte_Autor
    autorzy = models.ManyToManyField(Autor, through=autor_rekordu_klass)

    wydawnictwo_nadrzedne = models.ForeignKey(
        "self",
        CASCADE,
        blank=True,
        null=True,
        help_text="""Jeżeli dodajesz rozdział,
        tu wybierz pracę, w ramach której dany rozdział występuje.""",
        related_name="wydawnictwa_powiazane_set",
    )

    calkowita_liczba_autorow = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="""Jeżeli dodajesz monografię, wpisz
        tutaj całkowitą liczbę autorów monografii. Ta informacja zostanie
        użyta w eksporcie danych do PBN. Jeżeli informacja ta nie zostanie
        uzupełiona, wartość tego pola zostanie obliczona i będzie to ilość
        wszystkich autorów przypisanych do danej monografii""",
    )

    calkowita_liczba_redaktorow = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="""Jeżeli dodajesz monografię, wpisz tutaj całkowitą liczbę
        redaktorów monografii. Ta informacja zostanie użyta w eksporcie
        danych do PBN. Jeżeli pole to nie zostanie uzupełnione, wartość ta
        zostanie obliczona i będzie to ilość wszystkich redaktorów
        przypisanych do danej monografii""",
    )

    nagrody = GenericRelation(Nagroda)

    class Meta:
        verbose_name = "wydawnictwo zwarte"
        verbose_name_plural = "wydawnictwa zwarte"
        app_label = "bpp"

    def wydawnictwa_powiazane_posortowane(self):
        """
        Sortowanie wydawnictw powiązanych wg pierwszej liczby dziesiętnej występującej w polu 'Strony'
        """
        return self.wydawnictwa_powiazane_set.order_by(
            RawSQL(
                r"CAST((regexp_match(COALESCE(bpp_wydawnictwo_zwarte.strony, '99999999'), '(\d+)'))[1] AS INT)",
                "",
            )
        )

    #
    # Cache framework by django-denorm-iplweb
    #

    denorm_always_skip = ("ostatnio_zmieniony",)

    @denormalized(JSONField, blank=True, null=True)
    @depend_on_related(
        "bpp.Wydawnictwo_Zwarte_Autor",
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
    @depend_on_related("bpp.Wydawca", only=("lista_poziomow", "alias_dla_id"))
    def cached_punkty_dyscyplin(self):
        # TODO: idealnie byłoby uzależnić zmiane od pola 'rok' które by było identyczne
        # dla bpp.Poziom_Wydawcy, rok i id z nadrzędnego. Składnia SQLowa ewentualnie
        # jakis zapis django-podobny mile widziany.
        return self.przelicz_punkty_dyscyplin()

    @denormalized(models.TextField, default="")
    @depend_on_related("self", "wydawnictwo_nadrzedne")
    @depend_on_related(
        "bpp.Wydawnictwo_Zwarte_Autor",
        only=("zapisany_jako", "typ_odpowiedzialnosci_id", "kolejnosc"),
    )
    @depend_on_related("bpp.Wydawca", only=("nazwa", "alias_dla_id"))
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
    @depend_on_related("bpp.Wydawnictwo_Zwarte_Autor", only=("kolejnosc",))
    def opis_bibliograficzny_autorzy_cache(self):
        return [
            f"{x.autor.nazwisko} {x.autor.imiona}" for x in self.autorzy_dla_opisu()
        ]

    @denormalized(models.TextField, blank=True, null=True)
    @depend_on_related(
        "bpp.Wydawnictwo_Zwarte_Autor",
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
        "bpp.Wydawnictwo_Zwarte_Autor",
        only=("zapisany_jako", "kolejnosc"),
    )
    @depend_on_related(
        "bpp.Autor",
        only=("nazwisko", "imiona"),
    )
    @depend_on_related("self", "wydawnictwo_nadrzedne")
    def slug(self):
        return self.get_slug()

    def clean(self):
        DwaTytuly.clean(self)
        ModelZOplataZaPublikacje.clean(self)


class Wydawnictwo_Zwarte_Zewnetrzna_Baza_Danych(models.Model):
    rekord = models.ForeignKey(
        Wydawnictwo_Zwarte, CASCADE, related_name="zewnetrzna_baza_danych"
    )
    baza = models.ForeignKey(Zewnetrzna_Baza_Danych, CASCADE)
    info = models.CharField(
        verbose_name="Informacje dodatkowe", max_length=512, blank=True, null=True
    )

    class Meta:
        verbose_name = "powiązanie wyd. zwartego z zewn. bazami danych"
        verbose_name_plural = "powiązania wyd. zwartych z zewn. bazami danych"


class Wydawnictwo_Zwarte_Streszczenie(BazaModeluStreszczen):
    rekord = models.ForeignKey(Wydawnictwo_Zwarte, CASCADE, related_name="streszczenia")

    class Meta:
        verbose_name = "streszczenie wydawnictwa zwartego"
        verbose_name_plural = "streszczenia wydawnictw zwatrtych"

    def __str__(self):
        try:
            str(self.rekord)
        except Wydawnictwo_Zwarte.DoesNotExist:
            # Może nie istnieć w sytuacji, gdy jesteśmy w trakcie kasowania rekordu, zaś easyaudit
            # chce zalogować takie wydarzenie.
            return f"Streszczenie usuniętego rekordu o ID: {self.rekord_id}"

        if self.jezyk_streszczenia_id is not None:
            return (
                f"Streszczenie rekordu {self.rekord} w języku {self.jezyk_streszczenia}"
            )
        return f"Streszczenie rekordu {self.rekord}"
