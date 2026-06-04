import os
import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django_softdelete.models import SoftDeleteModel

from bpp.models import Autor_Dyscyplina, Uczelnia
from bpp.models.abstract import (
    BazaModeluOdpowiedzialnosciAutorow,
    DwaTytuly,
    ModelZDOI,
    ModelZOplataZaPublikacje,
    ModelZRokiem,
)
from bpp.models.wydawca import Wydawca
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from pbn_api.models.publication import Publication as PBN_Publication
from pbn_api.models.publisher import Publisher as PBN_Publisher


def skroc_nazwe_pliku(nazwa: str, max_dlugosc: int = 512) -> str:
    """
    Skraca nazwę pliku jeśli przekracza max_dlugosc.
    Zachowuje rozszerzenie i dodaje '...' przed rozszerzeniem.

    Przykład: 'bardzo_dluga_nazwa_pliku.pdf' -> 'bardzo_dluga_na....pdf'
    """
    if len(nazwa) <= max_dlugosc:
        return nazwa

    # Rozdziel nazwę i rozszerzenie
    base, ext = os.path.splitext(nazwa)

    # Oblicz ile znaków możemy zostawić dla nazwy bazowej
    # Potrzebujemy miejsca na: nazwa_bazowa + '...' + rozszerzenie
    dostepne_znaki = max_dlugosc - len(ext) - 3  # 3 znaki na '...'

    if dostepne_znaki <= 0:
        # Ekstremalny przypadek - samo rozszerzenie jest za długie
        return nazwa[:max_dlugosc]

    return f"{base[:dostepne_znaki]}...{ext}"


def zgloszenie_publikacji_upload_to(instance, filename):
    """
    Generuje unikalną nazwę pliku opartą na UUID.
    Zachowuje rozszerzenie oryginalnego pliku (małymi literami).
    """
    ext = os.path.splitext(filename)[1].lower()
    new_filename = f"{uuid.uuid4()}{ext}"
    return f"protected/zglos_publikacje/{new_filename}"


