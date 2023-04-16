"""
Struktura uczelni.
"""
from datetime import date, timedelta

from autoslug import AutoSlugField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CASCADE
from django.db.models.functions import Coalesce
from django.db.models.query_utils import Q
from django.urls.base import reverse
from mptt.fields import TreeForeignKey
from mptt.managers import TreeManager
from mptt.models import MPTTModel
from tinymce.models import HTMLField

from .uczelnia import Uczelnia
from .wydzial import Wydzial

from django.contrib.postgres.search import SearchVectorField as VectorField

from django.utils import timezone

from bpp.models import ModelZAdnotacjami, ModelZPBN_UID
from bpp.models.abstract import ModelZPBN_ID
from bpp.models.autor import Autor, Autor_Jednostka
from bpp.util import FulltextSearchMixin

SORTUJ_RECZNIE = ("kolejnosc", "nazwa")
SORTUJ_ALFABETYCZNIE = ("nazwa",)


class JednostkaManager(FulltextSearchMixin, TreeManager):
    def create(self, *args, **kw):
        if "wydzial" in kw and not ("uczelnia" in kw or "uczelnia_id" in kw):
            # Kompatybilność wsteczna, z czasów, gdy nie było metryczki historycznej
            # dla obecności jednostki w wydziałach
            kw["uczelnia"] = kw["wydzial"].uczelnia
        return super().create(*args, **kw)

    def get_default_ordering(self):
        uczelnia = Uczelnia.objects.get_default()

        ordering = SORTUJ_RECZNIE
        if uczelnia is None:
            ordering = SORTUJ_ALFABETYCZNIE
        else:
            if uczelnia.sortuj_jednostki_alfabetycznie:
                ordering = SORTUJ_ALFABETYCZNIE

        return ordering

    def get_queryset(self, *args, **kwargs):
        return super().get_queryset(*args, **kwargs).select_related("wydzial")

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

    wydzial = models.ForeignKey(
        Wydzial, CASCADE, verbose_name="Wydział", blank=True, null=True
    )
    aktualna = models.BooleanField(
        default=False,
        help_text="""Jeżeli dana jednostka wchodzi w struktury wydziału
    (czyli jej obecność w strukturach wydziału nie została zakończona z określoną datą), to pole to będzie miało
    wartość 'PRAWDA'.""",
    )

    nazwa = models.CharField(max_length=512, unique=True)
    skrot = models.CharField("Skrót", max_length=128, unique=True)
    opis = HTMLField(blank=True, null=True)  # models.TextField(blank=True, null=True)
    pokazuj_opis = models.BooleanField(
        default=True,
        help_text="Gdy to pole jest zaznaczone, system wyświetli pole 'Opis' na podstronie jednostki.",
    )
    slug = AutoSlugField(populate_from="nazwa", unique=True)

    widoczna = models.BooleanField(default=True, db_index=True)
    wchodzi_do_raportow = models.BooleanField(
        "Wchodzi do raportów",
        default=True,
        db_index=True,
        help_text="Jeżeli odznaczone, prace z jednostki nie sumują się w rankingu autorów.",
    )
    email = models.EmailField("E-mail", max_length=128, blank=True, null=True)
    www = models.URLField("WWW", max_length=1024, blank=True, null=True)

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

    class RODZAJ_JEDNOSTKI(models.TextChoices):
        NORMALNA = "normalna", "zwyczajna jednostka (katedra, zakład, pracownia, itp.)"
        KOLO_NAUKOWE = "kolo_naukowe", "koło naukowe"

    rodzaj_jednostki = models.CharField(
        max_length=20,
        db_index=True,
        default=RODZAJ_JEDNOSTKI.NORMALNA,
        choices=RODZAJ_JEDNOSTKI.choices,
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

        try:
            wydzial = self.wydzial
        except (ValueError, TypeError, Wydzial.DoesNotExist):  # TODO catch-all
            wydzial = None

        if wydzial is not None:
            ret += " (%s)" % self.wydzial.skrot

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

    #
    # "Nowe (2022)" procedury wyświetlające aktualnych autorów (ta jednostka ma przypisanie
    # gdzie podstawowe_miejsce_pracy=True) oraz poprzednich współpracowników
    #

    def aktualni_autorzy(self):
        return (
            Autor_Jednostka.objects.filter(
                podstawowe_miejsce_pracy=True, jednostka=self
            )
            .values_list("autor")
            .distinct()
        )

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
            .values_list("autor")
        )

    def kierownik(self):
        try:
            return self.obecni_autorzy().get(
                autor_jednostka__funkcja__nazwa="kierownik"
            )
        except Autor.DoesNotExist:
            return None

    def prace_w_latach(self):
        from bpp.models.cache import Rekord

        return (
            Rekord.objects.prace_jednostki(self)
            .values_list("rok", flat=True)
            .distinct()
            .order_by("rok")
        )

    def przypisania(self):
        return Jednostka_Wydzial.objects.filter(jednostka_id=self.pk).order_by("od")

    def przypisania_dla_czasokresu(self, od, do):
        return Jednostka_Wydzial.objects.dla_czasokresu(od=od, do=do).filter(
            jednostka_id=self.pk
        )

    def przypisanie_dla_dnia(self, data):
        return self.przypisania_dla_czasokresu(data, data).first()

    def wydzial_dnia(self, data):
        try:
            return self.przypisanie_dla_dnia(data).wydzial
        except AttributeError:
            return


