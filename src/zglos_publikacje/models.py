from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from bpp.models import Autor_Dyscyplina, Uczelnia
from bpp.models.abstract import (
    BazaModeluOdpowiedzialnosciAutorow,
    DwaTytuly,
    ModelZDOI,
    ModelZOplataZaPublikacje,
    ModelZRokiem,
)


class Zgloszenie_Publikacji(
    ModelZRokiem,
    DwaTytuly,
    ModelZDOI,
    ModelZOplataZaPublikacje,
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
    przyczyna_zwrotu = models.TextField(blank=True, null=True)

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
        ARTYKUL_LUB_MONOGRAFIA = 1, "artykuł naukowy lub monografia"
        POZOSTALE = 2, "pozostałe rodzaje"

    rodzaj_zglaszanej_publikacji = models.PositiveSmallIntegerField(
        "Rodzaj zgłaszanej publikacji",
        choices=Rodzaje.choices,
        help_text="Dla artykułów naukowych i monografii może być wymagane wprowadzenie informacji o opłatach"
        " za publikację w ostatnim etapie wypełniania formularza. ",
    )

    strona_www = models.URLField(
        "Dostępna w sieci pod adresem",
        help_text="Pole opcjonalne. Adres URL lokalizacji pełnego tekstu pracy (dostęp otwarty lub nie). "
        "Jeżeli praca posiada numer DOI, wpisz go w postaci adresu URL czyli https://dx.doi.org/[NUMER_DOI]. "
        "Jeżeli praca nie posiada numeru DOI bądź nie jest dostępna w sieci, pozostaw to pole puste. Adres "
        "URL musi być pełny, to znaczy musi zaczynać się od oznaczenia protokołu czyli od ciągu "
        "znaków http:// lub https:// ",
        max_length=1024,
        blank=True,
        null=True,
    )

    plik = models.FileField(
        "Plik załącznika",
        help_text="""Jeżeli zgłaszana publikacja nie jest dostępna nigdzie w sieci internet,
        prosimy o dodanie załącznika""",
        blank=True,
        null=True,
    )

    def clean(self):
        wpisano_informacje_o_oplatach = (
            self.opl_pub_cost_free is not None
            or self.opl_pub_research_potential is not None
            or self.opl_pub_research_or_development_projects is not None
            or self.opl_pub_other is not None
            or (self.opl_pub_amount is not None and self.opl_pub_amount != 0)
        )

        # Informacja o opłatach może być opcjonalna, w zależności od ustawień obiektu Uczelnia.
        # Informacja o opłatach może być opcjonalna jeżeli rodzaj zgłaszanej publikacji to "pozostałe"

        # W obydwu przypadkach nie walidujemy (nie uruchamiamy ModelZOplataZaPublikacje.clean)... ale pod jednym
        # warunkiem: pod takim warunkiem, ze NIC nie zostało wpisane jeżeli chodzi o informację o opłatach
        # -- czyli, że zmienna zupelny_brak_informacji_o_oplatach jest False.

        uczelnia = Uczelnia.objects.get_default()

        if uczelnia is not None and (
            uczelnia.wymagaj_informacji_o_oplatach is True
            or wpisano_informacje_o_oplatach
        ):
            # Administrator systemu wymaga informacji o opłatach dla artykułów i monografii
            if (
                self.rodzaj_zglaszanej_publikacji
                == Zgloszenie_Publikacji.Rodzaje.ARTYKUL_LUB_MONOGRAFIA
            ) or wpisano_informacje_o_oplatach:
                # Użytkownik zgłasza arytkuł lub monografię, uruchamiamy weryfikację
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
            except Autor_Dyscyplina.DoesNotExist:
                raise ValidationError(
                    {
                        "dyscyplina_naukowa": f"Autor {self.autor} nie ma przypisania na "
                        f"rok {self.rok} do dyscypliny {self.dyscyplina_naukowa}."
                    }
                )


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
        settings.AUTH_USER_MODEL, models.CASCADE, verbose_name="Użytkownik"
    )
    wydzial = models.ForeignKey("bpp.Wydzial", models.CASCADE, verbose_name="Wydział")

    objects = Obslugujacy_Zgloszenia_WydzialowManager()

    class Meta:
        verbose_name = "obsługujący zgłoszenia dla wydziału"
        verbose_name_plural = "obsługujący zgłoszenia dla wydziałów"
        ordering = ("user__username", "wydzial__nazwa")
        unique_together = [("user", "wydzial")]
