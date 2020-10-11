# -*- encoding: utf-8 -*-

"""
Klasy abstrakcyjne
"""
import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.db.models import CASCADE, SET_NULL, Q, Sum
from django.urls.base import reverse
from lxml.etree import SubElement

from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import HStoreField
from django.contrib.postgres.search import SearchVectorField as VectorField

from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.timezone import localtime

from bpp.fields import DOIField, YearField
from bpp.models.const import TO_AUTOR
from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina, Dyscyplina_Naukowa

from bpp.models.util import ModelZOpisemBibliograficznym, dodaj_autora
from bpp.util import safe_html

ILOSC_ZNAKOW_NA_ARKUSZ = 40000.0


def get_liczba_arkuszy_wydawniczych(liczba_znakow_wydawniczych):
    return round(liczba_znakow_wydawniczych / ILOSC_ZNAKOW_NA_ARKUSZ, 2)


class ModelZeZnakamiWydawniczymi(models.Model):
    liczba_znakow_wydawniczych = models.IntegerField(
        "Liczba znaków wydawniczych", blank=True, null=True, db_index=True
    )

    def ma_wymiar_wydawniczy(self):
        return self.liczba_znakow_wydawniczych is not None

    def wymiar_wydawniczy_w_arkuszach(self):
        return "%.2f" % get_liczba_arkuszy_wydawniczych(self.liczba_znakow_wydawniczych)

    class Meta:
        abstract = True


class ModelZAdnotacjami(models.Model):
    """Zawiera adnotację  dla danego obiektu, czyli informacje, które
    użytkownik może sobie dowolnie uzupełnić.
    """

    ostatnio_zmieniony = models.DateTimeField(auto_now=True, null=True, db_index=True)

    adnotacje = models.TextField(
        help_text="""Pole do użytku wewnętrznego -
        wpisane tu informacje nie są wyświetlane na stronach WWW dostępnych
        dla użytkowników końcowych.""",
        default="",
        blank=True,
        null=False,
        db_index=True,
    )

    class Meta:
        abstract = True


class ModelZPBN_ID(models.Model):
    """Zawiera informacje o PBN_ID
    """

    pbn_id = models.IntegerField(
        verbose_name="Identyfikator PBN",
        help_text="Identyfikator w systemie Polskiej Bibliografii Naukowej (PBN)",
        null=True,
        blank=True,
        unique=True,
        db_index=True,
    )

    class Meta:
        abstract = True


class ModelZNazwa(models.Model):
    """Nazwany model."""

    nazwa = models.CharField(max_length=512, unique=True)

    def __str__(self):
        return self.nazwa

    class Meta:
        abstract = True
        ordering = ["nazwa"]


class NazwaISkrot(ModelZNazwa):
    """Model z nazwą i ze skrótem"""

    skrot = models.CharField(max_length=128, unique=True)

    class Meta:
        abstract = True


class NazwaWDopelniaczu(models.Model):
    nazwa_dopelniacz_field = models.CharField(
        "Nazwa w dopełniaczu", max_length=512, null=True, blank=True
    )

    class Meta:
        abstract = True

    def nazwa_dopelniacz(self):
        if not hasattr(self, "nazwa"):
            return self.nazwa_dopelniacz_field
        if self.nazwa_dopelniacz_field is None or self.nazwa_dopelniacz_field == "":
            return self.nazwa
        return self.nazwa_dopelniacz_field


class ModelZISSN(models.Model):
    """Model z numerem ISSN oraz E-ISSN"""

    issn = models.CharField("ISSN", max_length=32, blank=True, null=True)
    e_issn = models.CharField("e-ISSN", max_length=32, blank=True, null=True)

    class Meta:
        abstract = True


class ModelZISBN(models.Model):
    """Model z numerem ISBN oraz E-ISBN"""

    isbn = models.CharField("ISBN", max_length=64, blank=True, null=True, db_index=True)
    e_isbn = models.CharField(
        "E-ISBN", max_length=64, blank=True, null=True, db_index=True
    )

    class Meta:
        abstract = True


class ModelZInformacjaZ(models.Model):
    """Model zawierający pole 'Informacja z' - czyli od kogo została
    dostarczona informacja o publikacji (np. od autora, od redakcji)."""

    informacja_z = models.ForeignKey(
        "Zrodlo_Informacji", SET_NULL, null=True, blank=True
    )

    class Meta:
        abstract = True


class DwaTytuly(models.Model):
    """Model zawierający dwa tytuły: tytuł oryginalny pracy oraz tytuł
    przetłumaczony."""

    tytul_oryginalny = models.TextField("Tytuł oryginalny", db_index=True)
    tytul = models.TextField("Tytuł", null=True, blank=True, db_index=True)

    def clean(self):
        self.tytul_oryginalny = safe_html(self.tytul_oryginalny)
        self.tytul = safe_html(self.tytul)

    class Meta:
        abstract = True