class Jednostka_Wydzial_Manager(models.Manager):
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
            assert (
                do >= parent_od
            ), "To nie powinno się zdarzyć. Funkcja przypisania_dla_czasokresu działa niepoprawnie"

            # Jeżeli zakres zaczyna się za parent.do, to nie ma prawa
            # być takiej sytuacji, bo funkcja przypisania_dla_czasokresu
            # ma nie zwracać takich zakresów. Ma prawo zaczynać się w dniu parent.od
            # ale nie ma prawa zaczynać się za:
            assert (
                od <= parent_do_not_null
            ), "To nie powinno się zdarzyć. Funkcja przypisania_dla_czasokresu działa niepoprawnie"

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

                Jednostka_Wydzial.objects.create(
                    jednostka=jw.jednostka, wydzial=jw.wydzial, od=new_od, do=old_do
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


class Jednostka_Wydzial(models.Model):
    jednostka = models.ForeignKey(Jednostka, CASCADE)
    wydzial = models.ForeignKey(Wydzial, CASCADE)
    od = models.DateField(null=True, blank=True)
    do = models.DateField(null=True, blank=True)

    objects = Jednostka_Wydzial_Manager()

    class Meta:
        verbose_name = "powiązanie jednostka-wydział"
        verbose_name_plural = "powiązania jednostka-wydział"
        ordering = ("-od",)

    def __str__(self):
        return f"{self.jednostka} - {self.wydzial} ({self.od}, {self.do})"

    def clean(self):
        try:
            self.wydzial
        except (ValueError, TypeError, Wydzial.DoesNotExist):
            raise ValidationError({"wydzial": "Określ wydział"})

        if self.wydzial.uczelnia_id != self.jednostka.uczelnia_id:
            raise ValidationError(
                {"wydzial": "Uczelnia dla wydziału i jednostki musi być identyczna."}
            )

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
                old = Jednostka_Wydzial.objects.get(pk=self.pk)
                if old.jednostka_id != self.jednostka_id:
                    raise ValidationError(
                        {
                            "jednostka": "Zmiana ID jednostki dla tych obiektów nie jest obsługiwana."
                        }
                    )
            except Jednostka_Wydzial.DoesNotExist:
                pass

        # Sprawdz zakres dat
        cnt = (
            Jednostka_Wydzial.objects.dla_czasokresu(self.od, self.do)
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
