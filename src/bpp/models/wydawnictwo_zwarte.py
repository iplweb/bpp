import re
import warnings

from denorm import denormalized, depend_on_fields, depend_on_related
from dirtyfields.dirtyfields import DirtyFieldsMixin
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import ArrayField, RangeOperators
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CASCADE, PROTECT, Deferrable, JSONField, Q
from django.db.models.expressions import RawSQL

from bpp import const
from bpp.models import (
    BazaModeluStreszczen,
    BazaModeluTytulow,
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
    ModelZeSlowamiKluczowymi,
    ModelZeStatusem,
    ModelZeSzczegolami,
    ModelZeZnakamiWydawniczymi,
    ModelZInformacjaZ,
    ModelZISBN,
    ModelZISSN,
    ModelZKonferencja,
    ModelZLiczbaCytowan,
    ModelZOpenAccess,
    ModelZPolamiEwaluacjiPBN,
    ModelZPrzeliczaniemDyscyplin,
    ModelZPubmedID,
    ModelZRokiem,
    ModelZSeria_Wydawnicza,
    ModelZWWW,
    Wydawnictwo_Baza,
)
from bpp.models.autor import Autor
from bpp.models.nagroda import Nagroda
from bpp.models.soft_delete import (
    BppAutorstwoSoftDeleteMixin,
    BppPublikacjaSoftDeleteMixin,
    BppSoftDeleteManager,
)
from bpp.models.system import Zewnetrzna_Baza_Danych
from bpp.models.util import ZapobiegajNiewlasciwymCharakterom
from bpp.models.wydawca import Wydawca


class Wydawnictwo_Zwarte_Autor(
    DirtyFieldsMixin,
    BppAutorstwoSoftDeleteMixin,
    BazaModeluOdpowiedzialnosciAutorow,
):
    """Model zawierający informację o przywiązaniu autorów do wydawnictwa
    zwartego."""

    rekord = models.ForeignKey(
        "Wydawnictwo_Zwarte",
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
        verbose_name = "powiązanie autora z wyd. zwartym"
        verbose_name_plural = "powiązania autorów z wyd. zwartymi"
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
                name="wz_autor_uniq_rekord_autor_typ",
            ),
            # NIE MA tu `UniqueConstraint(rekord, autor, kolejnosc)` —
            # `wz_autor_excl_rekord_kolejnosc` niżej jest ściśle silniejszy
            # (nie patrzy na autora); patrz komentarz w
            # `Wydawnictwo_Ciagle_Autor.Meta`.
            # Odpowiednik legacy `ALTER TABLE ... UNIQUE (rekord_id,
            # kolejnosc) DEFERRABLE INITIALLY DEFERRED` z migracji 0132 —
            # patrz analogiczny komentarz w Wydawnictwo_Ciagle_Autor.Meta.
            ExclusionConstraint(
                name="wz_autor_excl_rekord_kolejnosc",
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
                name="wz_autor_deleted_at_idx",
                condition=Q(deleted_at__isnull=False),
            ),
        ]

    # django-denorm buduje bramkę WHEN triggera z listy `only=` w
    # @depend_on_related. Bez deleted_at soft-delete autorstwa nie
    # unieważniłby denorm-cache rodzica (opis bibliograficzny, slug,
    # cached_punkty_dyscyplin) — zostałby nieświeży na stałe.
    denorm_always_only = ("deleted_at",)


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
    ModelZeSlowamiKluczowymi,
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
        default="",
        help_text="""Przykładowo:
        Warszawa 2012. Wpisz proszę najpierw miejsce potem rok; oddziel
        spacją.""",
    )

    # Auto-indeks FK redundantny: każda konkretna tabela dziedzicząca
    # Wydawnictwo_Zwarte_Baza (wydawnictwo_zwarte, praca_doktorska,
    # praca_habilitacyjna) ma raw-indeks <tabela>_wydawca_rok (wydawca_id, rok)
    # z migracji 0172 — wydawca jest tam wiodący, więc pokrywa lookup i PROTECT.
    wydawca = models.ForeignKey(Wydawca, PROTECT, null=True, blank=True, db_index=False)
    wydawca_opis = models.CharField(
        "Wydawca - szczegóły", max_length=256, blank=True, default=""
    )

    oznaczenie_wydania = models.CharField(max_length=400, blank=True, default="")

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
        warnings.warn(
            "W przyszlosci uzyj 'wydawca_opis'", DeprecationWarning, stacklevel=2
        )
        self.wydawca_opis = value

    wydawnictwo = property(get_wydawnictwo, set_wydawnictwo)

    redakcja = models.TextField(blank=True, default="")

    class Meta:
        abstract = True


