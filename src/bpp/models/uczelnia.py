# -*- encoding: utf-8 -*-

"""
Struktura uczelni.
"""

from autoslug import AutoSlugField
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models
from django.db.models import SET_NULL
from django.urls.base import reverse

from bpp.models import ModelZAdnotacjami, NazwaISkrot
from bpp.models.abstract import NazwaWDopelniaczu, ModelZPBN_ID
from .fields import OpcjaWyswietlaniaField


class Uczelnia(ModelZAdnotacjami, ModelZPBN_ID, NazwaISkrot, NazwaWDopelniaczu):
    slug = AutoSlugField(populate_from="skrot", unique=True)
    logo_www = models.ImageField(
        "Logo na stronę WWW",
        upload_to="logo",
        help_text="""Plik w formacie bitmapowym, np. JPEG lub PNG,
        w rozdzielczości maks. 100x100""",
        blank=True,
        null=True,
    )
    logo_svg = models.FileField(
        "Logo wektorowe (SVG)", upload_to="logo_svg", blank=True, null=True
    )
    favicon_ico = models.FileField(
        "Ikona ulubionych (favicon)", upload_to="favicon", blank=True, null=True
    )

    obca_jednostka = models.ForeignKey(
        "bpp.Jednostka",
        SET_NULL,
        null=True,
        blank=True,
        help_text="""
    Jednostka skupiająca autorów nieindeksowanych, nie będących pracownikami uczelni. Procedury importujące
    dane z zewnętrznych systemów informatycznych będą przypisywać do tej jednostki osoby, które zakończyły
    pracę na uczelni. """,
        related_name="obca_jednostka",
    )

    ranking_autorow_rozbij_domyslnie = models.BooleanField(
        'Zaznacz domyślnie "Rozbij punktację na jednostki i wydziały" dla rankingu autorów',
        default=False,
    )

    pokazuj_punktacje_wewnetrzna = models.BooleanField(
        "Pokazuj punktację wewnętrzną na stronie rekordu", default=True
    )
    pokazuj_index_copernicus = models.BooleanField(
        "Pokazuj Index Copernicus na stronie rekordu", default=True
    )
    pokazuj_punktacja_snip = models.BooleanField(
        "Pokazuj punktację SNIP na stronie rekordu", default=True
    )
    pokazuj_status_korekty = OpcjaWyswietlaniaField(
        "Pokazuj status korekty na stronie rekordu",
    )

    pokazuj_ranking_autorow = OpcjaWyswietlaniaField("Pokazuj ranking autorów",)

    pokazuj_raport_autorow = OpcjaWyswietlaniaField("Pokazuj raport autorów")

    pokazuj_raport_jednostek = OpcjaWyswietlaniaField(
        "Pokazuj raport jednostek", default=OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
    )

    pokazuj_raport_wydzialow = OpcjaWyswietlaniaField(
        "Pokazuj raport wydziałów", default=OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
    )

    pokazuj_raport_dla_komisji_centralnej = OpcjaWyswietlaniaField(
        "Pokazuj raport dla Komisji Centralnej"
    )

    pokazuj_praca_recenzowana = OpcjaWyswietlaniaField(
        'Pokazuj opcję "Praca recenzowana"'
    )

    domyslnie_afiliuje = models.BooleanField(
        "Domyślnie zaznaczaj, że autor afiliuje",
        help_text="""Przy powiązaniach autor + wydawnictwo, zaznaczaj domyślnie,
        że autor afiliuje do jednostki, która jest wpisywana.""",
        default=True,
    )

    pokazuj_liczbe_cytowan_w_rankingu = OpcjaWyswietlaniaField(
        "Pokazuj liczbę cytowań w rankingu"
    )

    pokazuj_liczbe_cytowan_na_stronie_autora = OpcjaWyswietlaniaField(
        "Pokazuj liczbę cytowań na podstronie autora",
        help_text="""Liczba cytowań będzie wyświetlana, gdy większa od 0""",
    )

    pokazuj_tabele_slotow_na_stronie_rekordu = OpcjaWyswietlaniaField(
        "Pokazuj tabelę slotów na stronie rekordu",
        default=OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM,
    )

    pokazuj_raport_slotow_autor = OpcjaWyswietlaniaField(
        "Pokazuj raport slotów - autor",
        default=OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM,
    )

    pokazuj_raport_slotow_zerowy = OpcjaWyswietlaniaField(
        "Pokazuj raport slotów zerowy",
        default=OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM,
    )

    pokazuj_raport_slotow_uczelnia = OpcjaWyswietlaniaField(
        "Pokazuj raport slotów - uczelnia",
        default=OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM,
    )

    wydruk_logo = models.BooleanField("Pokazuj logo na wydrukach", default=False)

    wydruk_logo_szerokosc = models.SmallIntegerField(
        "Szerokość logo na wydrukach",
        default=250,
        help_text="Podaj wartość w pikselach. Wysokość zostanie przeskalowana"
        " proporcjonalnie. ",
    )

    wydruk_parametry_zapytania = models.BooleanField(
        "Pokazuj parametry zapytania na wydrukach", default=True
    )

    wyszukiwanie_rekordy_na_strone_anonim = models.SmallIntegerField(
        "Ilość rekordów na stronę - anonim",
        default=200,
        help_text="Ilość rekordów w wyszukiwaniu powyżej której znika opcja"
        '"Pokaż wszystkie" i "Drukuj" dla użytkownika anonimowego. '
        "Nie jest zalecane ustawianie powyżej 500. ",
    )

    wyszukiwanie_rekordy_na_strone_zalogowany = models.SmallIntegerField(
        "Ilość rekordów na stronę - anonim",
        default=10000,
        help_text="Ilość rekordów w wyszukiwaniu powyżej której znika opcja"
        '"Pokaż wszystkie" i "Drukuj" dla użytkownika zalogowanego. '
        "Nie jest zalecane ustawianie powyżej 10000. ",
    )

    podpowiadaj_dyscypliny = models.BooleanField(
        default=True,
        help_text="""W sytuacji gdy to pole ma wartość "PRAWDA", system będzie podpowiadał dyscyplinę
        naukową dla powiązania rekordu wydawnictwa i autora w sytuacji, gdy autor ma na dany rok
        określoną tylko jedną dyscyplinę. W sytuacji przypisania dla autora dwóch dyscyplin na dany rok,
        pożądaną dyscyplinę będzie trzeba wybrać ręcznie, niezależnie od ustawienia tego pola. """,
    )

    sortuj_jednostki_alfabetycznie = models.BooleanField(
        default=True,
        help_text="""Jeżeli ustawione na 'FAŁSZ', sortowanie jednostek będzie odbywało się ręcznie 
        tzn za pomocą ustalonej przez administratora systemu kolejności. """,
    )

    clarivate_username = models.CharField(
        verbose_name="Nazwa użytkownika", null=True, blank=True, max_length=50
    )

    clarivate_password = models.CharField(
        verbose_name="Hasło", null=True, blank=True, max_length=50
    )

    class Meta:
        verbose_name = "uczelnia"
        verbose_name_plural = "uczelnie"
        app_label = "bpp"

    def get_absolute_url(self):
        return reverse("bpp:browse_uczelnia", args=(self.slug,))

    def wydzialy(self):
        """Widoczne wydziały -- do pokazania na WWW"""
        from .wydzial import Wydzial

        return Wydzial.objects.filter(uczelnia=self, widoczny=True)

    def clean(self):
        if self.obca_jednostka is not None:
            if self.obca_jednostka.skupia_pracownikow:
                raise ValidationError(
                    {
                        "obca_jednostka": "Obca jednostka musi faktycznei być obca. Wybrana ma ustaloną wartość "
                        "'skupia pracowników' na PRAWDA, czyli nie jest obcą jednostką. "
                    }
                )

    def save(self, *args, **kw):
        self.clean()
        return super().save(*args, **kw)

    def wosclient(self):
        """
        :rtype: wosclient.wosclient.WoSClient
        """
        if not self.clarivate_username:
            raise ImproperlyConfigured("Brak użytkownika API w konfiguracji serwera")

        if not self.clarivate_password:
            raise ImproperlyConfigured("Brak hasła do API w konfiguracji serwera")

        from wosclient.wosclient import WoSClient

        return WoSClient(self.clarivate_username, self.clarivate_password)
