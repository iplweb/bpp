# -*- encoding: utf-8 -*-

"""
Struktura uczelni.
"""
from datetime import date, timedelta

from autoslug import AutoSlugField
from django.contrib.postgres.search import SearchVectorField as VectorField
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db import models
from django.db.models.functions import Coalesce
from django.db.models.query_utils import Q
from django.urls.base import reverse
from django.utils import six
from django.utils import timezone

from bpp.models import ModelZAdnotacjami, NazwaISkrot
from bpp.models.abstract import NazwaWDopelniaczu, ModelZPBN_ID
from bpp.models.autor import Autor, Autor_Jednostka
from bpp.util import FulltextSearchMixin
from .fields import OpcjaWyswietlaniaField


class Uczelnia(ModelZAdnotacjami, ModelZPBN_ID, NazwaISkrot, NazwaWDopelniaczu):
    slug = AutoSlugField(populate_from='skrot',
                         unique=True)
    logo_www = models.ImageField(
        "Logo na stronę WWW", upload_to="logo",
        help_text="""Plik w formacie bitmapowym, np. JPEG lub PNG,
        w rozdzielczości maks. 100x100""", blank=True, null=True)
    logo_svg = models.FileField(
        "Logo wektorowe (SVG)", upload_to="logo_svg",
        blank=True, null=True)
    favicon_ico = models.FileField(
        "Ikona ulubionych (favicon)", upload_to="favicon", blank=True, null=True)

    obca_jednostka = models.ForeignKey('bpp.Jednostka', null=True, blank=True, help_text="""
    Jednostka skupiająca autorów nieindeksowanych, nie będących pracownikami uczelni. Procedury importujące
    dane z zewnętrznych systemów informatycznych będą przypisywać do tej jednostki osoby, które zakończyły
    pracę na uczelni. """, related_name="obca_jednostka")

    pokazuj_punktacje_wewnetrzna = models.BooleanField(
        'Pokazuj punktację wewnętrzną na stronie rekordu',
        default=True
    )
    pokazuj_index_copernicus = models.BooleanField(
        'Pokazuj Index Copernicus na stronie rekordu',
        default=True
    )
    pokazuj_status_korekty = OpcjaWyswietlaniaField(
        'Pokazuj status korekty na stronie rekordu',
    )

    pokazuj_ranking_autorow = OpcjaWyswietlaniaField(
        'Pokazuj ranking autorów',
    )

    pokazuj_raport_autorow = OpcjaWyswietlaniaField(
        'Pokazuj raport autorów'
    )

    pokazuj_raport_jednostek = OpcjaWyswietlaniaField(
        'Pokazuj ranking jednostek'
    )

    pokazuj_raport_wydzialow = OpcjaWyswietlaniaField(
        'Pokazuj ranking wydziałów'
    )

    pokazuj_raport_dla_komisji_centralnej = OpcjaWyswietlaniaField(
        'Pokazuj raport dla Komisji Centralnej'
    )

    pokazuj_praca_recenzowana = OpcjaWyswietlaniaField(
        'Pokazuj opcję "Praca recenzowana"'
    )

    domyslnie_afiliuje = models.BooleanField(
        'Domyślnie zaznaczaj, że autor afiliuje',
        help_text="""Przy powiązaniach autor + wydawnictwo, zaznaczaj domyślnie,
        że autor afiliuje do jednostki, która jest wpisywana.""",
        default=True,
    )

    pokazuj_liczbe_cytowan_w_rankingu = OpcjaWyswietlaniaField(
        "Pokazuj liczbę cytowań w rankingu"
    )

    pokazuj_liczbe_cytowan_na_stronie_autora = OpcjaWyswietlaniaField(
        "Pokazuj liczbę cytowań na podstronie autora",
        help_text="""Liczba cytowań będzie wyświetlana, gdy większa od 0"""
    )

    clarivate_username = models.CharField(
        verbose_name="Nazwa użytkownika",
        null=True,
        blank=True,
        max_length=50)

    clarivate_password = models.CharField(
        verbose_name="Hasło",
        null=True,
        blank=True,
        max_length=50)

    class Meta:
        verbose_name = "uczelnia"
        verbose_name_plural = "uczelnie"
        app_label = 'bpp'

    def get_absolute_url(self):
        return reverse("bpp:browse_uczelnia", args=(self.slug,))

    def wydzialy(self):
        """Widoczne wydziały -- do pokazania na WWW"""
        return Wydzial.objects.filter(uczelnia=self, widoczny=True)

    def wosclient(self):
        """
        :rtype: wosclient.wosclient.WoSClient
        """
        if not self.clarivate_username:
            raise ImproperlyConfigured("Brak użytkownika API w konfiguracji serwera")

        if not self.clarivate_password:
            raise ImproperlyConfigured("Brak hasła do API w konfiguracji serwera")

        from wosclient.wosclient import WoSClient
        return WoSClient(
            self.clarivate_username,
            self.clarivate_password)