class ModelZeStatusem(models.Model):
    """Model zawierający pole statusu korekty, oraz informację, czy
    punktacja została zweryfikowana."""

    status_korekty = models.ForeignKey("Status_Korekty", CASCADE)

    class Meta:
        abstract = True


class ModelZAbsolutnymUrl:
    def get_absolute_url(self):
        return reverse(
            "bpp:browse_praca",
            args=(ContentType.objects.get_for_model(self).pk, self.pk),
        )


class ModelZRokiem(models.Model):
    """Model zawierający pole "Rok" """

    rok = YearField(
        help_text="""Rok uwzględniany przy wyszukiwaniu i raportach
        KBN/MNiSW)""",
        db_index=True,
    )

    class Meta:
        abstract = True


class ModelZWWW(models.Model):
    """Model zawierający adres strony WWW"""

    www = models.URLField(
        "Adres WWW (płatny dostęp)", max_length=1024, blank=True, null=True
    )
    dostep_dnia = models.DateField(
        "Dostęp dnia (płatny dostęp)",
        blank=True,
        null=True,
        help_text="""Data dostępu do strony WWW.""",
    )

    public_www = models.URLField(
        "Adres WWW (wolny dostęp)", max_length=2048, blank=True, null=True
    )
    public_dostep_dnia = models.DateField(
        "Dostęp dnia (wolny dostęp)",
        blank=True,
        null=True,
        help_text="""Data wolnego dostępu do strony WWW.""",
    )

    class Meta:
        abstract = True


class ModelZPubmedID(models.Model):
    pubmed_id = models.BigIntegerField(
        "PubMed ID", blank=True, null=True, help_text="Identyfikator PubMed (PMID)"
    )
    pmc_id = models.CharField("PubMed Central ID", max_length=32, blank=True, null=True)

    class Meta:
        abstract = True


class ModelZDOI(models.Model):
    doi = DOIField("DOI", null=True, blank=True, db_index=True)

    class Meta:
        abstract = True


class ModelRecenzowany(models.Model):
    """Model zawierający informacje o afiliowaniu/recenzowaniu pracy."""

    recenzowana = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True


class ModelPunktowanyBaza(models.Model):
    impact_factor = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal("0.000"), db_index=True
    )
    punkty_kbn = models.DecimalField(
        "Punkty KBN",
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        db_index=True,
    )
    index_copernicus = models.DecimalField(
        "Index Copernicus",
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        db_index=True,
    )
    punktacja_wewnetrzna = models.DecimalField(
        "Punktacja wewnętrzna",
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        db_index=True,
    )
    punktacja_snip = models.DecimalField(
        "Punktacja SNIP",
        max_digits=6,
        decimal_places=3,
        default=Decimal("0.000"),
        db_index=True,
        help_text="""CiteScore SNIP (Source Normalized Impact per Paper)""",
    )

    kc_impact_factor = models.DecimalField(
        "KC: Impact factor",
        max_digits=6,
        decimal_places=3,
        default=None,
        blank=True,
        null=True,
        help_text="""Jeżeli wpiszesz
        wartość w to pole, to zostanie ona użyta w raporcie dla Komisji
        Centralnej w punkcie IXa tego raportu.""",
        db_index=True,
    )
    kc_punkty_kbn = models.DecimalField(
        "KC: Punkty KBN",
        max_digits=6,
        decimal_places=2,
        default=None,
        blank=True,
        null=True,
        help_text="""Jeżeli wpiszesz
        wartość w to pole, to zostanie ona użyta w raporcie dla Komisji
        Centralnej w punkcie IXa i IXb tego raportu.""",
        db_index=True,
    )
    kc_index_copernicus = models.DecimalField(
        "KC: Index Copernicus",
        max_digits=6,
        decimal_places=2,
        default=None,
        blank=True,
        null=True,
        help_text="""Jeżeli wpiszesz
        wartość w to pole, to zostanie ona użyta w raporcie dla Komisji
        Centralnej w punkcie IXa i IXb tego raportu.""",
    )

    class Meta:
        abstract = True


class ModelPunktowany(ModelPunktowanyBaza):
    """Model zawiereający informację o punktacji."""

    weryfikacja_punktacji = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def ma_punktacje(self):
        """Zwraca 'True', jeżeli ten rekord ma jakąkolwiek punktację,
        czyli jeżeli dowolne z jego pól ma wartość nie-zerową"""

        for pole in POLA_PUNKTACJI:
            f = getattr(self, pole)

            if f is None:
                continue

            if type(f) == Decimal:
                if not f.is_zero():
                    return True
            else:
                if f != 0:
                    return True

        return False


POLA_PUNKTACJI = [
    x.name
    for x in ModelPunktowany._meta.fields
    if x.name not in ["weryfikacja_punktacji",]
]


