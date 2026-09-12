from denorm import denormalized, depend_on_fields, depend_on_related
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import ArrayField, RangeOperators
from django.db import models
from django.db.models import CASCADE, SET_NULL, Deferrable, JSONField, Q
from django.utils.functional import cached_property

from bpp.models import (
    BazaModeluOdpowiedzialnosciAutorow,
    ModelOpcjonalnieNieEksportowanyDoAPI,
    ModelPunktowany,
    ModelRecenzowany,
    ModelZAdnotacjami,
    ModelZeSlowamiKluczowymi,
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
from bpp.models.soft_delete import (
    BppAutorstwoSoftDeleteMixin,
    BppPublikacjaSoftDeleteMixin,
)
from bpp.models.system import Charakter_Formalny, Jezyk
from bpp.util import safe_tytul_html


class Patent_Autor(BppAutorstwoSoftDeleteMixin, BazaModeluOdpowiedzialnosciAutorow):
    """Powiązanie autora do patentu."""

    rekord = models.ForeignKey(
        "Patent",
        CASCADE,
        related_name="autorzy_set",
        # Task 3c: `db_index=False` było tu uzasadnione, dopóki
        # `unique_together` dawało pełny (nie częściowy) indeks btree z
        # `rekord` jako kolumną wiodącą. Warunkowe UniqueConstraint/
        # ExclusionConstraint z Taska 3c są CZĘŚCIOWE
        # (`WHERE deleted_at IS NULL`) — nie pokrywają zapytań po samym
        # `rekord` bez tego predykatu: RI-check Postgresa przy DELETE
        # rodzica, kolektor kaskady Django (`_base_manager`, bez filtra
        # soft-delete) i `global_objects`/`deleted_objects`.filter(rekord=…)
        # (czyli dokładnie zapytania, po które soft-delete istnieje).
        # Zwykły indeks FK (domyślny dla ForeignKey) jest więc znów
        # potrzebny — NIE ustawiaj tu `db_index=False`.
    )

    class Meta:
        verbose_name = "powiązanie autora z patentem"
        verbose_name_plural = "powiązania autorów z patentami"
        app_label = "bpp"
        ordering = ("kolejnosc",)
        # `unique_together` widziałby też wiersze soft-deleted (fizycznie
        # wciąż są w tabeli) i blokowałby wzorzec "skasuj i wstaw od nowa"
        # (re-import, korekta kolejności, edycja inline). Warunkowy
        # UniqueConstraint (condition=deleted_at__isnull) pilnuje unikalności
        # TYLKO wśród żywych wierszy. Django `validate_unique()` W OGÓLE nie
        # patrzy na `Meta.constraints` (mechanizmem jest osobny
        # `Model.validate_constraints()`, Django >=4.1) — a TEN wymaga, żeby
        # pole użyte w `condition` (`deleted_at`) nie było wykluczone z
        # walidacji formularza, inaczej cicho pomija sprawdzenie (albo, dla
        # ExclusionConstraint, rzuca gołym FieldError). Stąd `deleted_at`
        # jest jawnym, ukrytym polem w `generuj_formularz_dla_autorow`
        # (`bpp.admin.core`). Formset inline ma DODATKOWO ręczną walidację
        # kolizji nowy-wiersz-vs-istniejący-w-tym-samym-submicie
        # (`generuj_inline_dla_autorow`) — patrz Task 3c, raport.
        constraints = [
            models.UniqueConstraint(
                fields=["rekord", "autor", "typ_odpowiedzialnosci"],
                condition=Q(deleted_at__isnull=True),
                name="pat_autor_uniq_rekord_autor_typ",
            ),
            # NIE MA tu `UniqueConstraint(rekord, autor, kolejnosc)` —
            # `pat_autor_excl_rekord_kolejnosc` niżej jest ściśle silniejszy
            # (nie patrzy na autora); patrz komentarz w
            # `Wydawnictwo_Ciagle_Autor.Meta`.
            # Odpowiednik legacy `ALTER TABLE ... UNIQUE (rekord_id,
            # kolejnosc) DEFERRABLE INITIALLY DEFERRED` z migracji 0132 —
            # patrz analogiczny komentarz w Wydawnictwo_Ciagle_Autor.Meta.
            ExclusionConstraint(
                name="pat_autor_excl_rekord_kolejnosc",
                expressions=[
                    ("rekord", RangeOperators.EQUAL),
                    ("kolejnosc", RangeOperators.EQUAL),
                ],
                condition=Q(deleted_at__isnull=True),
                deferrable=Deferrable.DEFERRED,
            ),
        ]
        indexes = [
            # Indeks CZĘŚCIOWY — patrz uzasadnienie w
            # `Wydawnictwo_Ciagle_Autor.Meta.indexes`.
            models.Index(
                fields=["deleted_at"],
                name="patent_autor_deleted_at_idx",
                condition=Q(deleted_at__isnull=False),
            ),
        ]

    # django-denorm buduje bramkę WHEN triggera z listy `only=` w
    # @depend_on_related. Bez deleted_at soft-delete autorstwa nie
    # unieważniłby denorm-cache rodzica (opis bibliograficzny, slug,
    # cached_punkty_dyscyplin) — zostałby nieświeży na stałe.
    denorm_always_only = ("deleted_at",)


class _Patent_PropertyCache:
    @cached_property
    def charakter_formalny(self):
        return Charakter_Formalny.objects.get(skrot="PAT")

    @cached_property
    def jezyk(self):
        return Jezyk.objects.get(nazwa__icontains="polski")


_Patent_PropertyCache = _Patent_PropertyCache()


class Patent(
    BppPublikacjaSoftDeleteMixin,
    RekordBPPBaza,
    ModelZRokiem,
    ModelZeStatusem,
    ModelZWWW,
    ModelRecenzowany,
    ModelPunktowany,
    ModelZeSzczegolami,
    ModelZeSlowamiKluczowymi,
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

    numer_zgloszenia = models.CharField(  # noqa: DJ001
        # legacy null=True (jest na produkcji); zmiana wymagałaby migracji.
        "Numer zgłoszenia",
        max_length=255,
        null=True,
        blank=True,
    )

    data_decyzji = models.DateField(null=True, blank=True)

    numer_prawa_wylacznego = models.CharField(  # noqa: DJ001
        # legacy null=True (jest na produkcji); zmiana wymagałaby migracji.
        "Numer prawa wyłącznego",
        max_length=255,
        null=True,
        blank=True,
    )

    rodzaj_prawa = models.ForeignKey(
        "bpp.Rodzaj_Prawa_Patentowego", CASCADE, null=True, blank=True
    )

    wdrozenie = models.BooleanField("Wdrożenie", null=True, blank=True, default=None)

    wydzial = models.ForeignKey("bpp.Jednostka", SET_NULL, null=True, blank=True)

    autor_rekordu_klass = Patent_Autor
    autorzy = models.ManyToManyField(Autor, through=autor_rekordu_klass)

    class Meta:
        verbose_name = "patent"
        verbose_name_plural = "patenty"
        app_label = "bpp"
        indexes = [
            # Indeks CZĘŚCIOWY — uzasadnienie przy `wc_deleted_at_idx`
            # (`wydawnictwo_ciagle.py`, Meta klasy Wydawnictwo_Ciagle).
            models.Index(
                fields=["deleted_at"],
                name="patent_deleted_at_idx",
                condition=Q(deleted_at__isnull=False),
            ),
        ]

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
        self.tytul_oryginalny = safe_tytul_html(self.tytul_oryginalny)
        ModelZeSzczegolami.clean(self)

    def save(self, *args, **kwargs):
        # Egzekwuj sanityzację tytułu także na ścieżce objects.create()/import,
        # która nie woła full_clean().
        self.tytul_oryginalny = safe_tytul_html(self.tytul_oryginalny)
        return super().save(*args, **kwargs)

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
    @depend_on_fields("tytul_oryginalny")
    def slug(self):
        return self.get_slug()

    def to_bibtex(self):
        """Export this patent to BibTeX format."""
        from bpp.export.bibtex import patent_to_bibtex

        return patent_to_bibtex(self)
