"""
Struktura uczelni.
"""

from collections import defaultdict
from datetime import date, timedelta

from autoslug import AutoSlugField
from denorm import denormalized, depend_on_fields, depend_on_related
from django.conf import settings
from django.contrib.postgres.search import SearchVectorField as VectorField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CASCADE
from django.db.models.functions import Coalesce
from django.db.models.query_utils import Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls.base import reverse
from django.utils import timezone
from mptt.fields import TreeForeignKey
from mptt.managers import TreeManager
from mptt.models import MPTTModel
from tinymce.models import HTMLField

from bpp.models import ModelZAdnotacjami, ModelZPBN_UID
from bpp.models.abstract import ModelZPBN_ID
from bpp.models.autor import Autor, Autor_Jednostka
from bpp.util import FulltextSearchMixin

from .uczelnia import Uczelnia
from .wydzial import Wydzial

SORTUJ_RECZNIE = ("kolejnosc", "nazwa")
SORTUJ_ALFABETYCZNIE = ("nazwa",)


class JednostkaManager(FulltextSearchMixin, TreeManager):
    # Faza B (#438): usunięto kompat-kwarg ``wydzial=`` z ``create()`` —
    # ``wydzial`` jest teraz zdenormalizowanym self-FK (denorm nadpisuje przy
    # zapisie), więc nie da się (i nie należy) go podać ręcznie. Wołający
    # ustawiają ``parent`` (drzewo) i ``uczelnia`` wprost.

    def get_default_ordering(self, uczelnia=None):
        # Multi-hosted: odczyt PREFERENCJI sortowania. Bez przekazanej uczelni
        # próbujemy JEDYNEJ w systemie (get_single_uczelnia_or_none: single →
        # jej preferencja; 0 lub >1 → None → alfabetycznie). NIE ma „uczelni
        # domyślnej" (zgadywania pierwszej-z-brzegu). Wołający z requestem
        # może podać uczelnię jawnie.
        if uczelnia is None:
            uczelnia = Uczelnia.objects.get_single_uczelnia_or_none()

        ordering = SORTUJ_RECZNIE
        if uczelnia is None or uczelnia.sortuj_jednostki_alfabetycznie:
            ordering = SORTUJ_ALFABETYCZNIE

        return ordering

    def get_queryset(self, *args, **kwargs):
        return super().get_queryset(*args, **kwargs).select_related("wydzial")

    def rebuild(self, *args, **kwargs):
        # TreeManager.rebuild() internally runs `.only("pk")` on the queryset
        # this manager returns, which under Django 5+ errors out because our
        # default `select_related("wydzial")` can't coexist with a deferred
        # field of the same FK. Bypass the override for this one path.
        original = type(self).get_queryset
        try:
            type(self).get_queryset = TreeManager.get_queryset
            return super().rebuild(*args, **kwargs)
        finally:
            type(self).get_queryset = original

    def widoczne(self):
        "Jednostki widoczne (nie-ukryte)"
        return self.filter(widoczna=True)

    def publiczne(self):
        """Jednostki widoczne publicznie"""
        return self.widoczne().filter(aktualna=True)


