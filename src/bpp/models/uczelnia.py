# -*- encoding: utf-8 -*-

"""
Struktura uczelni.
"""
from typing import List, Union

from autoslug import AutoSlugField
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models
from django.db.models import SET_NULL, Max
from django.urls.base import reverse
from model_utils import Choices

from pbn_api.exceptions import WillNotExportError
from ..util import year_last_month
from .fields import OpcjaWyswietlaniaField

from django.utils.functional import cached_property

from bpp.models import ModelZAdnotacjami, NazwaISkrot, const
from bpp.models.abstract import ModelZPBN_ID, NazwaWDopelniaczu


class UczelniaManager(models.Manager):
    def get_default(self) -> Union["Uczelnia", None]:
        return self.all().only("pk").first()

    def get_for_request(self, request):
        return self.get_default()

    @cached_property
    def default(self):
        return self.get_default()

    def do_roku_default(self=None, request=None):
        if self is None:
            # Uruchomione przez migrację
            return
        uczelnia = self.get_default()
        if (
            uczelnia is None
            or uczelnia.metoda_do_roku_formularze
            == const.DO_STYCZNIA_POPRZEDNI_POTEM_OBECNY
        ):
            return year_last_month()
        if uczelnia.metoda_do_roku_formularze == const.NAJWIEKSZY_REKORD:
            from bpp.models.cache import Rekord

            return Rekord.objects.all().aggregate(Max("rok"))["rok__max"]
        raise NotImplementedError


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

    pbn_uid = models.ForeignKey(
        "pbn_api.Institution",
        verbose_name="Odpowiednik w PBN",
        on_delete=SET_NULL,
        null=True,
        blank=True,
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

    pokazuj_ranking_autorow = OpcjaWyswietlaniaField(
        "Pokazuj ranking autorów",
    )

    pokazuj_raport_uczelni = OpcjaWyswietlaniaField(
        "Pokazuj raport uczelni", default=OpcjaWyswietlaniaField.POKAZUJ_NIGDY
    )

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

    DO_ROKU = Choices(
        (
            const.DO_STYCZNIA_POPRZEDNI_POTEM_OBECNY,
            "do stycznia poprzedni, potem obecny",
        ),
        (const.NAJWIEKSZY_REKORD, "najwiekszy rok rekordu w bazie"),
    )

    metoda_do_roku_formularze = models.CharField(
        "Data w polu 'do roku' w formularzach",
        choices=DO_ROKU,
        default=const.DO_STYCZNIA_POPRZEDNI_POTEM_OBECNY,
        max_length=30,
        help_text="Decyduje o sposobie wyświetlania maksymalnej daty 'Do roku' w formularzach. ",
    )

    pbn_integracja = models.BooleanField(
        default=False,
        verbose_name="Czy używać integracji z PBN?",
        help_text="Wymaga prawidłowo wypełnionych pól 'Adres API w PBN', 'Nazwa aplikacji w PBN', "
        "'Token aplikacji w PBN' oraz łączności między serwerem BPP a serwerem PBN. ",
    )

    pbn_aktualizuj_na_biezaco = models.BooleanField(
        default=False,
        verbose_name="Włącz opcjonalną aktualizację przy edycji",
        help_text="""Aktualizuj rekordy w PBN przy zapisie rekordu, gdy redaktor kliknie odpowiedni przycisk.
        Wybranie tej opcji spowoduje, ze na podstronach modułu redagowania dla wydawnictw pojawią się
        przyciski 'Zapisz i wyślij do PBN'. """,
    )

    pbn_api_root = models.URLField(
        "Adres API w PBN", default="https://pbn-micro-alpha.opi.org.pl"
    )
    pbn_app_name = models.CharField(
        "Nazwa aplikacji w PBN", blank=True, null=True, max_length=128
    )
    pbn_app_token = models.CharField(
        "Token aplikacji w PBN", blank=True, null=True, max_length=128
    )

    pbn_api_user = models.ForeignKey(
        "bpp.BppUser",
        on_delete=SET_NULL,
        verbose_name="Użytkownik BPP dla PBN API",
        help_text="Użytkownik po stronie BPP który bedzie odpowiedzialny za operacje "
        "przeprowadzane w tle przez procesy działające na serwerze i pobierające dane z PBN np w nocy. Jeżeli ten "
        "użytkownik dokona autoryzacji w PBN za pomocą przeglądarki, to możliwe będzie również aktualizowanie "
        "(wgrywanie) rekordów przez niego na serwer PBN. ",
        blank=True,
        null=True,
    )

    objects = UczelniaManager()

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
                        "obca_jednostka": "Obca jednostka musi faktycznie być obca. Wybrana ma ustaloną wartość "
                        "'skupia pracowników' na PRAWDA, czyli nie jest obcą jednostką. "
                    }
                )

        if self.pbn_aktualizuj_na_biezaco and not self.pbn_integracja:
            raise ValidationError(
                {
                    "pbn_aktualizuj_na_biezaco": "Jeżeli nie używasz integracji z PBN, odznacz również i to pole. "
                }
            )

        if self.pbn_integracja:
            # Wykonaj próbne pobranie rekordu z PBNu
            client = self.pbn_client()
            try:
                client.get_languages()
            except Exception as e:
                raise ValidationError(
                    {
                        "pbn_integracja": f"Nie można pobrać przykładowych rekordów przez API celem weryfikacji. "
                        f"Kod błędu: {e}. "
                        f"Jeżeli bład nie dotyczy problemów z siecią lub z autoryzacją, skontaktuj się"
                        f"z administratorem. "
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

    def pbn_client(self, pbn_user_token=None):
        """
        Zwraca klienta PBNu
        """
        from pbn_api import client

        class UczelniaTransport(client.RequestsTransport):
            def authorize(self, base_url, app_id, token):
                if not pbn_user_token:
                    raise WillNotExportError(
                        "Najpierw wykonaj autoryzację w PBN API za pomocą menu dostępnego "
                        "na głównej stronie (operacje -> autoryzuj w PBN)"
                    )
                self.access_token = pbn_user_token
                return True

        if not self.pbn_app_name:
            raise ImproperlyConfigured("Brak nazwy aplikacji dla API PBN")

        if not self.pbn_app_token:
            raise ImproperlyConfigured("Brak tokena aplikacji dla API PBN")

        transport = UczelniaTransport(
            self.pbn_app_name, self.pbn_app_token, self.pbn_api_root, pbn_user_token
        )
        return client.PBNClient(transport)

    def ukryte_statusy(self, dla_funkcji: str) -> List[int]:
        """
        :param dla_funkcji: "sloty", "raporty", "multiwyszukiwarka", "rankingi"
        :return: lista numerów PK obiektów :class:`bpp.models.system.Status_Korekty`
        """
        return self.ukryj_status_korekty_set.filter(**{dla_funkcji: True}).values_list(
            "status_korekty", flat=True
        )

    def sprawdz_uprawnienie(self, attr, request):
        res = getattr(self, f"pokazuj_{attr}")
        if res == OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE:
            return True

        if res == OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM:
            if request.user.is_anonymous:
                return False
            return True

        if res == OpcjaWyswietlaniaField.POKAZUJ_GDY_W_ZESPOLE:
            if request.user.is_anonymous:
                return False
            if not request.user.is_staff:
                return False
            return True

        if res == OpcjaWyswietlaniaField.POKAZUJ_NIGDY:
            return False

        raise NotImplementedError()

    def autorzy_z_uczelni(self):
        # Zwróc listę wszystkich autorów, którzy są przypisani do
        # nie-obcych jednostek
        from bpp.models.struktura import Autor

        return Autor.objects.filter(
            autor_jednostka__jednostka__skupia_pracownikow=True,
            autor_jednostka__jednostka__uczelnia=self,
            autor_jednostka__jednostka__pk__gte=0,
        ).distinct()


class Ukryj_Status_Korekty(models.Model):
    uczelnia = models.ForeignKey(Uczelnia, on_delete=models.CASCADE)
    status_korekty = models.ForeignKey("Status_Korekty", on_delete=models.CASCADE)

    multiwyszukiwarka = models.BooleanField(
        default=True,
        help_text="Nie dotyczy użytkownika zalogowanego. Użytkownik zalogowany widzi wszystkie prace "
        "w wyszukiwaniu. ",
    )
    podglad = models.BooleanField(
        default=True,
        help_text="Uniemożliwia podgląd prac na stronie szczegółów rekordu oraz uniemożliwia wyszukanie takich "
        "prac przez pole globalnego wyszukania.",
    )
    raporty = models.BooleanField(
        "Raporty",
        default=True,
        help_text="Ukrywa prace w raporcie autora, " "jednostki, uczelni",
    )
    rankingi = models.BooleanField("Rankingi", default=True)
    sloty = models.BooleanField(
        "Raporty slotów",
        default=True,
        help_text="Prace o wybranym statusie nie będą miały liczonych punktów i slotów w chwili"
        "zapisywania rekordu do bazy danych. Jeżeli zmieniasz to ustawienie dla prac które już są w bazie danych "
        "to ich punktacja zniknie z bazy w dniu następnym (skasowana zostanie podczas nocnego przeindeksowania bazy).",
    )
    api = models.BooleanField(
        "API",
        default=True,
        help_text="Dotyczy ukrywania prac w API JSON-REST oraz OAI-PMH",
    )

    def __str__(self):
        res = (
            f'ukryj "{self.status_korekty}" dla '
            f"{'multiwyszukiwarki, ' if self.multiwyszukiwarka else ''}"
            f"{'raportów, ' if self.raporty else ''}"
            f"{'rankingów, ' if self.rankingi else ''}"
            f"{'slotów. ' if self.sloty else ''}"
        )

        if res.endswith(", "):
            res = res[:-2] + ". "
        return res

    class Meta:
        unique_together = [("uczelnia", "status_korekty")]
        verbose_name = "ustawienie ukrywania statusu korekty"
        verbose_name_plural = "ustawienia ukrywania statusów korekt"