class ModelTypowany(models.Model):
    """Model zawierający typ KBN oraz język."""

    typ_kbn = models.ForeignKey("Typ_KBN", CASCADE, verbose_name="Typ KBN")
    jezyk = models.ForeignKey("Jezyk", CASCADE, verbose_name="Język")
    jezyk_alt = models.ForeignKey(
        "Jezyk",
        SET_NULL,
        verbose_name="Język alternatywny",
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        abstract = True


class BazaModeluOdpowiedzialnosciAutorow(models.Model):
    """Bazowa klasa dla odpowiedzialności autorów (czyli dla przypisania
    autora do czegokolwiek innego). Zawiera wszystkie informacje dla autora,
    czyli: powiązanie ForeignKey, jednostkę, rodzaj zapisu nazwiska, ale
    nie zawiera podstawowej informacji, czyli powiązania"""

    autor = models.ForeignKey("Autor", CASCADE)
    jednostka = models.ForeignKey("Jednostka", CASCADE)
    kolejnosc = models.IntegerField("Kolejność", default=0)
    typ_odpowiedzialnosci = models.ForeignKey(
        "Typ_Odpowiedzialnosci", CASCADE, verbose_name="Typ odpowiedzialności"
    )
    zapisany_jako = models.CharField(max_length=512)
    afiliuje = models.BooleanField(
        default=True,
        help_text="""Afiliuje
    się do jednostki podanej w przypisaniu. Jednostka nie może być obcą. """,
    )
    zatrudniony = models.BooleanField(
        default=False,
        help_text="""Pracownik
    jednostki podanej w przypisaniu""",
    )

    procent = models.DecimalField(
        "Udział w opracowaniu (procent)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    dyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa, on_delete=SET_NULL, null=True, blank=True
    )

    upowaznienie_pbn = models.BooleanField(
        "Upoważnienie PBN",
        default=False,
        help_text='Tik w polu "upoważnienie PBN" oznacza, że dany autor upoważnił '
        "Uczelnię do sprawozdania tej publikacji w ocenie parametrycznej Uczelni",
    )

    class Meta:
        abstract = True
        ordering = ("kolejnosc", "typ_odpowiedzialnosci__skrot")

    def __str__(self):
        return str(self.autor) + " - " + str(self.jednostka.skrot)

    def okresl_dyscypline(self):
        return self.dyscyplina_naukowa

        # Ponizej wykomentowane automatyczne zachowanie, obecne w systemie do wersji 1.0.30-dev2,
        # którego po tej wersji NIE chcemy. Chcemy mieć explicte określoną dyscyplinę naukową.
        # Jednakże, gdyby się okazało, że należy powrócić do jakiejś automatyki w tym temacie,
        # API .okresl_dyscyplinę na ten moment zostaje, jak i resztka z tego kodu, któro
        # zapewniało zachowanie automatyczne:

        # # Jeżeli nie, sprawdź, czy dla danego autora jest określona dyscyplina
        # # na dany rok:
        # try:
        #     ad = Autor_Dyscyplina.objects.get(
        #         autor_id=self.autor_id,
        #         rok=self.rekord.rok,
        #     )
        # except Autor_Dyscyplina.DoesNotExist:
        #     return
        #
        # # Zwróć przypisaną dyscyplinę naukową tylko w sytuacji, gdy jest
        # # określona jedna. Jeżeli są dwie, to nie można określić z automatu
        # if ad.subdyscyplina_naukowa is None:
        #     return ad.dyscyplina_naukowa

    # XXX TODO sprawdzanie, żęby nie było dwóch autorów o tej samej kolejności

    def clean(self):
        # --- Walidacja dyscypliny ---
        # Czy jest określona dyscyplina? Jeżeli tak, to:
        # - rekord nadrzędny musi być określony i mieć jakąś wartość w polu 'Rok'
        # - musi istnieć takie przypisanie autora do dyscypliny dla danego roku
        if self.dyscyplina_naukowa is not None:

            if self.rekord is None:
                raise ValidationError(
                    {
                        "dyscyplina_naukowa": "Określono dyscyplinę naukową, ale brak publikacji nadrzędnej. "
                    }
                )

            if self.rekord is not None and self.rekord.rok is None:
                raise ValidationError(
                    {
                        "dyscyplina_naukowa": "Publikacja nadrzędna nie ma określonego roku."
                    }
                )

            try:
                Autor_Dyscyplina.objects.get(
                    Q(dyscyplina_naukowa=self.dyscyplina_naukowa)
                    | Q(subdyscyplina_naukowa=self.dyscyplina_naukowa),
                    autor=self.autor,
                    rok=self.rekord.rok,
                )
            except Autor_Dyscyplina.DoesNotExist:
                raise ValidationError(
                    {
                        "dyscyplina_naukowa": "Autor nie ma przypisania na dany rok do takiej dyscypliny."
                    }
                )

        # --- Walidacja procentów ---
        # Znajdź inne obiekty z tego rekordu, które są już w bazie danych, ewentualnie
        # utrudniając ich zapisanie w sytuacji, gdyby ilość procent przekroczyła 100:
        inne = self.__class__.objects.filter(rekord=self.rekord)
        if self.pk:
            inne = inne.exclude(pk=self.pk)
        suma = inne.aggregate(Sum("procent"))["procent__sum"] or Decimal("0.00")
        procent = self.procent or Decimal("0.00")

        if suma + procent > Decimal("100.00"):
            raise ValidationError(
                {
                    "procent": "Suma podanych odpowiedzialności przekracza 100. "
                    "Jeżeli edytujesz rekord, spróbuj zrobić to w dwóch etapach. W pierwszym "
                    "zmniejsz punkty procentowe innym, zapisz, w następnym zwiększ punkty "
                    "procentowe i zapisz ponownie. Rekordy nie zostały zapisane. "
                }
            )

        # --- Walidacja afiliacji ---
        # Jeżeli autor afiliuje na jednostkę która jest obca (skupia_pracownikow=False),
        # to zgłoś błąd

        if (
            self.afiliuje
            and self.jednostka_id is not None
            and self.jednostka.skupia_pracownikow is False
            and getattr(settings, "BPP_WALIDUJ_AFILIACJE_AUTOROW", True)
        ):
            raise ValidationError(
                {
                    "afiliuje": "Jeżeli autor opracował tą pracę w obcej jednostce, to pole "
                    "'Afiliuje' nie powinno być zaznaczone."
                }
            )

    def save(self, *args, **kw):
        if "__disable_bmoa_clean_method" in kw:
            del kw["__disable_bmoa_clean_method"]
        else:
            self.clean()
        from bpp.models import Autor_Jednostka

        if (
            getattr(settings, "BPP_DODAWAJ_JEDNOSTKE_PRZY_ZAPISIE_PRACY", True)
            and not Autor_Jednostka.objects.filter(
                autor_id=self.autor_id, jednostka_id=self.jednostka_id
            ).exists()
        ):
            Autor_Jednostka.objects.create(
                autor_id=self.autor_id, jednostka_id=self.jednostka_id,
            )
            # olewamy refresh_from_db i autor.aktualna_jednostka

        return super(BazaModeluOdpowiedzialnosciAutorow, self).save(*args, **kw)


class ModelZeSzczegolami(models.Model):
    """Model zawierający pola: informacje, szczegóły, uwagi, słowa kluczowe."""

    informacje = models.TextField("Informacje", null=True, blank=True, db_index=True)

    szczegoly = models.CharField(
        "Szczegóły", max_length=512, null=True, blank=True, help_text="Np. str. 23-45"
    )

    uwagi = models.TextField(null=True, blank=True, db_index=True)

    slowa_kluczowe = models.TextField("Słowa kluczowe", null=True, blank=True)

    utworzono = models.DateTimeField(
        "Utworzono", auto_now_add=True, blank=True, null=True
    )

    strony = models.CharField(
        max_length=250,
        null=True,
        blank=True,
        help_text="""Jeżeli uzupełnione, to pole będzie eksportowane do
        danych PBN. Jeżeli puste, informacja ta będzie ekstrahowana z
        pola "Szczegóły" w chwili generowania eksportu PBN. Aby uniknąć
        sytuacji, gdy wskutek błędnego wprowadzenia tekstu do pola
        "Szczegóły" informacja ta nie będzie mogła być wyekstrahowana
        z tego pola, kliknij przycisk "Uzupełnij", aby spowodować uzupełnienie
        tego pola na podstawie pola "Szczegóły".
        """,
    )

    tom = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="""Jeżeli uzupełnione, to pole będzie eksportowane do
        danych PBN. Jeżeli puste, informacja ta będzie ekstrahowana z
        pola 'Informacje'. Kliknięcie przycisku "Uzupełnij" powoduje
        również automatyczne wypełnienie tego pola, o ile do formularza
        zostały wprowadzone odpowiednie informacje. """,
    )

    class Meta:
        abstract = True