class Jednostka(ModelZAdnotacjami, ModelZPBN_ID, ModelZPBN_UID, MPTTModel):
    parent = TreeForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Jednostka nadrzędna",
    )

    uczelnia = models.ForeignKey(
        Uczelnia,
        CASCADE,
        # Jeżeli dam tu rozsądny default, żeby w adminie się wyświetlało prawidłowo,
        # to z kolei wysiądzie mi cała masa testów, korzystająca z model_bakery
        # i tworząca obiekt 'Uczelnia' na poczekaniu (pole nie może być NULL).
        # Zatem, zostawiamy to wyłączone i w adminie ustawimy wartośći inicjalne.
        # default=lambda: Uczelnia.objects.first()
    )

    @denormalized(
        models.ForeignKey,
        "self",
        verbose_name="Wydział",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    @depend_on_fields("parent")
    @depend_on_related("self", "parent", only=("wydzial_id",))
    def wydzial(self):
        # Faza B (#438): zdenormalizowany wskaźnik KORZENIA drzewa MPTT.
        # Root (parent IS NULL) → NULL; potomek → korzeń swojego poddrzewa.
        # Kaskada tranzytywna (denorm) przelicza poddrzewo przy re-parencie.
        if self.parent_id is None:
            return None
        return self.parent.wydzial or self.parent

    aktualna = models.BooleanField(
        default=True,
        help_text="""Jeżeli dana jednostka wchodzi w struktury wydziału
    (czyli jej obecność w strukturach wydziału nie została zakończona z określoną datą), to pole to będzie miało
    wartość 'PRAWDA'.""",
    )
    aktualna_override = models.BooleanField(
        "Ręczne nadpisanie «aktualna»",
        null=True,
        blank=True,
        help_text="Puste = licz z historii; ustawione = trzymaj tę wartość",
    )

    nazwa = models.CharField(max_length=512, unique=True)
    skrot = models.CharField("Skrót", max_length=128, unique=True)
    opis = HTMLField(blank=True, null=True)  # models.TextField(blank=True, null=True)
    pokazuj_opis = models.BooleanField(
        default=True,
        help_text="Gdy to pole jest zaznaczone, system wyświetli pole 'Opis' na podstronie jednostki.",
    )
    slug = AutoSlugField(populate_from="nazwa", max_length=512, unique=True)

    widoczna = models.BooleanField(default=True, db_index=True)
    wchodzi_do_rankingu_autorow = models.BooleanField(
        "Wlicza prace jednostki do rankingu autorów",
        default=True,
        db_index=True,
        help_text="Jeżeli odznaczone, prace z tej jednostki NIE sumują się w rankingu "
        "autorów.",
    )
    email = models.EmailField("E-mail", max_length=128, blank=True, default="")
    www = models.URLField("WWW", max_length=1024, blank=True, default="")

    pbn_uid = models.ForeignKey(
        "pbn_api.Institution",
        verbose_name="Odpowiednik w PBN",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    skupia_pracownikow = models.BooleanField(
        "Skupia pracowników",
        default=True,
        help_text="""Ta jednostka skupia osoby będące faktycznymi pracownikami uczelni. Odznacz dla jednostek
         typu 'Studenci', 'Doktoranci', 'Pracownicy emerytowani' itp. Odznacz dla 'obcych' jednostek. """,
        db_index=True,
    )

    zarzadzaj_automatycznie = models.BooleanField(
        "Zarządzaj automatycznie",
        default=True,
        help_text="""Jednostka ta będzie dowolnie modyfikowana przez procedury importujace dane z zewnętrznych
        systemów informatycznych""",
    )

    # Faza B (#438), III-1: stary CharField ``rodzaj_jednostki`` +
    # ``RODZAJ_JEDNOSTKI`` (TextChoices) usunięte — jedyne źródło prawdy to
    # FK ``rodzaj`` (→ ``RodzajJednostki``, słownik per-tenant edytowalny w
    # adminie). Migracja 0461 usuwa kolumnę po ostatnim re-backfillu.
    rodzaj = models.ForeignKey(
        "bpp.RodzajJednostki",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="jednostki",
    )

    zezwalaj_na_ranking_autorow = models.BooleanField(
        "Zezwalaj na generowanie rankingu autorów dla tej jednostki",
        default=True,
    )
    poprzednie_nazwy = models.CharField(max_length=4096, blank=True, default="")
    skrot_nazwy = models.CharField(  # noqa: DJ001
        max_length=250, blank=True, null=True
    )
    legacy_wydzial_id = models.IntegerField(null=True, blank=True, db_index=True)
    # Faza B (#438): stabilny marker TOŻSAMOŚCI KONWERSJI. Rozdziela trzy
    # niezależne pojęcia, dotąd sklejone w nazwie rodzaju "Wydział":
    #  - ``legacy_wydzial_id`` — KTÓRY stary Wydzial reprezentuje ten węzeł
    #    (mają OBA: syntetyczne lustro I promowana 1-jednostkowa) → mapowanie FK,
    #  - ``jest_lustrem`` — czy to SYNTETYCZNY węzeł-lustro (True), czy REALNA
    #    jednostka promowana do roota (False) → logika kasowania/widoczności/
    #    historii lustra filtruje PO TYM (nie po edytowalnej nazwie rodzaju),
    #  - ``rodzaj.pokazuj_strukture_podjednostek`` — czy wyświetlać stronę w
    #    stylu wydziału (edytowalna preferencja UI, osobna sprawa).
    jest_lustrem = models.BooleanField(
        "Syntetyczny węzeł-lustro wydziału", default=False
    )

    search = VectorField(blank=True, null=True)

    kolejnosc = models.PositiveIntegerField(default=0, blank=False, null=False)

    objects = JednostkaManager()

    class Meta:
        verbose_name = "jednostka"
        verbose_name_plural = "jednostki"
        ordering = ["kolejnosc", "nazwa"]
        app_label = "bpp"

    class MPTTMeta:
        order_insertion_by = ["kolejnosc", "nazwa"]

    def get_absolute_url(self):
        return reverse("bpp:browse_jednostka", args=(self.slug,))

    def __str__(self):
        ret = self.nazwa

        if settings.DJANGO_BPP_SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI is False:
            return ret

        # Faza B (#438): flaga „używaj wydziałów" żyje teraz WYŁĄCZNIE na
        # modelu Uczelnia (bez globalnego env). ``self.uczelnia`` to FK do
        # obiektu, który każda Jednostka MUSI mieć (pole wymagane) — w
        # praktyce to .get() Django (cache'owany przez cacheops dla
        # ``bpp.uczelnia`` na produkcji; ten sam koszt ponosi już
        # ``self.wydzial`` niżej). Odczyt jest DEFENSYWNY: ``__str__`` bywa
        # wołany z audytu ``post_delete`` (easyaudit ``object_repr``), gdy
        # Uczelnia jest już skasowana w kaskadzie — wtedy FK rzuca
        # ``DoesNotExist`` i repr NIE może wybuchać (traktujemy brak uczelni
        # jak „pokaż wydział"). Bez ``uczelnia_id`` (niezapisany obiekt w
        # pamięci) też pomijamy sprawdzenie.
        if self.uczelnia_id is not None:
            try:
                if self.uczelnia.uzywaj_wydzialow is False:
                    return ret
            except Uczelnia.DoesNotExist:
                pass

        try:
            wydzial = self.wydzial
        except (ValueError, TypeError, Jednostka.DoesNotExist):
            # Faza B (#438): ``wydzial`` to teraz self-FK -> Jednostka, więc
            # dangling/deferred dostęp rzuca Jednostka.DoesNotExist (dawny
            # guard na Wydzial.DoesNotExist był martwy po retargecie).
            wydzial = None

        if wydzial is not None:
            ret += f" ({self.wydzial.skrot})"

        return ret

    def dodaj_autora(
        self, autor, funkcja=None, rozpoczal_prace=None, zakonczyl_prace=None
    ):
        ret = Autor_Jednostka.objects.create(
            autor=autor,
            jednostka=self,
            funkcja=funkcja,
            rozpoczal_prace=rozpoczal_prace,
            zakonczyl_prace=zakonczyl_prace,
        )
        # Odśwież obiekt - pobierz ewentualną zmiane pola 'aktualna_jednostka', obsługiwaną
        # przez trigger bazodanowy (migracja 0046)
        autor.refresh_from_db()
        return ret

    zatrudnij = dodaj_autora

    #
    # "Stare (przed-2022)" procedury wyświetlające autorów obecnie przypisanych do tej jednostki
    #

    def obecni_autorzy(self):
        dzis = timezone.now().date()

        return Autor.objects.filter(
            Q(autor_jednostka__zakonczyl_prace__gte=dzis)
            | Q(autor_jednostka__zakonczyl_prace=None),
            Q(autor_jednostka__rozpoczal_prace__lte=dzis)
            | Q(autor_jednostka__rozpoczal_prace=None),
            autor_jednostka__jednostka=self,
        ).distinct()

    def autorzy_na_strone_jednostki(self):
        """ "Stara" funkcja, wyswietlajaca autorow przypisanych do tej jednostki,
        w przypadku, gdy nikt nie ma 'Podstawowe miejsce pracy' ustawione na TRUE"""
        return self.obecni_autorzy().filter(pokazuj=True)

    def aktualni_autorzy(self):
        """
        "Nowe (2022)" procedury do generowania aktualnych autorów (współpracowników)
        na stronę jednostki.

        Zasady:
        * autor jest aktualnym współpracownikiem, jezeli ma przypisanie do danej jednostki
         i określony atrybut podstawowe_miejsce_pracy = True _ORAZ_ data zakonczenia pracy
          jest pusta lub w przyszłośc,
        * autor jest aktualnym współpracownikiem, jeżeli w polu aktualna_jednostka
          (pole obliczane na podstawie triggera bazodanowego) znajduje się ta sama
          jednostka co {self}
        """
        podstawowe_miejsce_pracy = set(
            Autor_Jednostka.objects.filter(
                Q(
                    Q(zakonczyl_prace=None)
                    | Q(zakonczyl_prace__gt=timezone.now().date()),
                    podstawowe_miejsce_pracy=True,
                    jednostka=self,
                )
            )
            .values_list("autor", flat=True)
            .distinct()
        )
        aktualni_autorzy = set(
            Autor.objects.filter(aktualna_jednostka=self).values_list("pk", flat=True)
        )

        return podstawowe_miejsce_pracy.union(aktualni_autorzy)

    def pracownicy(self):
        """Autorzy, którzy tą jednostkę mają wpisani jako AKTUALNA -- czyli
        aktualni pracownicy, obecni pracownicy"""
        return Autor.objects.filter(pk__in=self.aktualni_autorzy(), pokazuj=True)

    def wspolpracowali(self):
        """Autorzy, którzy popełnili jakiekolwiek prace z afiliacją na tę jednostkę,
        nie będący autorami z  funkcji 'pracownicy'"""
        from bpp.models.cache import Autorzy

        return Autor.objects.filter(
            pk__in=Autorzy.objects.filter(jednostka=self)
            .exclude(autor_id__in=self.aktualni_autorzy())
            .values_list("autor", flat=True),
            pokazuj=True,
        )

    def kierownik(self):
        return (
            self.obecni_autorzy()
            .filter(autor_jednostka__funkcja__nazwa="kierownik")
            .first()
        )

    def prace_w_latach(self):
        from bpp.models.cache import Rekord

        return (
            Rekord.objects.prace_jednostki(self)
            .values_list("rok", flat=True)
            .distinct()
            .order_by("rok")
        )

    def przypisania(self):
        return Jednostka_Rodzic.objects.filter(jednostka_id=self.pk).order_by("od")

    def przypisania_dla_czasokresu(self, od, do):
        return Jednostka_Rodzic.objects.dla_czasokresu(od=od, do=do).filter(
            jednostka_id=self.pk
        )

    def przypisanie_dla_dnia(self, data):
        return self.przypisania_dla_czasokresu(data, data).first()

    def wydzial_dnia(self, data):
        # Faza B (#438): metryczka historyczna trzyma teraz węzeł-rodzic
        # (Jednostka), a nie Wydzial. Stary Wydzial odzyskujemy przez
        # legacy_wydzial_id węzła — utrzymuje kontrakt (zwraca Wydzial lub None)
        # do czasu usunięcia strony wydziału (B-III).
        przypisanie = self.przypisanie_dla_dnia(data)
        if przypisanie is None or przypisanie.parent_id is None:
            return None
        return Wydzial.objects.filter(id=przypisanie.parent.legacy_wydzial_id).first()

    #
    # Metody węzła dla strukturalnego stylu browse (Faza B, III-2, #438).
    #
    # Zastępują dawne ``Wydzial.jednostki/aktualne_jednostki/kola_naukowe/
    # historyczne_jednostki`` (models/wydzial.py). Używane przez
    # ``JednostkaView`` w stylu strukturalnym
    # (``self.rodzaj.pokazuj_strukture_podjednostek``), czyli dawnej stronie
    # wydziału.
    #
    # SEMANTYKA PODDRZEWA (regresja III-2 naprawiona): dawne metody ``Wydzial``
    # pokazywały CAŁE poddrzewo wydziału przez denorm FK
    # (``wydzial__legacy_wydzial_id=<wydzial.pk>``). III-2 zwęził to omyłkowo do
    # ``self.get_children()`` (TYLKO bezpośrednie dzieci MPTT) -> strona
    # wydziału stawała się pusta, gdy jednostki wisiały głębiej (wydział ->
    # instytut -> katedra). Przywracamy poddrzewo przez MPTT
    # ``self.get_descendants()`` (lft/rght range), które działa dla KAŻDEGO
    # węzła — także nie-korzenia. WAŻNE: nie używamy ``wydzial=self``, bo
    # zdenorm. ``wydzial`` wskazuje KORZEŃ drzewa (a nie ``self``), więc
    # ``wydzial=self`` dawałoby PUSTKĘ dla węzła w środku drzewa (np. rodzaj z
    # flagą ``pokazuj_strukture_podjednostek`` przypisany do „Instytutu")
    # -> pusta strona mimo dzieci. Poddrzewo liczymy helperami
    # ``_poddrzewo_jednostki`` / ``_poddrzewo_jednostki_z_soba``: dla KORZENIA
    # zdenorm. ``wydzial`` (pk-owe, odporne na nieaktualne lft/rght instancji --
    # jak w dawnych metodach), dla węzła nie-korzenia MPTT ``get_descendants``
    # (w widoku ``self`` jest świeżo wczytany, więc lft/rght aktualne).
    # Odwzorowanie: ``wydzial__legacy_wydzial_id=self.pk`` -> poddrzewo jednostek;
    # ``parent__legacy_wydzial_id=self.pk`` -> rodzic metryczki w poddrzewie.
    #

    def _poddrzewo_jednostki(self):
        """Queryset jednostek z PODDRZEWA tego węzła (bez samego węzła).

        Korzeń: zdenorm. ``wydzial=self`` (pk-owe, odporne na nieaktualne
        lft/rght). Nie-korzeń: MPTT ``get_descendants`` (``wydzial`` potomka
        wskazuje KORZEŃ, nie ``self``, więc ``wydzial=self`` dałoby pustkę)."""
        if self.parent_id is None:
            return Jednostka.objects.filter(wydzial=self)
        return self.get_descendants()

    def _poddrzewo_jednostki_z_soba(self):
        """Jak ``_poddrzewo_jednostki``, ale WŁĄCZNIE z samym węzłem -- dla
        metryczek ``Jednostka_Rodzic`` z rodzicem w poddrzewie."""
        if self.parent_id is None:
            return Jednostka.objects.filter(Q(pk=self.pk) | Q(wydzial=self))
        return self.get_descendants(include_self=True)

    def aktualne_podjednostki(self):
        """Aktualne, widoczne jednostki z PODDRZEWA tego węzła -- bez jednostek
        oznaczonych jako odrębna sekcja (np. koła naukowe).

        Wierny port dawnej ``Wydzial.aktualne_jednostki`` (poddrzewo -- patrz
        komentarz wyżej): obejmuje wnuki, prawnuki, ..., i działa też dla węzła
        nie-korzenia; ``rodzaj__nazwa="Koło naukowe"`` -> flaga
        ``rodzaj__pokazuj_jako_odrebna_sekcje`` (spójność Fazy B)."""
        return (
            self._poddrzewo_jednostki()
            .filter(widoczna=True)
            .exclude(rodzaj__pokazuj_jako_odrebna_sekcje=True)
            .exclude(aktualna=False)
            .order_by(*Jednostka.objects.get_default_ordering())
        )

    def kola_naukowe(self):
        """Koła naukowe (rodzaj z flagą ``pokazuj_jako_odrebna_sekcje``) z
        PODDRZEWA węzła -- pokazywane osobno od zwykłych podjednostek.

        Wierny port dawnej ``Wydzial.kola_naukowe``: aktualne przez poddrzewo
        (helper ``_poddrzewo_jednostki``), historyczne (odłączone od drzewa,
        ``wydzial=None``) przez wciąż-ważną metryczkę ``Jednostka_Rodzic`` z
        rodzicem w poddrzewie. ``rodzaj__nazwa="Koło naukowe"`` -> flaga
        ``pokazuj_jako_odrebna_sekcje``; ``parent__legacy_wydzial_id`` ->
        rodzic w poddrzewie (helper ``_poddrzewo_jednostki_z_soba``)."""
        today = timezone.now().date()

        return (
            Jednostka.objects.filter(rodzaj__pokazuj_jako_odrebna_sekcje=True)
            .filter(
                Q(pk__in=self._poddrzewo_jednostki(), aktualna=True, widoczna=True)
                | Q(
                    wydzial=None,
                    pk__in=Jednostka_Rodzic.objects.filter(
                        parent__in=self._poddrzewo_jednostki_z_soba()
                    )
                    .exclude(do=None)
                    .exclude(do__lt=today)
                    .values_list("jednostka_id", flat=True),
                )
            )
            .order_by(*Jednostka.objects.get_default_ordering())
        )

    def historyczne_podjednostki(self):
        """Jednostki, które historycznie należały do PODDRZEWA tego węzła
        (metryczka ``Jednostka_Rodzic`` z rodzicem w poddrzewie i ``do`` w
        przeszłości), a obecnie już nie (``aktualna`` != True).

        Wierny port dawnej ``Wydzial.historyczne_jednostki``:
        ``parent__legacy_wydzial_id=self.pk`` -> rodzic w poddrzewie (helper
        ``_poddrzewo_jednostki_z_soba``) -- obejmuje historię z całego
        poddrzewa, nie tylko bezpośrednich dzieci, i działa też dla węzła
        nie-korzenia."""
        today = timezone.now().date()

        return (
            Jednostka.objects.exclude(aktualna=True)
            .filter(
                pk__in=Jednostka_Rodzic.objects.filter(
                    parent__in=self._poddrzewo_jednostki_z_soba()
                )
                .exclude(do=None)
                .exclude(do__gte=today)
                .values_list("jednostka_id", flat=True)
            )
            .order_by(*Jednostka.objects.get_default_ordering())
        )

    def wymaga_nawigacji(self):
        """Jeżeli węzeł ma co najmniej dwie z trzech kategorii podjednostek
        (aktualne, koła naukowe, historyczne), to wymaga wyświetlenia
        nawigacji na podstronie strukturalnej -- zwraca wówczas True."""
        res = defaultdict(int)

        res[self.aktualne_podjednostki().exists()] += 1
        res[self.historyczne_podjednostki().exists()] += 1
        res[self.kola_naukowe().exists()] += 1

        return res[True] >= 2


class Jednostka_Rodzic_Manager(models.Manager):
    def od_do_not_null(self):
        return self.get_queryset().annotate(
            od_not_null=Coalesce("od", date(1, 1, 1)),
            do_not_null=Coalesce("do", date(9999, 12, 31)),
        )

    def dla_czasokresu(self, od, do):
        return self.od_do_not_null().filter(
            od_not_null__lte=do or date(9999, 12, 31),
            do_not_null__gte=od or date(1, 1, 1),
        )

    def wyczysc_przypisania(self, jednostka, parent_od=None, parent_do=None):
        parent_do_not_null = parent_do or date(9999, 12, 31)

        for jw in (
            self.dla_czasokresu(parent_od, parent_do)
            .filter(jednostka_id=jednostka.pk)
            .order_by("od_not_null")
        ):
            od = jw.od or date(1, 1, 1)
            do = jw.do or date(9999, 12, 31)

            # Jeżeli zakres kończy przed parent.do, to nie ma prawa
            # być takiej sytuacji, bo funkcja przypisania_dla_czasokresu
            # ma nie zwracać takich zakresów. Ma prawo kończyć się w dniu parent.do
            # ale nie ma się kończyć przed
            assert do >= parent_od, (
                "To nie powinno się zdarzyć. Funkcja przypisania_dla_czasokresu działa niepoprawnie"
            )

            # Jeżeli zakres zaczyna się za parent.do, to nie ma prawa
            # być takiej sytuacji, bo funkcja przypisania_dla_czasokresu
            # ma nie zwracać takich zakresów. Ma prawo zaczynać się w dniu parent.od
            # ale nie ma prawa zaczynać się za:
            assert od <= parent_do_not_null, (
                "To nie powinno się zdarzyć. Funkcja przypisania_dla_czasokresu działa niepoprawnie"
            )

            # Jeżeli zakres zaczyna się przed parent.od i kończy wewnątrz parent
            #
            #      +---+
            #          |........|
            #
            #      +-------+
            #          |........|
            #
            #      +------------+
            #          |........|

            if od < parent_od and do <= parent_do_not_null:
                jw.do = parent_od - timedelta(days=1)
                jw.save()
                continue

            # Jeżeli zakres zaczyna się przed parent.od i kończy za parent
            #
            #      +---------------+
            #          |........|
            if od < parent_od and do > parent_do:
                old_do = jw.do
                new_do = parent_od - timedelta(days=1)
                new_od = parent_do + timedelta(days=1)

                jw.do = new_do
                jw.save()

                Jednostka_Rodzic.objects.create(
                    jednostka=jw.jednostka, parent=jw.parent, od=new_od, do=old_do
                )
                continue

            # Jeżeli zakres zaczyna się na lub po parent.od i kończy wewnątrz
            #
            #          +----+
            #          |........|
            #
            #          +--------+
            #          |........|
            #
            #             +-----+
            #          |........|
            if od >= parent_od and do <= parent_do:
                jw.delete()
                continue

            # Jeżeli zakres zaczyna się na lub po parent.od i kończy po parent.do
            #
            #
            #               +-----------+
            #          |........|
            #
            #          +--------------+
            #          |........|
            if od >= parent_od and do > parent_do:
                jw.od = parent_do + timedelta(days=1)
                jw.save()
                continue


class Jednostka_Rodzic(models.Model):
    jednostka = models.ForeignKey(Jednostka, CASCADE)
    parent = models.ForeignKey(
        Jednostka,
        CASCADE,
        null=True,
        blank=True,
        related_name="jednostka_rodzic_parent_set",
    )
    od = models.DateField(null=True, blank=True)
    do = models.DateField(null=True, blank=True)

    objects = Jednostka_Rodzic_Manager()

    class Meta:
        verbose_name = "powiązanie jednostka-rodzic"
        verbose_name_plural = "powiązania jednostka-rodzic"
        ordering = ("-od",)

    def __str__(self):
        return f"{self.jednostka} - {self.parent} ({self.od}, {self.do})"

    def clean(self):
        # Faza B (#438): walidacja równości uczelni (wydzial.uczelnia ==
        # jednostka.uczelnia) USUNIĘTA — federacja (Zasada #4) dopuszcza
        # krawędzie między-uczelniane. Check obecności starego pola „wydzial"
        # też znika (pole zastąpione nullowalnym „parent"). Zostają checki
        # niezależne od uczelni: zakres dat, tożsamość jednostki, nakładanie
        # zakresów, data „do" w przyszłości.
        if self.od is not None and self.do is not None:
            if self.od >= self.do:
                raise ValidationError(
                    {
                        "od": "Wartość w polu 'Od' musi byc mniejsza, niż wartość w polu 'Do'.",
                        "do": "Wartosć w polu 'Do' musi być większa, niż wartość w polu 'Od'.",
                    }
                )

        if self.pk:
            try:
                old = Jednostka_Rodzic.objects.get(pk=self.pk)
                if old.jednostka_id != self.jednostka_id:
                    raise ValidationError(
                        {
                            "jednostka": "Zmiana ID jednostki dla tych obiektów nie jest obsługiwana."
                        }
                    )
            except Jednostka_Rodzic.DoesNotExist:
                pass

        # Sprawdz zakres dat
        cnt = (
            Jednostka_Rodzic.objects.dla_czasokresu(self.od, self.do)
            .filter(jednostka_id=self.jednostka_id)
            .exclude(id=self.id)
            .count()
        )

        if cnt:
            msg = """rekord z podobnym lub nakładającym się zakresem dat już istnieje w bazie danych.
            Nie możesz dodać nakładających się zakresów dat. Jeżeli próbujesz dokonać kilku zmian jednocześnie, ten
            komunikat może pojawić się również, gdy taka sytuacja nie zachodzi. Wówczas zmień tylko jeden
            rekord jednoczasowo - rozbij zmianę na kilka pojedynczych działań."""
            raise ValidationError({"od": msg})

        # Sprawdź, czy pole "do" nie zawiera daty w przyszłości
        d = self.do or date(1, 1, 1)
        if d >= date.today():
            raise ValidationError(
                {
                    "do": 'Data w polu "Do" nie może być większa lub równa, niż data aktualna (dzisiejsza).'
                }
            )


def wylicz_aktualna(najswiezszy_do, ma_wpis, override, dzis=None):
    """FINALNA logika pola ``Jednostka.aktualna`` (issue #438, Faza B, IV-1).

    Jedno źródło prawdy dla sygnału ``ustaw_aktualna_jednostki``, komendy
    ``przelicz_aktualna`` i (zduplikowanej inline) migracji ``0462``.

    * ``override`` (``aktualna_override``) nie-NULL → użyj override, POMIŃ
      derywację.
    * ``ma_wpis`` False (brak wpisów ``Jednostka_Rodzic``) → ``True``.
    * najświeższy wpis ``do IS NULL`` → ``True`` (``coalesce(do, 9999) > dziś``).
    * najświeższy wpis ``do`` w przeszłości → ``False``.

    ``najswiezszy_do`` to pole ``do`` NAJŚWIEŻSZEGO wpisu (max
    ``coalesce(od, 0001-01-01)``); ``ma_wpis`` mówi, czy jakikolwiek wpis
    istnieje (odróżnia „brak wpisów → True" od „wpis z ``do``").
    """
    if override is not None:
        return override
    if not ma_wpis:
        return True
    if dzis is None:
        dzis = date.today()
    do = najswiezszy_do if najswiezszy_do is not None else date(9999, 12, 31)
    return do > dzis


def _najswiezsze_do_per_jednostka():
    """Mapa ``jednostka_id -> do`` NAJŚWIEŻSZEGO wpisu ``Jednostka_Rodzic``
    (max ``coalesce(od, 0001-01-01)``), jednym zapytaniem (``DISTINCT ON``).

    Brak jednostki w mapie ⇒ nie ma żadnego wpisu (``ma_wpis`` = False).
    """
    return dict(
        Jednostka_Rodzic.objects.annotate(_od=Coalesce("od", date(1, 1, 1)))
        .order_by("jednostka_id", "-_od")
        .distinct("jednostka_id")
        .values_list("jednostka_id", "do")
    )


def przelicz_aktualna_wszystkich():
    """Przelicz ``aktualna`` dla WSZYSTKICH jednostek wg finalnej logiki
    (``wylicz_aktualna``). Idempotentne, bez N+1 (najświeższy wpis per
    jednostka jednym ``DISTINCT ON``, zapis dwoma ``.update()``). Zwraca
    liczbę zmienionych wierszy. Używane przez komendę ``przelicz_aktualna``;
    migracja ``0462`` duplikuje tę logikę inline na modelach historycznych.
    """
    najswiezsze = _najswiezsze_do_per_jednostka()
    dzis = date.today()

    aktualne, nieaktualne = [], []
    for pk, override in Jednostka.objects.values_list("pk", "aktualna_override"):
        ma_wpis = pk in najswiezsze
        val = wylicz_aktualna(najswiezsze.get(pk), ma_wpis, override, dzis)
        (aktualne if val else nieaktualne).append(pk)

    zmienione = (
        Jednostka.objects.filter(pk__in=aktualne)
        .exclude(aktualna=True)
        .update(aktualna=True)
    )
    zmienione += (
        Jednostka.objects.filter(pk__in=nieaktualne)
        .exclude(aktualna=False)
        .update(aktualna=False)
    )
    return zmienione


@receiver(post_save, sender=Jednostka_Rodzic)
@receiver(post_delete, sender=Jednostka_Rodzic)
def ustaw_aktualna_jednostki(sender, instance, **kwargs):
    """Zastępuje część triggera ``bpp_jednostka_ustaw_wydzial_aktualna``
    dotyczącą pola ``aktualna`` (zdjęty w migracji 0455, Faza B / issue #438).

    **Zmiana w II-1 (0459):** sygnał NIE utrzymuje już interim ``wydzial_id``
    — po retargecie ``Jednostka.wydzial`` jest zdenormalizowanym self-FK do
    korzenia drzewa MPTT, utrzymywanym przez ``django-denorm-iplweb`` na
    podstawie ``parent`` (a NIE historii ``Jednostka_Rodzic``). Sygnał liczy
    wyłącznie ``aktualna``.

    Po każdej zmianie wpisów ``Jednostka_Rodzic`` danej jednostki bierze
    NAJŚWIEŻSZY wpis (max ``coalesce(od, 0001-01-01)``) i deleguje do
    ``wylicz_aktualna`` (FINALNA logika, ujednolicona w IV-1 z jednorazowym
    przeliczeniem): brak wpisów → True, ``do IS NULL`` → True, ``do`` w
    przeszłości → False; ``aktualna_override`` nie-NULL nadpisuje wszystko.

    Zapis przez ``.update()`` (bypass ``save()`` na Jednostce → brak
    rekurencji sygnałów).
    """
    jednostka_id = instance.jednostka_id

    najswiezszy = (
        Jednostka_Rodzic.objects.filter(jednostka_id=jednostka_id)
        .annotate(_od_not_null=Coalesce("od", date(1, 1, 1)))
        .order_by("-_od_not_null")
        .first()
    )

    override = (
        Jednostka.objects.filter(pk=jednostka_id)
        .values_list("aktualna_override", flat=True)
        .first()
    )

    aktualna = wylicz_aktualna(
        najswiezszy.do if najswiezszy is not None else None,
        najswiezszy is not None,
        override,
    )

    Jednostka.objects.filter(pk=jednostka_id).update(aktualna=aktualna)


@receiver(post_save, sender=Jednostka)
def invalidate_uczelnia_cache_on_jednostka_change(sender, instance, **kwargs):
    """
    Invalidate main page cache when jednostka is saved.
    This ensures the homepage is updated immediately.
    """
    from bpp.views.browse import get_uczelnia_context_data

    get_uczelnia_context_data.invalidate()