class ModelZOpenAccessWydawnictwoZwarte(ModelZOpenAccess):
    openaccess_tryb_dostepu = models.ForeignKey(
        "Tryb_OpenAccess_Wydawnictwo_Zwarte", CASCADE, blank=True, null=True
    )

    class Meta:
        abstract = True


rok_regex = re.compile(r"\s[12]\d\d\d")


class Wydawnictwo_Zwarte_Manager(
    ManagerModeliZOplataZaPublikacjeMixin, BppSoftDeleteManager
):
    """Jak ``Wydawnictwo_Ciagle_Manager`` — uzasadnienie doboru bazy
    (i tego, dlaczego kolejność NIE jest nośna) w jego docstringu
    (``wydawnictwo_ciagle.py``).

    ``wydawnictwa_nadrzedne_dla_innych()`` też korzysta na przepleceniu:
    po fazie 02 nie zwróci już książki-matki, której jedyne rozdziały
    trafiły do kosza.
    """

    def wydawnictwa_nadrzedne_dla_innych(self):
        return (
            self.exclude(wydawnictwo_nadrzedne_id=None)
            .values_list("wydawnictwo_nadrzedne_id", flat=True)
            .distinct()
        )


class Wydawnictwo_Zwarte(
    BppPublikacjaSoftDeleteMixin,
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
    ModelZPolamiEwaluacjiPBN,
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

    # PROTECT, nie CASCADE (faza 04 soft-delete): skasowanie książki-matki nie
    # ma prawa zabrać ze sobą rozdziałów — to osobne rekordy bibliograficzne,
    # każdy z własnymi autorami, punktacją i historią w PBN. Miękkie kasowanie
    # blokuje guard w ``Wydawnictwo_Zwarte.delete()``.
    wydawnictwo_nadrzedne = models.ForeignKey(
        "self",
        PROTECT,
        blank=True,
        null=True,
        help_text="""Jeżeli dodajesz rozdział,
        tu wybierz pracę, w ramach której dany rozdział występuje.""",
        related_name="wydawnictwa_powiazane_set",
    )

    wydawnictwo_nadrzedne_w_pbn = models.ForeignKey(
        "pbn_api.Publication",
        models.PROTECT,
        blank=True,
        null=True,
        verbose_name="Wydawnictwo nadrzędne w PBN",
        help_text="""Jeżeli ten rekord to rozdział, a redakcja książki nie jest z obecnej instytucji, możesz uzupełnić
        to pole, aby móc wysłać 'swój' rozdział do PBNu i jednocześnie nie musieć dodawać do bazy BPP 'cudzej' książki.
        Innymi słowy, jeżeli 'okładki' dla Twojego rozdziału znajdują się w PBN i nie chcesz ich dodawać do BPP,
        to skorzystaj z tego pola. Jeżeli jednak wypełnisz to pole, to musisz pozostawić oryginalne
        'Wydawnictwo nadrzędne' puste. """,
        related_name="+",
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
        indexes = [
            # Indeks CZĘŚCIOWY — uzasadnienie przy `wc_deleted_at_idx`
            # (`wydawnictwo_ciagle.py`, Meta klasy Wydawnictwo_Ciagle).
            models.Index(
                fields=["deleted_at"],
                name="wz_deleted_at_idx",
                condition=Q(deleted_at__isnull=False),
            ),
        ]

    def delete(self, *args, user=None, reason="", **kwargs):
        """Soft-delete książki — zablokowany, dopóki wiszą na niej rozdziały.

        DLACZEGO TU, A NIE WE WSPÓLNYM MIXINIE: ``BppPublikacjaSoftDelete
        Mixin`` dzielą wszystkie pięć modeli publikacji. Guard wstawiony tam
        odpytywałby dla ``Wydawnictwo_Ciagle``, ``Patent`` czy prac
        dyplomowych ``Wydawnictwo_Zwarte.global_objects.filter(
        wydawnictwo_nadrzedne=<obiekt innego modelu>)`` — zapytanie
        międzytypowe, w najlepszym razie zawsze puste, w gorszym wyjątek.
        Self-FK jest cechą TEGO modelu, więc guard jest jego metodą.

        Guard idzie PRZED ``super().delete()``, czyli przed zapisem
        ``deleted_at`` i przed kaskadą fazy 02 na ``*_Autor`` — odmowa ma
        być odmową, a nie odmową po fakcie. Kaskady nie gubimy: cała reszta
        pracy zostaje w mixinie, tutaj dokładamy wyłącznie warunek wstępny.

        Rozdział w koszu też blokuje (liczymy przez ``global_objects``,
        spec §2.6): inaczej książkę dałoby się usunąć w dwóch krokach —
        najpierw rozdział, potem ją — a przywrócenie rozdziału zostawiłoby
        go bez książki-matki.

        ``user``/``reason`` przepuszczamy dalej do mixinu (kontrakt PINNED
        faz 06/07) — własny ``delete()`` przesłania tamten, więc gdyby ich
        tu zabrakło, kasowanie z powodem z panelu admina wywaliłoby się
        ``TypeError``-em na każdej książce.
        """
        from bpp.models.soft_delete import raise_if_has_protected_children

        raise_if_has_protected_children(
            self,
            [(Wydawnictwo_Zwarte, "wydawnictwo_nadrzedne")],
            label="książki (ma rozdziały)",
        )
        return super().delete(*args, user=user, reason=reason, **kwargs)

    delete.alters_data = True

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
    @depend_on_fields("tytul_oryginalny", "wydawnictwo_nadrzedne_id")
    def slug(self):
        return self.get_slug()

    def to_bibtex(self):
        """Export this publication to BibTeX format."""
        from bpp.export.bibtex import wydawnictwo_zwarte_to_bibtex

        return wydawnictwo_zwarte_to_bibtex(self)

    def clean(self):
        DwaTytuly.clean(self)
        ModelZeSzczegolami.clean(self)
        ModelZOplataZaPublikacje.clean(self)

        if (
            self.wydawnictwo_nadrzedne_w_pbn_id is not None
            and self.wydawnictwo_nadrzedne_id is not None
        ):
            raise ValidationError(
                {
                    "wydawnictwo_nadrzedne": "Jeżeli chcesz ustawić pole 'Wydawnictwo nadrzędne w PBN' to musisz "
                    "usunąć wartośc z tego pola. ",
                    "wydawnictwo_nadrzedne_w_pbn": "Jeżeli chcesz ustawić pole 'Wydawnictwo nadrzędne w PBN' to "
                    "musisz wyczyścić wartość w polu 'Wydawnictwo nadrzędne'. ",
                }
            )

    def warunek_redakcja(self):
        from bpp.models import Typ_Odpowiedzialnosci

        return Typ_Odpowiedzialnosci.objects.filter(
            pk__in=self.autorzy_set.values_list("typ_odpowiedzialnosci_id"),
            typ_ogolny=const.TO_REDAKTOR,
        ).exists()

    def warunek_autorstwo(self):
        from bpp.models import Typ_Odpowiedzialnosci

        return Typ_Odpowiedzialnosci.objects.filter(
            pk__in=self.autorzy_set.values_list("typ_odpowiedzialnosci_id"),
            typ_ogolny=const.TO_AUTOR,
        ).exists()

    def warunek_ksiazka(self):
        if self.charakter_formalny.charakter_sloty == const.CHARAKTER_SLOTY_KSIAZKA:
            return True

    def warunek_rozdzial(self):
        if self.charakter_formalny.charakter_sloty == const.CHARAKTER_SLOTY_ROZDZIAL:
            return True


class Wydawnictwo_Zwarte_Zewnetrzna_Baza_Danych(models.Model):
    rekord = models.ForeignKey(
        Wydawnictwo_Zwarte, CASCADE, related_name="zewnetrzna_baza_danych"
    )
    baza = models.ForeignKey(Zewnetrzna_Baza_Danych, CASCADE)
    info = models.CharField(
        verbose_name="Informacje dodatkowe", max_length=512, blank=True, default=""
    )

    class Meta:
        verbose_name = "powiązanie wyd. zwartego z zewn. bazami danych"
        verbose_name_plural = "powiązania wyd. zwartych z zewn. bazami danych"


class Wydawnictwo_Zwarte_Tytul(BazaModeluTytulow):
    rekord = models.ForeignKey(
        Wydawnictwo_Zwarte, CASCADE, related_name="dodatkowe_tytuly"
    )

    class Meta:
        verbose_name = "dodatkowy tytuł wydawnictwa zwartego"
        verbose_name_plural = "dodatkowe tytuły wydawnictw zwartych"
        unique_together = [("rekord", "kod_jezyka_pbn")]

    def __str__(self):
        return f"Tytuł rekordu {self.rekord_id} w języku {self.kod_jezyka_pbn}"


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
