"""
Struktura uczelni.
"""

from typing import TYPE_CHECKING, Union

from autoslug import AutoSlugField
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import ProgrammingError, models
from django.db.models import SET_NULL, Max, URLField
from django.urls.base import reverse
from django.utils.functional import cached_property
from model_utils import Choices
from tinymce.models import HTMLField

from bpp.fields import EncryptedTextField
from bpp.models import ModelZAdnotacjami, NazwaISkrot
from bpp.models.abstract import ModelZPBN_ID, NazwaWDopelniaczu
from pbn_api.exceptions import WillNotExportError

from .. import const
from ..const import GR_RAPORTY_WYSWIETLANIE
from ..util import year_last_month
from .fields import OpcjaWyswietlaniaField

if TYPE_CHECKING:
    import pbn_api  # noqa


class UczelniaManager(models.Manager):
    def get_default(self) -> Union["Uczelnia", None]:
        try:
            return self.all().first()
        except ProgrammingError:
            # Błąd może wystapić w sytuacji, gdy do obiektu Uczelnia po stronie kodu zostały
            # dodane jakieś kolumny, ale nie zostały jeszcze dodane do bazy danych. Próba "grzebnięcia"
            # po bazie spowoduje błąd. Spróbujemy wobec tego pobrać wyłacznie PK rekordu:
            return self.all().only("pk").first()

    def get_for_request(self, request):
        if hasattr(request, "_uczelnia"):
            return request._uczelnia

        return self.get_default()

    def get_for_pbn_background(self, uczelnia_id) -> "Uczelnia":
        """Resolwer uczelni dla PBN-owych zadań w tle (Celery, kolejki).

        W instalacji multi-hosted KAŻDY entrypoint (widok) zna konkretną
        uczelnię z requestu (``get_for_request``) i MUSI przekazać jej
        ``pk`` do zadania. Brak ``uczelnia_id`` to błąd programistyczny —
        świadomie NIE robimy fallbacku do ``get_default()``, bo wybrałby
        pierwszą-z-brzegu uczelnię, która może nie mieć skonfigurowanego
        PBN (to było źródłem błędu ``403 token aplikacji null``).

        :raises ValueError: gdy ``uczelnia_id`` jest ``None``.
        :raises Uczelnia.DoesNotExist: gdy uczelnia o danym id nie istnieje.
        """
        if uczelnia_id is None:
            raise ValueError(
                "Operacja PBN w tle wymaga jawnego uczelnia_id — w trybie "
                "multi-hosted nie ma fallbacku do uczelni domyślnej. "
                "Entrypoint (widok) musi przekazać id uczelni z requestu."
            )
        return self.get(pk=uczelnia_id)

    def get_for_site(self, site) -> Union["Uczelnia", None]:
        """Zwraca Uczelnię powiązaną z danym obiektem Site."""
        if site is None:
            return self.get_default()
        return getattr(site, "uczelnia", None)

    @cached_property
    def default(self):
        return self.get_default()

    def do_roku_default(self=None, request=None):
        # Cienki delegator do funkcji modułowej `do_roku_default` (niżej).
        # Trzymany dla zgodności z `Uczelnia.objects.do_roku_default` używanym
        # jako `initial=` w formularzach raportów i w testach.
        return do_roku_default(request=request)