@six.python_2_unicode_compatible
class Wydzial(ModelZAdnotacjami, ModelZPBN_ID):
    uczelnia = models.ForeignKey(Uczelnia)
    nazwa = models.CharField(
        max_length=512,
        unique=True,
        help_text='Pełna nazwa wydziału, np. "Wydział Lekarski"')
    skrot_nazwy = models.CharField(
        max_length=250,
        unique=True,
        blank=True,
        null=True,
        help_text='Skrót nazwy wydziału, wersja czytelna, np. "Wydz. Lek."')
    skrot = models.CharField(
        "Skrót",
        max_length=10,
        unique=True,
        help_text='Skrót nazwy wydziału, wersja minimalna, np. "WL"')

    opis = models.TextField(null=True, blank=True)
    slug = AutoSlugField(populate_from='nazwa',
                         max_length=512, unique=True)
    poprzednie_nazwy = models.CharField(max_length=4096, blank=True, null=True, default='')
    kolejnosc = models.IntegerField("Kolejność", default=0)
    widoczny = models.BooleanField(
        default=True,
        help_text="""Czy wydział ma być widoczny przy przeglądaniu strony dla zakładki "Uczelnia"?""")

    zezwalaj_na_ranking_autorow = models.BooleanField(
        "Zezwalaj na generowanie rankingu autorów dla tego wydziału",
        default=True)

    zarzadzaj_automatycznie = models.BooleanField(
        "Zarządzaj automatycznie",
        default=True,
        help_text="""Wydział ten będzie dowolnie modyfikowany przez procedury importujace dane z zewnętrznych
        systemów informatycznych. W przypadku, gdy pole ma ustawioną wartość na 'fałsz', wydział ten może być"""
    )

    otwarcie = models.DateField("Data otwarcia wydziału", blank=True, null=True)
    zamkniecie = models.DateField("Data zamknięcia wydziału", blank=True, null=True)

    class Meta:
        verbose_name = "wydział"
        verbose_name_plural = "wydziały"
        ordering = ['kolejnosc', 'skrot']
        app_label = 'bpp'

    def __str__(self):
        return self.nazwa

    def get_absolute_url(self):
        return reverse("bpp:browse_wydzial", args=(self.slug,))

    def jednostki(self):
        """Lista jednostek - dla WWW"""
        return Jednostka.objects.filter(wydzial=self, widoczna=True)


class JednostkaManager(FulltextSearchMixin, models.Manager):
    def create(self, *args, **kw):
        if 'wydzial' in kw and not ('uczelnia' in kw or 'uczelnia_id' in kw):
            # Kompatybilność wsteczna, z czasów, gdy nie było metryczki historycznej
            # dla obecności jednostki w wydziałach
            kw['uczelnia'] = kw['wydzial'].uczelnia
        return super(JednostkaManager, self).create(*args, **kw)

