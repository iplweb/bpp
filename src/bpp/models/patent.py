from denorm import denormalized, depend_on_related
from django.db import models
from django.db.models import CASCADE, SET_NULL, JSONField

from django.contrib.postgres.fields import ArrayField

from django.utils.functional import cached_property

from bpp.models import (
    BazaModeluOdpowiedzialnosciAutorow,
    ModelOpcjonalnieNieEksportowanyDoAPI,
    ModelPunktowany,
    ModelRecenzowany,
    ModelZAdnotacjami,
    ModelZeStatusem,
    ModelZeSzczegolami,
    ModelZInformacjaZ,
    ModelZPrzeliczaniemDyscyplin,
    ModelZRokiem,
    ModelZWWW,
)
from bpp.models.abstract import (
    DodajAutoraMixin,
    MaProcentyMixin,
    ModelZAbsolutnymUrl,
    RekordBPPBaza,
)
from bpp.models.autor import Autor
from bpp.models.system import Charakter_Formalny, Jezyk
from bpp.util import safe_html


class Patent_Autor(BazaModeluOdpowiedzialnosciAutorow):
    """Powiązanie autora do patentu."""

    rekord = models.ForeignKey("Patent", CASCADE, related_name="autorzy_set")

    class Meta:
        verbose_name = "powiązanie autora z patentem"
        verbose_name_plural = "powiązania autorów z patentami"
        app_label = "bpp"
        ordering = ("kolejnosc",)
        unique_together = [
            ("rekord", "autor", "typ_odpowiedzialnosci"),
            # Tu musi być autor, inaczej admin nie pozwoli wyedytować
            ("rekord", "autor", "kolejnosc"),
        ]


class _Patent_PropertyCache:
    @cached_property
    def charakter_formalny(self):
        return Charakter_Formalny.objects.get(skrot="PAT")

    @cached_property
    def jezyk(self):
        return Jezyk.objects.get(nazwa__icontains="polski")


_Patent_PropertyCache = _Patent_PropertyCache()


class Patent(
    RekordBPPBaza,
    ModelZRokiem,
    ModelZeStatusem,
    ModelZWWW,
    ModelRecenzowany,
    ModelPunktowany,
    ModelZeSzczegolami,
    ModelZInformacjaZ,
    ModelZAdnotacjami,
    MaProcentyMixin,
    DodajAutoraMixin,
    ModelZAbsolutnymUrl,
    ModelOpcjonalnieNieEksportowanyDoAPI,
    ModelZPrzeliczaniemDyscyplin,
):
    tytul_oryginalny = models.TextField("Tytuł oryginalny", db_index=True)

    data_zgloszenia = models.DateField("Data zgłoszenia", null=True, blank=True)

    numer_zgloszenia = models.CharField(
        "Numer zgłoszenia", max_length=255, null=True, blank=True
    )

    data_decyzji = models.DateField(null=True, blank=True)

    numer_prawa_wylacznego = models.CharField(
        "Numer prawa wyłącznego", max_length=255, null=True, blank=True
    )

    rodzaj_prawa = models.ForeignKey(
        "bpp.Rodzaj_Prawa_Patentowego", CASCADE, null=True, blank=True
    )

    wdrozenie = models.BooleanField("Wdrożenie", null=True, blank=True, default=None)

    wydzial = models.ForeignKey("bpp.Wydzial", SET_NULL, null=True, blank=True)

    autor_rekordu_klass = Patent_Autor
    autorzy = models.ManyToManyField(Autor, through=autor_rekordu_klass)

    class Meta:
        verbose_name = "patent"
        verbose_name_plural = "patenty"
        app_label = "bpp"

    def __str__(self):
        return self.tytul_oryginalny

    @cached_property
    def charakter_formalny(self):
        return _Patent_PropertyCache.charakter_formalny

    @cached_property
    def jezyk(self):
        return _Patent_PropertyCache.jezyk

    def clean(self):
        # DwaTytuly.clean() w wydaniu jedno-tytułowym...
        self.tytul_oryginalny = safe_html(self.tytul_oryginalny)

    #
    # Cache framework by django-denorm-iplweb
    #

    denorm_always_skip = ("ostatnio_zmieniony",)

    @denormalized(JSONField, blank=True, null=True)
    @depend_on_related(
        "bpp.Patent_Autor",
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
        "bpp.Patent_Autor",
        only=("zapisany_jako", "typ_odpowiedzialnosci_id", "kolejnosc"),
    )
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
    @depend_on_related("bpp.Patent_Autor", only=("kolejnosc",))
    def opis_bibliograficzny_autorzy_cache(self):
        return [
            f"{x.autor.nazwisko} {x.autor.imiona}" for x in self.autorzy_dla_opisu()
        ]

    @denormalized(models.TextField, blank=True, null=True)
    @depend_on_related(
        "bpp.Patent_Autor",
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
        "bpp.Patent_Autor",
        only=("zapisany_jako", "kolejnosc"),
    )
    @depend_on_related(
        "bpp.Autor",
        only=("nazwisko", "imiona"),
    )
    def slug(self):
        return self.get_slug()