class ModelZNumeremZeszytu(models.Model):
    nr_zeszytu = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="""Jeżeli uzupełnione, to pole będzie eksportowane do
        danych PBN. Jeżeli puste, informacja ta będzie ekstrahowana z
        pola 'Informacje'. Kliknięcie przycisku "Uzupełnij" powoduje
        również automatyczne wypełnienie tego pola, o ile do formularza
        zostały wprowadzone odpowiednie informacje. """,
    )

    class Meta:
        abstract = True


class ModelZCharakterem(models.Model):
    charakter_formalny = models.ForeignKey(
        "bpp.Charakter_Formalny", CASCADE, verbose_name="Charakter formalny"
    )

    class Meta:
        abstract = True


class ModelPrzeszukiwalny(models.Model):
    """Model zawierający pole pełnotekstowego przeszukiwania
    'search_index'"""

    search_index = VectorField()
    tytul_oryginalny_sort = models.TextField(db_index=True, default="")

    class Meta:
        abstract = True


class ModelZLegacyData(models.Model):
    """Model zawierający informacje zaimportowane z poprzedniego systemu,
    nie mające odpowiednika w nowych danych, jednakże pozostawione na
    rekordzie w taki sposób, aby w razie potrzeby w przyszłości można było
    z nich skorzystać"""

    legacy_data = HStoreField(blank=True, null=True)

    class Meta:
        abstract = True