@six.python_2_unicode_compatible
class Jednostka(ModelZAdnotacjami, ModelZPBN_ID):
    uczelnia = models.ForeignKey(Uczelnia)

    wydzial = models.ForeignKey(Wydzial, verbose_name="Wydział", blank=True, null=True)
    aktualna = models.BooleanField(default=False, help_text="""Jeżeli dana jednostka wchodzi w struktury wydziału
    (czyli jej obecność w strukturach wydziału nie została zakończona z określoną datą), to pole to będzie miało
    wartość 'PRAWDA'.""")

    nazwa = models.CharField(max_length=512, unique=True)
    skrot = models.CharField("Skrót", max_length=128, unique=True)
    opis = models.TextField(blank=True, null=True)
    slug = AutoSlugField(
        populate_from='nazwa',
        unique=True)

    widoczna = models.BooleanField(default=True, db_index=True)
    wchodzi_do_raportow = models.BooleanField(
        "Wchodzi do raportów", default=True, db_index=True)
    email = models.EmailField("E-mail", max_length=128, blank=True, null=True)
    www = models.URLField("WWW", max_length=1024, blank=True, null=True)

    skupia_pracownikow = models.BooleanField(
        "Skupia pracowników",
        default=True,
        help_text="""Ta jednostka skupia osoby będące faktycznymi pracownikami uczelni. Odznacz dla jednostek
         typu 'Studenci', 'Doktoranci', 'Pracownicy emerytowani' itp."""
    )

    zarzadzaj_automatycznie = models.BooleanField(
        "Zarządzaj automatycznie",
        default=True,
        help_text="""Jednostka ta będzie dowolnie modyfikowana przez procedury importujace dane z zewnętrznych
        systemów informatycznych"""
    )

    search = VectorField(blank=True, null=True)

    objects = JednostkaManager()

    class Meta:
        verbose_name = 'jednostka'
        verbose_name_plural = 'jednostki'
        ordering = ['nazwa']
        app_label = 'bpp'

    def get_absolute_url(self):
        return reverse("bpp:browse_jednostka", args=(self.slug,))

    def __str__(self):
        ret = self.nazwa

        try:
            wydzial = self.wydzial
        except:  # TODO catch-all
            wydzial = None

        if wydzial is not None:
            ret += " (%s)" % self.wydzial.skrot

        return ret

    def dodaj_autora(self, autor, funkcja=None, rozpoczal_prace=None, zakonczyl_prace=None):
        ret = Autor_Jednostka.objects.create(
            autor=autor, jednostka=self, funkcja=funkcja,
            rozpoczal_prace=rozpoczal_prace, zakonczyl_prace=zakonczyl_prace)
        # Odśwież obiekt - pobierz ewentualną zmiane pola 'aktualna_jednostka', obsługiwaną
        # przez trigger bazodanowy (migracja 0046)
        autor.refresh_from_db()
        return ret

    zatrudnij = dodaj_autora

    def obecni_autorzy(self):
        dzis = timezone.now().date()

        return Autor.objects.filter(
            Q(autor_jednostka__zakonczyl_prace__gte=dzis) | Q(autor_jednostka__zakonczyl_prace=None),
            Q(autor_jednostka__rozpoczal_prace__lte=dzis) | Q(autor_jednostka__rozpoczal_prace=None),
            autor_jednostka__jednostka=self
        ).distinct()

    pracownicy = obecni_autorzy

    def autorzy_na_strone_jednostki(self):
        return self.obecni_autorzy().filter(pokazuj=True)

    def kierownik(self):
        try:
            return self.obecni_autorzy().get(autor_jednostka__funkcja__nazwa='kierownik')
        except Autor.DoesNotExist:
            return None

    def prace_w_latach(self):
        from bpp.models.cache import Rekord
        return Rekord.objects.prace_jednostki(self).values_list(
            'rok', flat=True).distinct().order_by('rok')

    def przypisania(self):
        return Jednostka_Wydzial.objects.filter(jednostka_id=self.pk).order_by('od')

    def przypisania_dla_czasokresu(self, od, do):
        return Jednostka_Wydzial.objects.dla_czasokresu(od=od, do=do).filter(jednostka_id=self.pk)

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
            do_not_null=Coalesce("do", date(9999, 12, 31))
        )

    def dla_czasokresu(self, od, do):
        return self.od_do_not_null().filter(
            od_not_null__lte=do or date(9999, 12, 31),
            do_not_null__gte=od or date(1, 1, 1)
        )

    def wyczysc_przypisania(self, jednostka, parent_od=None, parent_do=None):
        parent_do_not_null = parent_do or date(9999, 12, 31)

        for jw in self.dla_czasokresu(parent_od, parent_do).filter(jednostka_id=jednostka.pk).order_by("od_not_null"):
            od = jw.od or date(1, 1, 1)
            do = jw.do or date(9999, 12, 31)

            # Jeżeli zakres kończy przed parent.do, to nie ma prawa
            # być takiej sytuacji, bo funkcja przypisania_dla_czasokresu
            # ma nie zwracać takich zakresów. Ma prawo kończyć się w dniu parent.do
            # ale nie ma się kończyć przed
            assert do >= parent_od, \
                "To nie powinno się zdarzyć. Funkcja przypisania_dla_czasokresu działa niepoprawnie"

            # Jeżeli zakres zaczyna się za parent.do, to nie ma prawa
            # być takiej sytuacji, bo funkcja przypisania_dla_czasokresu
            # ma nie zwracać takich zakresów. Ma prawo zaczynać się w dniu parent.od
            # ale nie ma prawa zaczynać się za:
            assert od <= parent_do_not_null, \
                "To nie powinno się zdarzyć. Funkcja przypisania_dla_czasokresu działa niepoprawnie"

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
                    jednostka=jw.jednostka, wydzial=jw.wydzial,
                    od=new_od, do=old_do
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