class Zgloszenie_Publikacji(
    ModelZRokiem, DwaTytuly, ModelZDOI, ModelZOplataZaPublikacje, SoftDeleteModel
):
    email = models.EmailField("E-mail zgłaszającego")

    utworzono = models.DateTimeField(
        "Utworzono", auto_now_add=True, blank=True, null=True
    )
    utworzyl = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.CASCADE,
        verbose_name="Utworzył",
        null=True,
        blank=True,
    )

    ostatnio_zmieniony = models.DateTimeField(auto_now=True, null=True, db_index=True)

    object_id = models.BigIntegerField(null=True, blank=True)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    odpowiednik_w_bpp = GenericForeignKey()

    kod_do_edycji = models.UUIDField(editable=False, unique=True, null=True, blank=True)
    przyczyna_zwrotu = models.TextField(blank=True, default="")

    zgoda_na_publikacje_pelnego_tekstu = models.BooleanField(
        "Zgoda na publikację pełnego tekstu", default=False
    )

    class Statusy(models.IntegerChoices):
        NOWY = 0, "nowe zgłoszenie"
        ZAAKCEPTOWANY = 1, "zaakceptowany - dodany do bazy BPP"
        WYMAGA_ZMIAN = 2, "wymaga zmian - odesłano do zgłaszającego"
        PO_ZMIANACH = 3, "zmiany naniesione przez zgłaszającego"
        ODRZUCONO = 4, "odrzucono w całości"
        SPAM = 5, "spam"

    status = models.PositiveSmallIntegerField(
        default=Statusy.NOWY, choices=Statusy.choices
    )

    class Rodzaje(models.IntegerChoices):
        # Legacy - nie używane w nowym formularzu
        ARTYKUL_LUB_MONOGRAFIA = 1, "artykuł naukowy lub monografia"
        POZOSTALE = 2, "pozostałe rodzaje"
        ROZDZIAL_W_MONOGRAFII = 3, "rozdział w monografii"
        # Nowe wartości używane w nowym formularzu
        MONOGRAFIA = 4, "monografia"
        ARTYKUL = 5, "artykuł naukowy"
        INNE = 6, "inne"

    class FormyDostepu(models.IntegerChoices):
        OTWARTY = 1, "otwarty dostęp"
        OGRANICZONY = 2, "dostęp ograniczony"

    rodzaj_zglaszanej_publikacji = models.PositiveSmallIntegerField(
        "Rodzaj zgłaszanej publikacji",
        choices=Rodzaje.choices,
        help_text=(
            "Dla artykułów naukowych i monografii może być"
            " wymagane wprowadzenie informacji o opłatach"
            " za publikację w ostatnim etapie wypełniania"
            " formularza. "
        ),
    )

    forma_dostepu = models.PositiveSmallIntegerField(
        "Forma dostępu",
        choices=FormyDostepu.choices,
        null=True,
        blank=True,
        help_text="Otwarty dostęp lub dostęp ograniczony",
    )

    strona_www = models.URLField(
        "Dostępna w sieci pod adresem",
        help_text=(
            "Adres URL lub DOI pełnego tekstu pracy. "
            "System automatycznie rozpozna, czy podano DOI"
            " czy URL."
        ),
        max_length=1024,
        blank=True,
        default="",
    )

    # Wydawca -- mogą być wypełnione: FK do bpp.Wydawca,
    # FK do pbn_api.Publisher, lub tekst (freetext)
    wydawca_zgloszenia = models.CharField(
        "Wydawca (tekst)",
        max_length=512,
        blank=True,
        default="",
        help_text="Nazwa wydawcy wpisana przez zgłaszającego",
    )
    wydawca_bpp = models.ForeignKey(
        Wydawca,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Wydawca (BPP)",
        related_name="zgloszenia_publikacji",
    )
    wydawca_pbn = models.ForeignKey(
        PBN_Publisher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Wydawca (PBN)",
        related_name="zgloszenia_publikacji",
    )

    # Wydawnictwo nadrzędne -- dla rozdziałów
    wydawnictwo_nadrzedne_tekst = models.CharField(
        "Wydawnictwo nadrzędne (tekst)",
        max_length=512,
        blank=True,
        default="",
        help_text=(
            "Tytuł monografii, w której jest rozdział"
            " -- wpisany ręcznie przez zgłaszającego"
        ),
    )
    wydawnictwo_nadrzedne_bpp = models.ForeignKey(
        Wydawnictwo_Zwarte,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Wydawnictwo nadrzędne (BPP)",
        related_name="zgloszenia_publikacji",
    )
    wydawnictwo_nadrzedne_pbn = models.ForeignKey(
        PBN_Publication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Wydawnictwo nadrzędne (PBN)",
        related_name="zgloszenia_publikacji",
    )

    plik = models.FileField(
        "Plik załącznika",
        upload_to=zgloszenie_publikacji_upload_to,
        max_length=765,
        help_text="""Jeżeli zgłaszana publikacja nie jest dostępna nigdzie w sieci internet,
        prosimy o dodanie załącznika""",
        blank=True,
        null=True,
    )

    oryginalna_nazwa_pliku = models.CharField(
        "Oryginalna nazwa pliku",
        max_length=512,
        blank=True,
        default="",
        help_text="Oryginalna nazwa pliku przesłana przez użytkownika",
    )

    def _uczelnia_wymaga_oplatach_dla_rodzaju(self, uczelnia):
        """Sprawdź czy uczelnia wymaga informacji o opłatach
        dla danego rodzaju publikacji."""
        if uczelnia is None:
            return False

        mapping = {
            self.Rodzaje.ARTYKUL: uczelnia.wymagaj_oplatach_artykul,
            self.Rodzaje.MONOGRAFIA: uczelnia.wymagaj_oplatach_monografia,
            self.Rodzaje.ROZDZIAL_W_MONOGRAFII: (uczelnia.wymagaj_oplatach_rozdzial),
            self.Rodzaje.INNE: uczelnia.wymagaj_oplatach_inne,
            # Legacy
            self.Rodzaje.ARTYKUL_LUB_MONOGRAFIA: (uczelnia.wymagaj_oplatach_artykul),
            self.Rodzaje.POZOSTALE: uczelnia.wymagaj_oplatach_inne,
        }
        return mapping.get(self.rodzaj_zglaszanej_publikacji, False)

    def clean(self):
        wpisano_informacje_o_oplatach = (
            self.opl_pub_cost_free is not None
            or self.opl_pub_research_potential is not None
            or (self.opl_pub_research_or_development_projects is not None)
            or self.opl_pub_other is not None
            or (self.opl_pub_amount is not None and self.opl_pub_amount != 0)
        )

        uczelnia = Uczelnia.objects.get_default()

        wymaga_oplatach = self._uczelnia_wymaga_oplatach_dla_rodzaju(uczelnia)

        if wymaga_oplatach or wpisano_informacje_o_oplatach:
            ModelZOplataZaPublikacje.clean(self)

    def __str__(self):
        return f"Zgłoszenie od {self.email} utworzone {self.utworzono} dla pracy {self.tytul_oryginalny}"

    class Meta:
        verbose_name = "zgłoszenie publikacji"
        verbose_name_plural = "zgłoszenia publikacji"
        ordering = ("-ostatnio_zmieniony", "tytul_oryginalny")

    def moze_zostac_zwrocony(self):
        return self.status in [
            Zgloszenie_Publikacji.Statusy.NOWY,
            Zgloszenie_Publikacji.Statusy.PO_ZMIANACH,
        ]

    @property
    def pokazuj_przycisk_wydawnictwo_zwarte(self) -> bool:
        return self.rodzaj_zglaszanej_publikacji in (
            self.Rodzaje.MONOGRAFIA,
            self.Rodzaje.ROZDZIAL_W_MONOGRAFII,
        )

    @property
    def pokazuj_przycisk_wydawnictwo_ciagle(self) -> bool:
        return self.rodzaj_zglaszanej_publikacji == self.Rodzaje.ARTYKUL