class RekordBPPBaza(
    ModelZPBN_ID, ModelZOpisemBibliograficznym, ModelPrzeszukiwalny, ModelZLegacyData
):
    """Klasa bazowa wszystkich rekordów (patenty, prace doktorskie,
    habilitacyjne, wydawnictwa zwarte i ciągłe)"""

    class Meta:
        abstract = True


class ModelWybitny(models.Model):
    praca_wybitna = models.BooleanField(default=False)
    uzasadnienie_wybitnosci = models.TextField(
        "Uzasadnienie wybitności", default="", blank=True
    )

    class Meta:
        abstract = True


class Wydawnictwo_Baza(RekordBPPBaza):
    """Klasa bazowa wydawnictw (prace doktorskie, habilitacyjne, wydawnictwa
    ciągłe, zwarte -- bez patentów)."""

    def __str__(self):
        return self.tytul_oryginalny

    class Meta:
        abstract = True


url_validator = URLValidator()


strony_regex = re.compile(
    r"(?P<parametr>s{1,2}\.)\s*"
    r"(?P<poczatek>(\w*\d+|\w+|\d+))"
    r"((-)(?P<koniec>(\w*\d+|\w+|\d+))|)",
    flags=re.IGNORECASE,
)

alt_strony_regex = re.compile(
    r"(?P<poczatek>\d+)(-(?P<koniec>\d+)|)(\s*s.|)", flags=re.IGNORECASE
)

BRAK_PAGINACJI = ("[b. pag.]", "[b.pag.]", "[b. pag]", "[b. bag.]")


def wez_zakres_stron(szczegoly):
    """Funkcja wycinająca informacje o stronach z pola 'Szczegóły'"""
    if not szczegoly:
        return

    for bp in BRAK_PAGINACJI:
        if szczegoly.find(bp) >= 0:
            return "brak"

    def ret(res):
        d = res.groupdict()
        if "poczatek" in d and "koniec" in d and d["koniec"] is not None:
            return "%s-%s" % (d["poczatek"], d["koniec"])

        return "%s" % d["poczatek"]

    res = strony_regex.search(szczegoly)
    if res is not None:
        return ret(res)

    res = alt_strony_regex.search(szczegoly)
    if res is not None:
        return ret(res)


parsed_informacje_regex = re.compile(
    r"(\[online\])?\s*"
    r"(?P<rok>\d\d+)"
    r"(\s*(vol|t|r|bd)\.*\s*\[?(?P<tom>[A-Za-z]?\d+)\]?)?"
    r"(\s*(iss|nr|z|h|no)?\.*\s*(?P<numer>((\d+\w*([\/-]\d*\w*)?)\s*((e-)?(suppl|supl)?\.?(\s*\d+|\w+)?)|((e-)?(suppl|supl)?\.?\s*\d+(\/\d+)?)|(\d+\w*([\/-]\d*\w*)?))|\[?(suppl|supl)\.\]?))?",
    flags=re.IGNORECASE,
)


def parse_informacje_as_dict(
    informacje, parsed_informacje_regex=parsed_informacje_regex
):
    """Wycina z pola informacje informację o tomie lub numerze lub roku.

    Jeśli mamy zapis "Vol.60 supl.3" - to "supl.3";
    jeśli mamy zapis "Vol.61 no.2 suppl.2" - to optymalnie byłoby, żeby do pola numeru trafiało "2 suppl.2",
    jeśli zapis jest "Vol.15 no.5 suppl." - "5 suppl."
    """
    if not informacje:
        return {}

    p = parsed_informacje_regex.search(informacje)
    if p is not None:
        return p.groupdict()
    return {}


def parse_informacje(informacje, key):
    "Wstecznie kompatybilna wersja funkcji parse_informacje_as_dict"
    return parse_informacje_as_dict(informacje).get(key)