@six.python_2_unicode_compatible
class Jednostka_Wydzial(models.Model):
    jednostka = models.ForeignKey(Jednostka)
    wydzial = models.ForeignKey(Wydzial)
    od = models.DateField(null=True, blank=True)
    do = models.DateField(null=True, blank=True)

    objects = Jednostka_Wydzial_Manager()

    class Meta:
        verbose_name = "powiązanie jednostka-wydział"
        verbose_name_plural = "powiązania jednostka-wydział"
        ordering = ('-od',)

    def __str__(self):
        return "%s - %s (%s, %s)" % (self.jednostka, self.wydzial, self.od, self.do)

    def clean(self):
        try:
            self.wydzial
        except:
            raise ValidationError({'wydzial': 'Określ wydział'})

        if self.wydzial.uczelnia_id != self.jednostka.uczelnia_id:
            raise ValidationError({"wydzial": "Uczelnia dla wydziału i jednostki musi być identyczna."})

        if self.od is not None and self.do is not None:
            if self.od >= self.do:
                raise ValidationError({'od': "Wartość w polu 'Od' musi byc mniejsza, niż wartość w polu 'Do'.",
                                       'do': "Wartosć w polu 'Do' musi być większa, niż wartość w polu 'Od'."})

        if self.pk:
            try:
                old = Jednostka_Wydzial.objects.get(pk=self.pk)
                if old.jednostka_id != self.jednostka_id:
                    raise ValidationError({"jednostka": "Zmiana ID jednostki dla tych obiektów nie jest obsługiwana."})
            except Jednostka_Wydzial.DoesNotExist:
                pass

        # Sprawdz zakres dat
        cnt = Jednostka_Wydzial.objects.dla_czasokresu(self.od, self.do) \
            .filter(jednostka_id=self.jednostka_id) \
            .exclude(id=self.id) \
            .count()

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
                {"do": "Data w polu \"Do\" nie może być większa lub równa, niż data aktualna (dzisiejsza)."})
