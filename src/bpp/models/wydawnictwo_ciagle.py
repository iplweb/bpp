from denorm import denormalized, depend_on_fields, depend_on_related
from dirtyfields.dirtyfields import DirtyFieldsMixin
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import ArrayField, RangeOperators
from django.db import models
from django.db.models import CASCADE, SET_NULL, Deferrable, JSONField, Q

from bpp.models import (
    BazaModeluStreszczen,
    BazaModeluTytulow,
    ManagerModeliZOplataZaPublikacjeMixin,
    MaProcentyMixin,
    ModelZeSlowamiKluczowymi,
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
    ModelZPolamiEwaluacjiPBN,
    ModelZPrzeliczaniemDyscyplin,
    ModelZPubmedID,
    ModelZRokiem,
    ModelZWWW,
    Wydawnictwo_Baza,
)
from bpp.models.soft_delete import (
    BppAutorstwoSoftDeleteMixin,
    BppPublikacjaSoftDeleteMixin,
)
from bpp.models.system import Zewnetrzna_Baza_Danych
from bpp.models.util import ZapobiegajNiewlasciwymCharakterom


class Wydawnictwo_Ciagle_Autor(
    DirtyFieldsMixin,
    BppAutorstwoSoftDeleteMixin,
    BazaModeluOdpowiedzialnosciAutorow,
):
    """Powiązanie autora do wydawnictwa ciągłego."""

    rekord = models.ForeignKey(
        "Wydawnictwo_Ciagle",
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
        verbose_name = "powiązanie autora z wyd. ciągłym"
        verbose_name_plural = "powiązania autorów z wyd. ciągłymi"
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
                name="wc_autor_uniq_rekord_autor_typ",
            ),
            # NIE MA tu `UniqueConstraint(rekord, autor, kolejnosc)` — byłby
            # w 100% redundantny wobec `wc_autor_excl_rekord_kolejnosc`
            # niżej. Ten pilnuje pary (rekord, kolejnosc) NIE PATRZĄC na
            # autora, a więc jest ściśle silniejszy: skoro w obrębie rekordu
            # żadna pozycja nie może się powtórzyć, to tym bardziej nie może
            # się powtórzyć w obrębie (rekord, autor). Kosztowałby wyłącznie
            # trzeci indeks: build w oknie serwisowym + stały narzut na
            # każdym zapisie autorstwa (najgorętsza ścieżka zapisu w BPP).
            # Odpowiednik legacy `ALTER TABLE ... UNIQUE (rekord_id,
            # kolejnosc) DEFERRABLE INITIALLY DEFERRED` z migracji 0132 —
            # gwarantuje, że DWÓCH RÓŻNYCH autorów nie dzieli tej samej
            # pozycji w obrębie rekordu. `UniqueConstraint` nie umie
            # łączyć `condition` z `deferrable` (Django to blokuje —
            # `condition` i `deferrable` się wykluczają), a `deferrable`
            # jest tu wymagane przez drag&drop reorder w adminie
            # (adminsortable2, patrz `sortable_field_name = "kolejnosc"`)
            # — zamiana kolejności dwóch wierszy przejściowo dubluje
            # wartość `kolejnosc` w obrębie jednej transakcji, co bez
            # DEFERRED wywaliłoby się na pierwszym UPDATE. Stąd
            # `ExclusionConstraint` (GiST + btree_gist, rozszerzenie już
            # włączone w bazie) — jedyny typ ograniczenia w Postgresie,
            # który łączy `WHERE` (warunek) z `DEFERRABLE`.
            ExclusionConstraint(
                name="wc_autor_excl_rekord_kolejnosc",
                expressions=[
                    ("rekord", RangeOperators.EQUAL),
                    ("kolejnosc", RangeOperators.EQUAL),
                ],
                condition=Q(deleted_at__isnull=True),
                deferrable=Deferrable.DEFERRED,
            ),
        ]
        indexes = [
            # Indeks CZĘŚCIOWY (`WHERE deleted_at IS NOT NULL`), nie pełny.
            # Predykat `deleted_at IS NULL` pasuje do ~100% wierszy, więc
            # planner i tak nigdy nie wybrałby pod niego indeksu (seq scan
            # jest tańszy) — pełny btree byłby wyłącznie kosztem: rozmiar
            # rzędu tabeli + wpis przy każdym INSERT/UPDATE autorstwa.
            # Realnie selektywne jest zapytanie ODWROTNE — `deleted_objects`
            # (`deleted_at IS NOT NULL`), czyli kosz/audyt — i to ono
            # dostaje tu mikroskopijny indeks.
            models.Index(
                fields=["deleted_at"],
                name="wc_autor_deleted_at_idx",
                condition=Q(deleted_at__isnull=False),
            ),
        ]

    # django-denorm buduje bramkę WHEN triggera z listy `only=` w
    # @depend_on_related. Bez deleted_at soft-delete autorstwa nie
    # unieważniłby denorm-cache rodzica (opis bibliograficzny, slug,
    # cached_punkty_dyscyplin) — zostałby nieświeży na stałe.
    denorm_always_only = ("deleted_at",)


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