class PBNSerializerHelperMixin:
    def eksport_pbn_zakres_stron(self):
        if hasattr(self, "strony"):
            if self.strony:
                return self.strony
        return wez_zakres_stron(self.szczegoly)

    def eksport_pbn_pages(self, toplevel, autorzy_klass=None):
        zakres = self.eksport_pbn_zakres_stron()
        if zakres:
            pages = SubElement(toplevel, "pages")
            pages.text = zakres

    def eksport_pbn_is(self, toplevel, autorzy_klass=None):
        is_text = None

        if self.charakter_formalny.charakter_pbn is not None:
            is_text = self.charakter_formalny.charakter_pbn.identyfikator
        else:
            if self.typ_kbn.charakter_pbn is not None:
                is_text = self.typ_kbn.charakter_pbn.identyfikator

        if is_text:
            _is = SubElement(toplevel, "is")
            _is.text = is_text

    def eksport_pbn_system_identifier(self, toplevel, autorzy_klass=None):
        # W zależności od rodzaju klasy 'self', dodaj cyferkę i kilka zer. W ten sposób
        # symlujemy unikalne ID dla każdej oodzielnej tabeli. Generalnie w systemie bpp
        # Wydawnictwo_Zwarte oraz Wydawnictwo_Ciagle może mieć ten sam numer ID, ponieważ
        # są to różne tabele, śledzone oddzielnie. Aby jednakże w PBN te ID były unikalne,
        # dodajemy przedrostki.
        #
        # Maksymalny int 32-bity: 2147483647
        # sys.maxint na MacOS X:  9223372036854775807
        #
        # ... zatem, do Wydawnictwo_Ciagle dopisujemy dwójkę i tyle zer, żeby zmieściś się w 10 znakach
        # ... tak samo do Wydawnictwo_Zwarte, tylko, ze tam damy czwórkę
        #
        # kilka miliardów publikacji w każdej kategorii "should be enough for anyone"
        #

        # node XML

        system_identifier = SubElement(toplevel, "system-identifier")

        # Jeżeli rekord ma ustalone pole pbn_id, to wyeksportuj to pole

        if self.pbn_id is not None:
            system_identifier.text = str(self.pbn_id)
            return

        # teraz omijamy cyrkularny import za pomocą tego hacka:
        s = str(self.__class__)
        global_id = 3

        if "Wydawnictwo_Zwarte" in s:
            global_id = 4
        elif "Wydawnictwo_Ciagle" in s:
            global_id = 2
        else:
            raise NotImplementedError

        system_identifier.text = "%i%.9i" % (global_id, self.pk)

    def eksport_pbn_title(self, toplevel, autorzy_klass=None):
        title = SubElement(toplevel, "title")
        title.text = self.tytul_oryginalny

    def eksport_pbn_get_nasi_autorzy_iter(self, autorzy_klass):
        # TODO: zrób sprawdzanie jednostki w kontekście ROKU do jakiego wydziału była WÓWCZAS przypisana
        return [
            elem
            for elem in autorzy_klass.objects.filter(
                rekord=self, typ_odpowiedzialnosci__typ_ogolny=TO_AUTOR
            ).select_related("jednostka")
            if elem.jednostka.skupia_pracownikow
        ]

    def eksport_pbn_get_wszyscy_autorzy_iter(self, autorzy_klass):
        return [
            elem
            for elem in autorzy_klass.objects.filter(
                rekord=self, typ_odpowiedzialnosci__typ_ogolny=TO_AUTOR
            )
        ]

    def eksport_pbn_author(self, toplevel, autorzy_klass):
        for autor_wyd in self.eksport_pbn_get_wszyscy_autorzy_iter(autorzy_klass):
            toplevel.append(
                autor_wyd.autor.eksport_pbn_serializuj(
                    affiliated=autor_wyd.afiliuje, employed=autor_wyd.zatrudniony
                )
            )

    def eksport_pbn_get_nasi_autorzy_count(self, autorzy_klass):
        return len(list(self.eksport_pbn_get_nasi_autorzy_iter(autorzy_klass)))

    def eksport_pbn_get_wszyscy_autorzy_count(self, autorzy_klass):
        return len(list(self.eksport_pbn_get_wszyscy_autorzy_iter(autorzy_klass)))

    def eksport_pbn_get_other_contributors_cnt(self, autorzy_klass):
        wszyscy_autorzy = self.eksport_pbn_get_wszyscy_autorzy_count(autorzy_klass)
        nasi_autorzy = self.eksport_pbn_get_nasi_autorzy_count(autorzy_klass)
        return wszyscy_autorzy - nasi_autorzy

    def eksport_pbn_lang(self, toplevel, autorzy_klass=None):
        lang = SubElement(toplevel, "lang")
        lang.text = self.jezyk.get_skrot_dla_pbn()

    def eksport_pbn_keywords(self, toplevel, autorzy_klass=None):
        if self.slowa_kluczowe:
            lang = self.jezyk.get_skrot_dla_pbn()
            keywords = SubElement(toplevel, "keywords", lang=lang)
            for elem in self.slowa_kluczowe.split(","):
                k = SubElement(keywords, "k")
                k.text = elem.strip()

    def eksport_pbn_public_uri(self, toplevel, wydzial=None, autorzy_klass=None):
        def exp_www(www):
            try:
                url_validator(www)
                SubElement(toplevel, "public-uri", href=www)
            except (ValueError, ValidationError):
                pass

        if self.public_www:
            exp_www(self.public_www)

        elif self.www:
            exp_www(self.www)

    def eksport_pbn_open_access(self, toplevel, autorzy_klass=None):
        class NodeMaker:
            @cached_property
            def node(self):
                return SubElement(toplevel, "open-access")

        nm = NodeMaker()

        if self.openaccess_wersja_tekstu is not None:
            text_version = SubElement(nm.node, "open-access-text-version")
            text_version.text = self.openaccess_wersja_tekstu.skrot

        if self.openaccess_licencja is not None:
            license = SubElement(nm.node, "open-access-license")
            license.text = self.openaccess_licencja.skrot

        if self.openaccess_czas_publikacji is not None:
            release_time = SubElement(nm.node, "open-access-release-time")
            release_time.text = self.openaccess_czas_publikacji.skrot

        if self.openaccess_ilosc_miesiecy:
            months = SubElement(nm.node, "open-access-months")
            months.text = str(self.openaccess_ilosc_miesiecy)

        if self.openaccess_tryb_dostepu is not None:
            mode = SubElement(nm.node, "open-access-mode")
            mode.text = self.openaccess_tryb_dostepu.skrot

        # Dostęp dnia (wolny dostęp) idzie jako creation-date
        if self.public_dostep_dnia is not None:
            pdd = SubElement(nm.node, "creation-date")
            pdd.text = str(self.public_dostep_dnia)

    def eksport_pbn_publication_date(self, toplevel, wydzial=None, autorzy_klass=None):
        publication_date = SubElement(toplevel, "publication-date")
        publication_date.text = str(self.rok)

    def eksport_pbn_doi(self, toplevel, autorzy_klass=None):
        if self.doi:
            doi = SubElement(toplevel, "doi")
            doi.text = self.doi

    def eksport_pbn_conference(self, toplevel, autorzy_klass=None):
        if self.konferencja is not None:
            tag = self.konferencja.eksport_pbn_serializuj()
            toplevel.append(tag)

    def eksport_pbn_outstanding(self, toplevel, autorzy_klass=None):
        if self.praca_wybitna:
            outstanding = SubElement(toplevel, "outstanding")
            outstanding.text = "1"

        if self.uzasadnienie_wybitnosci:
            outstanding_description = SubElement(toplevel, "outstanding-description")
            outstanding_description.text = self.uzasadnienie_wybitnosci

    def eksport_pbn_award(self, toplevel, wydzial=None, autorzy_klass=None):
        from bpp.models.nagroda import Nagroda

        for nagroda in Nagroda.objects.filter(
            content_type=ContentType.objects.get_for_model(self), object_id=self.pk
        ):
            tag = nagroda.eksport_pbn_serializuj()
            toplevel.append(tag)

    def eksport_pbn_modification_date(self, toplevel, autorzy_klass=None):
        md = SubElement(toplevel, "modification-date")
        md.text = localtime(self.ostatnio_zmieniony_dla_pbn).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    def eksport_pbn_run_serialization_functions(self, names, toplevel, autorzy_klass):
        for elem in names:
            func = "eksport_pbn_" + elem.replace("-", "_")
            f = getattr(self, func, None)
            if f and hasattr(f, "__call__"):
                f(toplevel, autorzy_klass)

    def eksport_pbn_serializuj(self, toplevel, autorzy_klass):
        self.eksport_pbn_run_serialization_functions(
            [
                "modification-date",
                "title",
                "author",
                "doi",
                "lang",
                "abstract",
                "keywords",
                "outstanding",
                "award",
                "public-uri",
                "publication-date",
                "conference",
                "is",
                "system-identifier",
            ],
            toplevel,
            autorzy_klass,
        )