class Zgloszenie_Publikacji_Autor(BazaModeluOdpowiedzialnosciAutorow):
    rekord = models.ForeignKey(Zgloszenie_Publikacji, on_delete=models.CASCADE)

    rok = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "autor w zgłoszeniu publikacji"
        verbose_name_plural = "autorzy w zgłoszeniu publikacji"
        ordering = ("kolejnosc",)

    def __str__(self):
        return f"autor {self.autor} dla zgłoszenia publikacji {self.rekord.tytul_oryginalny}"

    def clean(self):
        if self.autor_id is None:
            raise ValidationError({"autor": "Wybierz jakiegoś autora"})

        przypisanie_na_rok_istnieje = Autor_Dyscyplina.objects.filter(
            autor=self.autor,
            rok=self.rok,
        ).exists()

        if przypisanie_na_rok_istnieje and self.dyscyplina_naukowa_id is None:
            raise ValidationError(
                {
                    "dyscyplina_naukowa": f"Autor {self.autor} ma przypisaną przynajmniej jedną dyscyplinę na rok "
                    f"{self.rok} i z tego powodu to pole nie może być puste. "
                }
            )

        if self.dyscyplina_naukowa is not None:
            try:
                Autor_Dyscyplina.objects.get(
                    Q(dyscyplina_naukowa=self.dyscyplina_naukowa)
                    | Q(subdyscyplina_naukowa=self.dyscyplina_naukowa),
                    autor=self.autor,
                    rok=self.rok,
                )
            except Autor_Dyscyplina.DoesNotExist as e:
                raise ValidationError(
                    {
                        "dyscyplina_naukowa": f"Autor {self.autor} nie ma przypisania na "
                        f"rok {self.rok} do dyscypliny {self.dyscyplina_naukowa}."
                    }
                ) from e


class Zgloszenie_Publikacji_Zalacznik(models.Model):
    zgloszenie = models.ForeignKey(
        Zgloszenie_Publikacji,
        on_delete=models.CASCADE,
        related_name="zalaczniki",
    )
    plik = models.FileField(
        "Plik załącznika",
        upload_to=zgloszenie_publikacji_upload_to,
        max_length=765,
    )
    oryginalna_nazwa_pliku = models.CharField(
        "Oryginalna nazwa pliku",
        max_length=512,
        blank=True,
        default="",
    )
    kolejnosc = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "załącznik zgłoszenia publikacji"
        verbose_name_plural = "załączniki zgłoszenia publikacji"
        ordering = ("kolejnosc",)

    def __str__(self):
        return f"Załącznik {self.oryginalna_nazwa_pliku} do {self.zgloszenie}"


class Obslugujacy_Zgloszenia_WydzialowManager(models.Manager):
    def emaile_dla_wydzialu(self, wydzial):
        # Jeżeli jest ktokolwiek przypisany do danego wydziału, to zwróć go:
        if self.filter(wydzial=wydzial).exists():
            ret = []
            for email in (
                self.filter(wydzial=wydzial)
                .values_list("user__email", flat=True)
                .distinct()
            ):
                if email != "" and email is not None and email != "brak@email.pl":
                    ret.append(email)

            if ret:
                return ret


class Obslugujacy_Zgloszenia_Wydzialow(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.CASCADE,
        verbose_name="Użytkownik",
        # Auto-indeks FK redundantny: pokrywa go unique_together
        # [user, wydzial] (user jest kolumną wiodącą).
        db_index=False,
    )
    wydzial = models.ForeignKey("bpp.Wydzial", models.CASCADE, verbose_name="Wydział")

    objects = Obslugujacy_Zgloszenia_WydzialowManager()

    class Meta:
        verbose_name = "obsługujący zgłoszenia dla wydziału"
        verbose_name_plural = "obsługujący zgłoszenia dla wydziałów"
        ordering = ("user__username", "wydzial__nazwa")
        unique_together = [("user", "wydzial")]