class Wydawnictwo_Ciagle_Manager(ManagerModeliZOplataZaPublikacjeMixin, models.Manager):
    pass


class Wydawnictwo_Ciagle(
    BppPublikacjaSoftDeleteMixin,
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
    ModelZeSlowamiKluczowymi,
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
    ModelZPolamiEwaluacjiPBN,
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
        indexes = [
            # Indeks CZĘŚCIOWY (`WHERE deleted_at IS NOT NULL`) — ten sam
            # wzorzec i to samo uzasadnienie, co `wc_autor_deleted_at_idx`
            # wyżej (faza 01): predykat `deleted_at IS NULL` pasuje do ~100%
            # wierszy, więc planner nigdy nie wybrałby pod niego indeksu, a
            # pełny btree byłby wyłącznie kosztem (rozmiar + wpis przy
            # każdym INSERT/UPDATE publikacji). Selektywne jest zapytanie
            # ODWROTNE — kosz/audyt (`deleted_objects`) — i to ono dostaje
            # tu mikroskopijny indeks. KANONICZNE UZASADNIENIE dla
            # wszystkich pięciu tabel publikacji.
            models.Index(
                fields=["deleted_at"],
                name="wc_deleted_at_idx",
                condition=Q(deleted_at__isnull=False),
            ),
        ]

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

    objects = Wydawnictwo_Ciagle_Manager()

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
    @depend_on_fields("tytul_oryginalny", "zrodlo_id")
    def slug(self):
        return self.get_slug()

    def to_bibtex(self):
        """Export this publication to BibTeX format."""
        from bpp.export.bibtex import wydawnictwo_ciagle_to_bibtex

        return wydawnictwo_ciagle_to_bibtex(self)

    def clean(self):
        DwaTytuly.clean(self)
        ModelZeSzczegolami.clean(self)
        ModelZOplataZaPublikacje.clean(self)


class Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych(models.Model):
    rekord = models.ForeignKey(
        Wydawnictwo_Ciagle, CASCADE, related_name="zewnetrzna_baza_danych"
    )
    baza = models.ForeignKey(Zewnetrzna_Baza_Danych, CASCADE)
    info = models.CharField(
        verbose_name="Informacje dodatkowe", max_length=512, blank=True, default=""
    )

    class Meta:
        verbose_name = "powiązanie wyd. ciągłego z zewn. bazą danych"
        verbose_name_plural = "powiązania wyd. ciągłych z zewn. bazami danych"

    def __str__(self):
        return f"{self.baza}"


class Wydawnictwo_Ciagle_Tytul(BazaModeluTytulow):
    rekord = models.ForeignKey(
        Wydawnictwo_Ciagle, CASCADE, related_name="dodatkowe_tytuly"
    )

    class Meta:
        verbose_name = "dodatkowy tytuł wydawnictwa ciągłego"
        verbose_name_plural = "dodatkowe tytuły wydawnictw ciągłych"
        unique_together = [("rekord", "kod_jezyka_pbn")]

    def __str__(self):
        return f"Tytuł rekordu {self.rekord_id} w języku {self.kod_jezyka_pbn}"


class Wydawnictwo_Ciagle_Streszczenie(BazaModeluStreszczen):
    rekord = models.ForeignKey(Wydawnictwo_Ciagle, CASCADE, related_name="streszczenia")

    class Meta:
        verbose_name = "streszczenie wydawnictwa ciągłego"
        verbose_name_plural = "streszczenia wydawnictw ciągłych"

    def __str__(self):
        try:
            str(self.rekord)
        except Wydawnictwo_Ciagle.DoesNotExist:
            # Może nie istnieć w sytuacji, gdy jesteśmy w trakcie kasowania rekordu, zaś easyaudit
            # chce zalogować takie wydarzenie.
            return f"Streszczenie usuniętego rekordu o ID: {self.rekord_id}"

        if self.jezyk_streszczenia_id is not None:
            return (
                f"Streszczenie rekordu {self.rekord} w języku {self.jezyk_streszczenia}"
            )
        return f"Streszczenie rekordu {self.rekord}"