class ModelZSeria_Wydawnicza(models.Model):
    seria_wydawnicza = models.ForeignKey(
        "bpp.Seria_Wydawnicza", CASCADE, blank=True, null=True
    )

    numer_w_serii = models.CharField(max_length=512, blank=True, null=True)

    class Meta:
        abstract = True


class ModelZKonferencja(models.Model):
    konferencja = models.ForeignKey("bpp.Konferencja", CASCADE, blank=True, null=True)

    class Meta:
        abstract = True


class ModelZOpenAccess(models.Model):
    openaccess_wersja_tekstu = models.ForeignKey(
        "Wersja_Tekstu_OpenAccess",
        CASCADE,
        verbose_name="OpenAccess: wersja tekstu",
        blank=True,
        null=True,
    )

    openaccess_licencja = models.ForeignKey(
        "Licencja_OpenAccess",
        CASCADE,
        verbose_name="OpenAccess: licencja",
        blank=True,
        null=True,
    )

    openaccess_czas_publikacji = models.ForeignKey(
        "Czas_Udostepnienia_OpenAccess",
        CASCADE,
        verbose_name="OpenAccess: czas udostępnienia",
        blank=True,
        null=True,
    )

    openaccess_ilosc_miesiecy = models.PositiveIntegerField(
        "OpenAccess: ilość miesięcy",
        blank=True,
        null=True,
        help_text="Ilość miesięcy jakie upłynęły od momentu opublikowania do momentu udostępnienia",
    )

    class Meta:
        abstract = True