def do_roku_default(request=None):
    """Domyślna wartość `do_roku` dla formularzy raportów oraz pola modelu
    `RaportSlotowUczelnia.do_roku`.

    Funkcja MODUŁOWA (nie metoda managera) celowo: default pola modelu musi
    być stabilnie serializowalny w migracjach. Wcześniej był to bound-method
    instancji managera (`Uczelnia.objects.do_roku_default`), który Django
    serializował jako wersję unbound — nigdy nie równą wersji z modelu, przez
    co `makemigrations` w nieskończoność wykrywał „zmianę" pola (wieczny
    drift). Bez `self` działa zarówno serializowalnie, jak i w runtime
    (zwraca prawdziwy rok, nie None).
    """
    uczelnia = Uczelnia.objects.get_default()
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
    site = models.OneToOneField(
        "sites.Site",
        verbose_name="Strona (domena)",
        on_delete=models.PROTECT,
        related_name="uczelnia",
        help_text="Powiązanie z obiektem Site (domena internetowa tej uczelni).",
    )

    theme_name = models.CharField(
        "Motyw kolorystyczny",
        max_length=50,
        default="app-green",
        # Dozwolone wartości pochodzą z settings.BPP_THEMES, walidowane w
        # UczelniaAdminForm — celowo BEZ `choices=` na poziomie modelu, żeby
        # zmiana listy motywów nie generowała migracji.
    )

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

    tytul_strony_glownej = models.TextField(
        "Tytuł strony głównej",
        default="Bibliografia Publikacji Pracowników",
        help_text="HTML z tytułem strony głównej. Możesz użyć tagów HTML do formatowania.",
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

    ilosc_jednostek_na_strone = models.PositiveIntegerField(
        default=150,
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
        help_text="""Ilość jednostek wyświetlanych na podstronie prezentacji
        danych dla użytkownika końcowego (strona główna -> przeglądaj -> jednostki)""",
    )

    pokazuj_tylko_jednostki_nadrzedne = models.BooleanField(
        default=False,
        help_text="""Pokazuj tylko jednostki nadrzędne na stronie prezentacji
        danych dla użytkownika końcowego""",
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

    ranking_autorow_bez_kol_naukowych = models.BooleanField(
        "Ranking autorów bez kół naukowych", default=True
    )

    pokazuj_praca_recenzowana = OpcjaWyswietlaniaField(
        'Pokazuj opcję "Praca recenzowana"'
    )

    pokazuj_formularz_zglaszania_publikacji = OpcjaWyswietlaniaField(
        "Pokazuj opcję 'Zgłoś nową publikację'",
        help_text="Czy pokazywać formularz zgłaszania publikacji?",
    )

    wymagaj_logowania_zglos_publikacje = models.BooleanField(
        "Wymagaj zalogowania użytkownika dla formularza zgłaszania publikacji",
        default=False,
        help_text="Jeśli zaznaczone, użytkownik musi się zalogować przed zgłoszeniem publikacji, "
        "niezależnie od ustawienia widoczności przycisku 'Zgłoś nową publikację'. "
        "Niezalogowani użytkownicy zostaną przekierowani na stronę logowania.",
    )

    domyslnie_afiliuje = models.BooleanField(
        "Domyślnie zaznaczaj, że autor afiliuje",
        help_text="""Przy powiązaniach autor + wydawnictwo, zaznaczaj domyślnie,
        że autor afiliuje do jednostki, która jest wpisywana.""",
        default=True,
    )

    nowy_autor_z_formularza_pokazuj = models.BooleanField(
        "Nowy autor tworzony przez autocomplete jest widoczny",
        help_text="""Gdy zaznaczone, autorzy tworzeni automatycznie przez formularze z rozwijaną listą wyboru
        (autocomplete) będą mieli ustawione pole 'pokazuj' na PRAWDA, co oznacza że będą widoczni na stronach
        jednostek oraz w rankingach. Gdy odznaczone (domyślnie), nowi autorzy będą ukryci.""",
        default=False,
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

    wymagaj_informacji_o_oplatach = models.BooleanField(
        "Wymagaj informacji o opłatach (legacy)",
        default=True,
        help_text=(
            "LEGACY: używaj pól wymagaj_oplatach_* poniżej."
            " To pole zachowane dla kompatybilności."
        ),
    )

    wymagaj_oplatach_artykul = models.BooleanField(
        "Wymagaj informacji o opłatach: artykuł",
        default=True,
        help_text=(
            "Gdy zaznaczone, formularz zgłaszania publikacji"
            " będzie pytać o opłaty za artykuły naukowe."
        ),
    )
    wymagaj_oplatach_monografia = models.BooleanField(
        "Wymagaj informacji o opłatach: monografia",
        default=True,
        help_text=(
            "Gdy zaznaczone, formularz zgłaszania publikacji"
            " będzie pytać o opłaty za monografie."
        ),
    )
    wymagaj_oplatach_rozdzial = models.BooleanField(
        "Wymagaj informacji o opłatach: rozdział",
        default=False,
        help_text=(
            "Gdy zaznaczone, formularz zgłaszania publikacji"
            " będzie pytać o opłaty za rozdziały."
        ),
    )
    wymagaj_oplatach_inne = models.BooleanField(
        "Wymagaj informacji o opłatach: inne",
        default=False,
        help_text=(
            "Gdy zaznaczone, formularz zgłaszania publikacji"
            " będzie pytać o opłaty za pozostałe publikacje."
        ),
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
        verbose_name="Nazwa użytkownika", blank=True, default="", max_length=50
    )

    clarivate_password = models.CharField(
        verbose_name="Hasło", blank=True, default="", max_length=50
    )

    orcid_client_id = models.CharField(
        "ORCID Client ID", max_length=128, blank=True, default=""
    )
    orcid_client_secret = models.CharField(
        "ORCID Client Secret", max_length=128, blank=True, default=""
    )
    orcid_sandbox = models.BooleanField(
        "Używaj ORCID Sandbox",
        default=True,
        help_text="Sandbox do testów (sandbox.orcid.org)."
        " Odznacz dla produkcji (orcid.org).",
    )
    orcid_tylko_dla_pracownikow = models.BooleanField(
        "ORCID tylko dla pracowników",
        default=False,
        help_text="Gdy zaznaczone, logowanie przez ORCID będzie dostępne"
        " wyłącznie dla użytkowników z uprawnieniem 'w zespole'"
        " (is_staff) lub superużytkowników.",
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

    pbn_wysylaj_bez_oswiadczen = models.BooleanField(
        default=False,
        verbose_name="Wysyłaj prace bez oświadczeń",
        help_text="Umożliwiaj wysyłanie prac bez oświadczeń do PBN. Domyślnie wyłączone.",
    )

    pbn_api_root = models.URLField(
        "Adres API w PBN", default="https://pbn-micro-alpha.opi.org.pl"
    )
    pbn_app_name = models.CharField(
        "Nazwa aplikacji w PBN", blank=True, default="", max_length=128
    )
    pbn_app_token = models.CharField(
        "Token aplikacji w PBN", blank=True, default="", max_length=128
    )
    dspace_aktywny = models.BooleanField(
        "Włącz eksport do DSpace",
        default=False,
        help_text="Gdy włączone, rekordy afiliowane do tej uczelni można "
        "wysyłać do jej instalacji DSpace.",
    )
    dspace_api_endpoint = models.URLField(
        "Adres API DSpace",
        blank=True,
        default="",
        help_text="np. https://repozytorium.uczelnia.pl/server/api",
    )
    dspace_api_username = models.CharField(
        "Użytkownik API DSpace", max_length=255, blank=True, default=""
    )
    dspace_api_password = EncryptedTextField("Hasło API DSpace", blank=True, default="")
    dspace_domyslny_jezyk_dc = models.CharField(
        "Domyślny język dc.language.iso",
        max_length=8,
        blank=True,
        default="pl",
    )
    pbn_kasuj_dyscypliny_selektywnie = models.BooleanField(
        "Kasuj oświadczenia selektywnie (per osoba)",
        default=True,
        help_text=(
            "Gdy zaznaczone: ``sync_publication`` usuwa oświadczenia "
            "selektywnie per-osoba (DELETE ``/publications/{id}`` z "
            "``{personId, role}``) i wysyła tylko brakujące. Gdy "
            "odznaczone: usuwa wszystkie oświadczenia publikacji jednym "
            "DELETE (``{all: True}``), a następnie wysyła wszystkie "
            "lokalne jako batch. Wariant selektywny zachowuje metadata "
            "PBN (``addedTimestamp`` itd.) dla identycznych rekordów."
        ),
    )
    pbn_api_nie_wysylaj_prac_bez_pk = models.BooleanField(
        "Nie wysyłaj do PBN prac z PK=0", default=False
    )

    pbn_api_afiliacja_zawsze_na_uczelnie = models.BooleanField(
        "Wysyłaj zawsze PBN UID uczelni jako afiliację",
        default=True,
        help_text="Jeżeli praca jest w jednostce z wypełnionym PBN UID bądź w jednostce "
        "innej-niż-obca, zatrudniającej-pracowników, to zaznaczenie tej opcji spowoduje, ze  zamiast PBN "
        "UID tej jednostki zostanie użyty PBN UID uczelni, co efektywnie "
        "spowoduje, że afiliacje w PBN będą na uczelnię, nie zaś na konkretną jednostkę. ",
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

    przydzielaj_1_slot_gdy_udzial_mniejszy = models.BooleanField(
        "Przydzielaj 1 slot gdy udziały za 4 lata mniejsze",
        default=False,
        help_text="""Jeżeli zaznaczone, system będzie przydzielać 1 slot dla autorów, którzy za 4 lata ewaluacji"
                  mieliby mieć mniej, niż 1 slot. Obowiązuje zarówno dla artykułów jak i dla monografii. Zatem,
                  jeżeli ktoś za 4 lata ewaluacji będzie miał zdać 0.8 slota, to gdy ta flaga jest zaznaczona to
                  system zwiększy to do 1 slota za artykuły oraz do 1 slota za monografie. Jeżeli ta flaga jest
                  nie zaznaczona, to system policzy takiej osobie 0.8 slota za artykuły i 0.4 slota za monografie. """,
    )

    class DeklaracjaDostepnosciChoices(models.IntegerChoices):
        NIE_POKAZUJ = 0, "nie pokazuj"
        ZEWNETRZNY_URL = 1, "zewnętrzny adres URL"
        TEKST = 2, "tekst na podstronie serwisu BPP"

    pokazuj_deklaracje_dostepnosci = models.PositiveSmallIntegerField(
        choices=DeklaracjaDostepnosciChoices.choices,
        default=DeklaracjaDostepnosciChoices.NIE_POKAZUJ,
    )

    pokazuj_autorow_obcych_w_przegladaniu_danych = models.BooleanField(
        "Pokazuj autorów obcych w przeglądaniu danych",
        default=False,
        help_text="""Autor obcy to taki, który ma afiliację wyłącznie na
        obcą jednostkę i obca jednostka jest jego jednostką aktualną""",
    )

    pokazuj_autorow_bez_prac_w_przegladaniu_danych = models.BooleanField(
        verbose_name="Pokazuj autorów nie posiadających rekordów publikacji w przeglądaniu danych",
        default=True,
    )

    pokazuj_zrodla_bez_prac_w_przegladaniu_danych = models.BooleanField(
        verbose_name="Pokazuj źródła bez powiązanych rekordów w przeglądaniu danych",
        default=False,
    )

    pokazuj_jednostki_na_pierwszej_stronie = models.BooleanField(default=False)
    pokazuj_wydzialy_na_pierwszej_stronie = models.BooleanField(default=True)

    pokazuj_siec_powiazan = models.BooleanField(
        verbose_name="Pokazuj sieć powiązań autorów",
        default=True,
        help_text="Czy na stronie autora udostępniać interaktywną sieć "
        "współautorstwa. Ustawienie domyślne dla całej uczelni — pojedynczy "
        "autor może je nadpisać własnym polem 'Pokazuj sieć powiązań'.",
    )

    uzywaj_wydzialow = models.BooleanField(
        verbose_name="Używaj wydziałów",
        default=True,
        help_text="""Jeżeli struktura instytucji jest 2-progowa: uczelnia -> wydział -> jednostka, zaznacz na TAK.
        Jeżeli struktura instytucji jest 1-progowa: instytut -> dział, zaznacz na NIE. """,
    )

    deklaracja_dostepnosci_tekst = HTMLField(
        verbose_name="Tekst na stronę BPP dla deklaracji dostępności",
        blank=True,
        null=True,
    )
    deklaracja_dostepnosci_url = URLField(blank=True, default="")

    drukuj_oswiadczenia = models.BooleanField(
        verbose_name="Drukuj oświadczenia dla autorów",
        default=True,
        help_text="Włącza wydruk oświadczeń z podstrony rekordu - wyłącznie dla osób z grupy 'wprowadzanie danych'.",
    )
    drukuj_alternatywne_oswiadczenia = models.BooleanField(
        verbose_name="Drukuj alternatywne oświadczenia dla autorów",
        default=True,
        help_text="Jeżeli autor ma dwie dyscypliny, drukuj zawsze dwa oświadczenia.",
    )

    pytaj_o_zgode_na_publikacje_pelnego_tekstu = models.BooleanField(
        verbose_name="Pytaj o zgodę na publikację pełnego tekstu w formularzu zgłoszeniowym prac",
        default=False,
    )

    # Pola przeniesione z django-constance (per-uczelnia zamiast globalnych)
    google_analytics_property_id = models.CharField(
        "Google Analytics Property ID",
        max_length=100,
        blank=True,
        default="",
        help_text="Np. UA-XXXXXXXX-X lub G-XXXXXXXXXX",
    )
    google_verification_code = models.CharField(
        "Kod weryfikacyjny Google Search Console",
        max_length=100,
        blank=True,
        default="",
    )
    pokazuj_oswiadczenie_ken = models.BooleanField(
        "Pokazuj opcję oświadczenia KEN",
        default=False,
    )
    skrot_wydzialu_w_nazwie_jednostki = models.BooleanField(
        "Wyświetlaj skrót wydziału w nazwie jednostki",
        default=True,
    )
    wydruk_margines_gora = models.CharField(
        "Margines górny wydruku",
        max_length=10,
        default="2cm",
    )
    wydruk_margines_dol = models.CharField(
        "Margines dolny wydruku",
        max_length=10,
        default="2cm",
    )
    wydruk_margines_lewo = models.CharField(
        "Margines lewy wydruku",
        max_length=10,
        default="2cm",
    )
    wydruk_margines_prawo = models.CharField(
        "Margines prawy wydruku",
        max_length=10,
        default="2cm",
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

    def jednostki(self):
        from .jednostka import Jednostka

        return Jednostka.objects.filter(uczelnia=self, widoczna=True, parent=None)

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

        if (
            self.pokazuj_deklaracje_dostepnosci
            == Uczelnia.DeklaracjaDostepnosciChoices.ZEWNETRZNY_URL
            and not self.deklaracja_dostepnosci_url
        ):
            raise ValidationError(
                {
                    "pokazuj_deklaracje_dostepnosci": "Wybrano pokazywanie deklaracji dostępności "
                    "z zewnętrznego adresu URL... ",
                    "deklaracja_dostepnosci_url": "... ale nie został on wpisany poprawnie. Proszę skorygować.",
                }
            )
        if (
            self.pokazuj_deklaracje_dostepnosci
            == Uczelnia.DeklaracjaDostepnosciChoices.TEKST
            and not self.deklaracja_dostepnosci_tekst
        ):
            raise ValidationError(
                {
                    "pokazuj_deklaracje_dostepnosci": "Wybrano pokazywanie deklaracji dostępności za "
                    "pomocą tekstu w serwisie BPP... ",
                    "deklaracja_dostepnosci_tekst": "... ale nie został on wpisany poprawnie. Proszę skorygować.",
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

    def pbn_client(self, pbn_user_token=None) -> "pbn_api.client.BppPBNClient":
        """
        Zwraca klienta PBNu związanego z TĄ uczelnią (``BppPBNClient``).

        Klient zna ``self`` jako swoją ``uczelnia`` — orchestracja czyta z niej
        flagi zamiast zgadywać ``get_default()`` (kluczowe dla multi-hosted).
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
        return client.BppPBNClient(transport, uczelnia=self)

    @property
    def orcid_base_url(self):
        if self.orcid_sandbox:
            return "https://sandbox.orcid.org"
        return "https://orcid.org"

    @property
    def orcid_api_url(self):
        if self.orcid_sandbox:
            return "https://pub.sandbox.orcid.org/v3.0"
        return "https://pub.orcid.org/v3.0"

    @property
    def orcid_enabled(self):
        return bool(self.orcid_client_id and self.orcid_client_secret)

    def ukryte_statusy(self, dla_funkcji: str) -> list[int]:
        """
        :param dla_funkcji: "sloty", "raporty", "multiwyszukiwarka", "rankingi"
        :return: lista numerów PK obiektów :class:`bpp.models.system.Status_Korekty`
        """
        return self.ukryj_status_korekty_set.filter(**{dla_funkcji: True}).values_list(
            "status_korekty", flat=True
        )

    def _sprawdz_uprawnienie_zalogowany(self, request, ignoruj_grupe):
        """Helper method to check permissions for logged-in users."""
        if request.user.is_anonymous:
            return False

        if request.user.is_superuser:
            return True

        if str(ignoruj_grupe) != "ignoruj_grupe":
            return request.user.groups.filter(name=GR_RAPORTY_WYSWIETLANIE).exists()

        return True

    def sprawdz_uprawnienie(self, attr, request, ignoruj_grupe=None):
        res = getattr(self, f"pokazuj_{attr}")

        if res == OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE:
            return True

        if res == OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM:
            return self._sprawdz_uprawnienie_zalogowany(request, ignoruj_grupe)

        if res == OpcjaWyswietlaniaField.POKAZUJ_GDY_W_ZESPOLE:
            return not request.user.is_anonymous and request.user.is_staff

        if res == OpcjaWyswietlaniaField.POKAZUJ_NIGDY:
            return False

        raise NotImplementedError()

    def autorzy_z_uczelni(self):
        # Zwróc listę wszystkich autorów, którzy są przypisani do
        # nie-obcych jednostek
        from bpp.models.autor import Autor

        return Autor.objects.filter(
            autor_jednostka__jednostka__skupia_pracownikow=True,
            autor_jednostka__jednostka__uczelnia=self,
            autor_jednostka__jednostka__pk__gte=0,
        ).distinct()


class Ukryj_Status_Korekty(models.Model):
    # db_index=False: redundantny względem unique_together
    # (uczelnia, status_korekty) — uczelnia jest wiodącą kolumną tego indeksu.
    uczelnia = models.ForeignKey(Uczelnia, on_delete=models.CASCADE, db_index=False)
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
        help_text="Ukrywa prace w raporcie autora, jednostki, uczelni",
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

    class Meta:
        unique_together = [("uczelnia", "status_korekty")]
        verbose_name = "ustawienie ukrywania statusu korekty"
        verbose_name_plural = "ustawienia ukrywania statusów korekt"

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