class ModelZAktualizacjaDlaPBN(models.Model):
    #
    # Obiekt subklasujący tę klasę musi subklasować również DirtyFieldsMixin
    #

    ostatnio_zmieniony_dla_pbn = models.DateTimeField(
        "Ostatnio zmieniony (dla PBN)",
        auto_now_add=True,
        help_text="""Moment ostatniej aktualizacji rekordu dla potrzeb PBN. To pole zmieni się automatycznie, gdy
        nastąpi zmiana dowolnego z pól za wyjątkiem bloków pól: „punktacja”, „punktacja komisji centralnej”,
        „adnotacje” oraz pole „status korekty”.""",
    )

    def save(self, *args, **kw):
        if self.pk is not None:
            if self.is_dirty(check_relationship=True):
                flds = self.get_dirty_fields(check_relationship=True)
                flds_keys = list(flds.keys())
                from bpp.admin.helpers import (
                    MODEL_PUNKTOWANY,
                    MODEL_PUNKTOWANY_KOMISJA_CENTRALNA,
                )

                for elem in (
                    MODEL_PUNKTOWANY
                    + MODEL_PUNKTOWANY_KOMISJA_CENTRALNA
                    + (
                        "adnotacje",
                        "ostatnio_zmieniony",
                        # Nie wyrzucaj poniższego pola. Jeżeli jest jedynym
                        # zmienionym polem to zmiana prawdopodobnie idzie z
                        # powodu dodania lub usunięcia autora rekordu
                        # podrzędnego
                        # 'ostatnio_zmieniony_dla_pbn',
                        "opis_bibliograficzny_cache",
                        "search_index",
                        "tytul_oryginalny_sort",
                    )
                ):
                    if elem in flds_keys:
                        flds_keys.remove(elem)

                # Specjalny case: jeżeli jedyne zmienione pole to "informacje"
                # i z pola "informacje" zostało wycięte "W: " na początku, to
                # nie aktualizuj pola
                if (
                    "informacje" in flds_keys
                    and self.informacje is not None
                    and flds["informacje"] is not None
                ):
                    if (
                        "w: " + self.informacje.lower().strip()
                        == flds["informacje"].lower().strip()
                    ):
                        flds_keys.remove("informacje")

                if flds_keys:
                    self.ostatnio_zmieniony_dla_pbn = timezone.now()

        super(ModelZAktualizacjaDlaPBN, self).save(*args, **kw)

    class Meta:
        abstract = True


class ModelZLiczbaCytowan(models.Model):
    liczba_cytowan = models.PositiveIntegerField(
        verbose_name="Liczba cytowań",
        null=True,
        blank=True,
        help_text="""Wartość aktualizowana jest automatycznie raz na kilka dni w przypadku
        skonfigurowania dostępu do API WOS AMR (przez obiekt 'Uczelnia'). Możesz również
        czaktualizować tą wartość ręcznie, naciskając przycisk. """,
    )

    class Meta:
        abstract = True


class ModelZMiejscemPrzechowywania(models.Model):
    numer_odbitki = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        abstract = True


class MaProcentyMixin:
    def ma_procenty(self):
        for autor in self.autorzy_set.all():
            if autor.procent:
                return True
        return False


class NieMaProcentowMixin:
    def ma_procenty(self):
        return False


class DodajAutoraMixin:
    """Funkcja pomocnicza z dodawaniem autora do rekordu, raczej na 99%
    używana tylko i wyłącznie przez testy. Musisz określić self.autor_rekordu_class
    czyli np dla Wydawnictwo_Zwarte ta zmienna powinna przyjąć wartość
    Wydawnictwo_Zwarte_Autor. """

    autor_rekordu_klass = None

    def dodaj_autora(
        self,
        autor,
        jednostka,
        zapisany_jako=None,
        typ_odpowiedzialnosci_skrot="aut.",
        kolejnosc=None,
        dyscyplina_naukowa=None,
        afiliuje=True,
    ):
        """
        :rtype: bpp.models.abstract.BazaModeluOdpowiedzialnosciAutorow
        """
        return dodaj_autora(
            klass=self.autor_rekordu_klass,
            rekord=self,
            autor=autor,
            jednostka=jednostka,
            zapisany_jako=zapisany_jako,
            typ_odpowiedzialnosci_skrot=typ_odpowiedzialnosci_skrot,
            kolejnosc=kolejnosc,
            dyscyplina_naukowa=dyscyplina_naukowa,
            afiliuje=afiliuje,
        )


class AktualizujDatePBNNadrzednegoMixin:
    class Meta:
        abstract = True

    def save(self, *args, **kw):
        if getattr(settings, "ENABLE_DATA_AKT_PBN_UPDATE", True) and (
            self.pk is None or self.is_dirty()
        ):
            # W sytuacji gdy dodajemy nowego autora lub zmieniamy jego dane,
            # rekord "nadrzędny" publikacji powinien mieć zaktualizowany
            # czas ostatniej aktualizacji na potrzeby PBN:
            r = self.rekord
            r.ostatnio_zmieniony_dla_pbn = timezone.now()
            r.save(update_fields=["ostatnio_zmieniony_dla_pbn"])
        super(AktualizujDatePBNNadrzednegoMixin, self).save(*args, **kw)


class ModelOpcjonalnieNieEksportowanyDoAPI(models.Model):
    nie_eksportuj_przez_api = models.BooleanField(
        "Nie eksportuj przez API",
        default=False,
        db_index=True,
        help_text="Jeżeli zaznaczone, to ten rekord nie będzie dostępny przez JSON REST API",
    )

    class Meta:
        abstract = True
