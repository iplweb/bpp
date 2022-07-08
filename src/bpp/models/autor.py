"""
Autorzy
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from autoslug import AutoSlugField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import IntegrityError, models, transaction
from django.db.models import CASCADE, SET_NULL, Q, Sum, UniqueConstraint
from django.urls.base import reverse

from django.contrib.postgres.search import SearchVectorField as VectorField

from bpp import const
from bpp.core import zbieraj_sloty
from bpp.models import LinkDoPBNMixin, ModelZAdnotacjami, ModelZNazwa, NazwaISkrot
from bpp.models.abstract import ModelZPBN_ID
from bpp.util import FulltextSearchMixin


class Tytul(NazwaISkrot):
    class Meta:
        verbose_name = "tytuł"
        verbose_name_plural = "tytuły"
        app_label = "bpp"
        ordering = ("skrot",)


class Plec(NazwaISkrot):
    class Meta:
        verbose_name = "płeć"
        verbose_name_plural = "płcie"
        app_label = "bpp"


def autor_split_string(text):
    text = text.strip().replace("\t", " ").replace("\n", " ").replace("\r", " ")
    while text.find("  ") >= 0:
        text = text.replace("  ", " ")

    text = [x.strip() for x in text.split(" ", 1)]
    if len(text) != 2:
        raise ValueError(text)

    if not text[0] or not text[1]:
        raise ValueError(text)

    return text[0], text[1]


class AutorManager(FulltextSearchMixin, models.Manager):
    def create_from_string(self, text):
        """Tworzy rekord autora z ciągu znaków. Używane, gdy dysponujemy
        wpisanym ciągiem znaków z np AutorAutocomplete i chcemy utworzyć
        autora z nazwiskiem i imieniem w poprawny sposób."""

        text = autor_split_string(text)

        return self.create(
            **dict(nazwisko=text[0].title(), imiona=text[1].title(), pokazuj=False)
        )


class Autor(LinkDoPBNMixin, ModelZAdnotacjami, ModelZPBN_ID):
    url_do_pbn = const.LINK_PBN_DO_AUTORA

    imiona = models.CharField(max_length=512, db_index=True)
    nazwisko = models.CharField(max_length=256, db_index=True)
    tytul = models.ForeignKey(Tytul, CASCADE, blank=True, null=True)
    pseudonim = models.CharField(
        max_length=300,
        blank=True,
        null=True,
        help_text="""
    Jeżeli w bazie danych znajdują się autorzy o zbliżonych imionach, nazwiskach i tytułach naukowych,
    skorzystaj z tego pola aby ułatwić ich rozróżnienie. Pseudonim pokaże się w polach wyszukiwania
    oraz na podstronie autora, po nazwisku i tytule naukowym.""",
    )

    aktualna_jednostka = models.ForeignKey(
        "Jednostka", CASCADE, blank=True, null=True, related_name="aktualna_jednostka"
    )
    aktualna_funkcja = models.ForeignKey(
        "Funkcja_Autora",
        CASCADE,
        blank=True,
        null=True,
        related_name="aktualna_funkcja",
    )

    pokazuj = models.BooleanField(
        default=True, help_text="Pokazuj autora na stronach jednostek oraz w rankingu. "
    )

    email = models.EmailField("E-mail", max_length=128, blank=True, null=True)
    www = models.URLField("WWW", max_length=1024, blank=True, null=True)

    plec = models.ForeignKey(Plec, CASCADE, null=True, blank=True)

    urodzony = models.DateField(blank=True, null=True)
    zmarl = models.DateField(blank=True, null=True)
    poprzednie_nazwiska = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="""Jeżeli ten
        autor(-ka) posiada nazwisko panieńskie, pod którym ukazywały
        się publikacje lub zmieniał nazwisko z innych powodów, wpisz tutaj
        wszystkie poprzednie nazwiska, oddzielając je przecinkami.""",
        db_index=True,
    )
    pokazuj_poprzednie_nazwiska = models.BooleanField(
        default=True,
        help_text="Jeżeli odznaczone, poprzednie nazwiska nie będą się wyświetlać na podstronie autora "
        "dla użytkowników niezalogowanych. Użytkownicy zalogowani widzą je zawsze. Wyszukiwanie po poprzednich "
        "nazwiskach będzie nadal możliwe. ",
    )
    orcid = models.CharField(
        "Identyfikator ORCID",
        max_length=19,
        blank=True,
        null=True,
        unique=True,
        help_text="Open Researcher and Contributor ID, " "vide http://www.orcid.org",
        validators=[
            RegexValidator(
                regex=r"^\d\d\d\d-\d\d\d\d-\d\d\d\d-\d\d\d(\d|X)$",
                message="Identyfikator ORCID to 4 grupy po 4 cyfry w każdej, "
                "oddzielone myślnikami",
                code="orcid_invalid_format",
            ),
        ],
        db_index=True,
    )
    orcid_w_pbn = models.BooleanField(
        "ORCID jest w bazie PBN?",
        help_text="""Jeżeli ORCID jest w bazie PBN, to pole powinno być zaznaczone. Zaznaczenie następuje
        automatycznie, przez procedury integrujące bazę danych z PBNem w nocy. Można też zaznaczyć ręcznie.
        Pole wykorzystywane jest gdy autor nie ma odpowiednika w PBN (pole 'PBN UID' rekordu autora jest puste,
        zaś eksport danych powoduje komunikat zwrotny z PBN o nieistniejącym w ich bazie ORCID). W takich sytuacjach
        należy w polu wybrać "Nie". """,
        null=True,
    )

    expertus_id = models.CharField(
        "Identyfikator w bazie Expertus",
        max_length=10,
        null=True,
        blank=True,
        db_index=True,
        unique=True,
    )

    system_kadrowy_id = models.PositiveIntegerField(
        "Identyfikator w systemie kadrowym",
        help_text="""Identyfikator cyfrowy, używany do matchowania autora z danymi z systemu kadrowego Uczelni""",
        null=True,
        blank=True,
        db_index=True,
        unique=True,
    )

    pbn_uid = models.ForeignKey(
        "pbn_api.Scientist", null=True, blank=True, on_delete=SET_NULL
    )

    search = VectorField()

    objects = AutorManager()

    slug = AutoSlugField(populate_from="get_full_name", unique=True, max_length=1024)

    sort = models.TextField()

    jednostki = models.ManyToManyField("bpp.Jednostka", through="Autor_Jednostka")

    def get_absolute_url(self):
        return reverse("bpp:browse_autor", args=(self.slug,))

    class Meta:
        verbose_name = "autor"
        verbose_name_plural = "autorzy"
        ordering = ["sort"]
        app_label = "bpp"

    def __str__(self):
        buf = f"{self.nazwisko} {self.imiona}"

        if self.poprzednie_nazwiska and self.pokazuj_poprzednie_nazwiska:
            buf += " (%s)" % self.poprzednie_nazwiska

        if self.tytul is not None:
            buf += ", " + self.tytul.skrot

        if self.pseudonim is not None:
            buf += " (" + self.pseudonim + ")"

        return buf

    def dodaj_jednostke(
        self, jednostka, rok=None, funkcja=None
    ) -> Autor_Jednostka | None:

        start_pracy = None
        koniec_pracy = None

        if rok is not None:
            start_pracy = date(rok, 1, 1)
            koniec_pracy = date(rok, 12, 31)

        czy_juz_istnieje = Autor_Jednostka.objects.filter(
            autor=self,
            jednostka=jednostka,
            rozpoczal_prace__lte=start_pracy or date(1, 1, 1),
            zakonczyl_prace__gte=koniec_pracy or date(999, 12, 31),
        )

        if czy_juz_istnieje.exists():
            # Ten czas jest już pokryty
            return czy_juz_istnieje.first()

        try:
            ret = Autor_Jednostka.objects.create(
                autor=self,
                jednostka=jednostka,
                funkcja=funkcja,
                rozpoczal_prace=start_pracy,
                zakonczyl_prace=koniec_pracy,
            )
        except IntegrityError:
            return
        self.defragmentuj_jednostke(jednostka)

        return ret

    def defragmentuj_jednostke(self, jednostka):
        Autor_Jednostka.objects.defragmentuj(autor=self, jednostka=jednostka)

    def save(self, *args, **kw):
        self.sort = (self.nazwisko.lower().replace("von ", "") + self.imiona).lower()
        ret = super().save(*args, **kw)

        for jednostka in self.jednostki.all():
            self.defragmentuj_jednostke(jednostka)

        return ret

    def afiliacja_na_rok(self, rok, wydzial, rozszerzona=False):
        """
        Czy autor w danym roku był w danym wydziale?

        :param rok:
        :param wydzial:
        :return: True gdy w danym roku był w danym wydziale
        """
        start_pracy = date(rok, 1, 1)
        koniec_pracy = date(rok, 12, 31)

        if Autor_Jednostka.objects.filter(
            autor=self,
            rozpoczal_prace__lte=start_pracy,
            zakonczyl_prace__gte=koniec_pracy,
            jednostka__wydzial=wydzial,
        ):
            return True

        # A może ma wpisaną tylko datę początku pracy? W takiej sytuacji
        # stwierdzamy, że autor NADAL tam pracuje, bo nie ma końca, więc:
        if Autor_Jednostka.objects.filter(
            autor=self,
            rozpoczal_prace__lte=start_pracy,
            zakonczyl_prace=None,
            jednostka__wydzial=wydzial,
        ):
            return True

        # Jeżeli nie ma takiego rekordu z dopasowaniem z datami, to może jest
        # rekord z dopasowaniem JAKIMKOLWIEK innym?
        # XXX po telefonie p. Małgorzaty Zając dnia 2013-03-25 o godzinie 11:55
        # dostałem informację, że NIE interesują nas tacy autorzy, zatem:

        if not rozszerzona:
            return

        # ... aczkolwiek, sprawdzanie afiliacji do wydziału dla niektórych autorów może
        # być przydatne np przy importowaniu imion i innych rzeczy, więc sprawdźmy w sytuacj
        # gdy jest rozszerzona afiliacja:

        if Autor_Jednostka.objects.filter(autor=self, jednostka__wydzial=wydzial):
            return True

    def get_full_name(self):
        buf = f"{self.imiona} {self.nazwisko}"
        if self.poprzednie_nazwiska:
            buf += " (%s)" % self.poprzednie_nazwiska
        return buf

    def get_full_name_surname_first(self):
        buf = "%s" % self.nazwisko
        if self.poprzednie_nazwiska:
            buf += " (%s)" % self.poprzednie_nazwiska
        buf += " %s" % self.imiona
        return buf

    def prace_w_latach(self):
        """Zwraca lata, w których ten autor opracowywał jakiekolwiek prace."""
        from bpp.models.cache import Rekord

        return (
            Rekord.objects.prace_autora(self)
            .values_list("rok", flat=True)
            .distinct()
            .order_by("rok")
        )

    def liczba_cytowan(self):
        """Zwraca liczbę cytowań prac danego autora"""
        from bpp.models.cache import Rekord

        return (
            Rekord.objects.prace_autora(self)
            .distinct()
            .aggregate(s=Sum("liczba_cytowan"))["s"]
        )

    def liczba_cytowan_afiliowane(self):
        """Zwraca liczbę cytowań prac danego autora tam,
        gdzie została podana afiliacja na jednostkę uczelni"""
        from bpp.models.cache import Rekord

        return (
            Rekord.objects.prace_autora_z_afiliowanych_jednostek(self)
            .distinct()
            .aggregate(s=Sum("liczba_cytowan"))["s"]
        )

    def jednostki_gdzie_ma_publikacje(self):
        from bpp.models import Autorzy, Jednostka

        return Jednostka.objects.filter(
            pk__in=Autorzy.objects.filter(autor_id=self.pk)
            .values("jednostka_id")
            .distinct()
        )

    def zbieraj_sloty(
        self,
        zadany_slot,
        rok_min,
        rok_max,
        minimalny_pk=None,
        dyscyplina_id=None,
        jednostka_id=None,
        akcja=None,
    ):
        return zbieraj_sloty(
            autor_id=self.pk,
            zadany_slot=zadany_slot,
            rok_min=rok_min,
            rok_max=rok_max,
            minimalny_pk=minimalny_pk,
            dyscyplina_id=dyscyplina_id,
            jednostka_id=jednostka_id,
            akcja=akcja,
        )


class Funkcja_Autora(NazwaISkrot):
    """Funkcja autora w jednostce"""

    pokazuj_za_nazwiskiem = models.BooleanField(
        default=False,
        help_text="""Zaznaczenie tego pola sprawi, że ta funkcja
        będzie wyświetlana na stronie autora, za nazwiskiem.""",
    )

    class Meta:
        verbose_name = "funkcja w jednostce"
        verbose_name_plural = "funkcje w jednostkach"
        ordering = ["nazwa"]
        app_label = "bpp"


class Grupa_Pracownicza(ModelZNazwa):
    class Meta:
        verbose_name = "grupa pracownicza"
        verbose_name_plural = "grupy pracownicze"
        ordering = [
            "nazwa",
        ]
        app_label = "bpp"


class Wymiar_Etatu(ModelZNazwa):
    class Meta:
        verbose_name = "wymiar etatu"
        verbose_name_plural = "wymiary etatów"
        ordering = ["nazwa"]
        app_label = "bpp"


class Autor_Jednostka_Manager(models.Manager):
    def defragmentuj(self, autor, jednostka):
        poprzedni_rekord = None
        usun = []
        for rec in Autor_Jednostka.objects.filter(
            autor=autor, jednostka=jednostka
        ).order_by("rozpoczal_prace"):

            if poprzedni_rekord is None:
                poprzedni_rekord = rec
                continue

            if rec.rozpoczal_prace is None and rec.zakonczyl_prace is None:
                # Nic nie wnosi tutaj taki rekord ORAZ nie jest to 'poprzedni'
                # rekord, więc:
                usun.append(rec)
                continue

            # Przy imporcie danych z XLS na dane ze starego systemu - obydwa pola są None
            if (
                poprzedni_rekord.zakonczyl_prace is None
                and poprzedni_rekord.rozpoczal_prace is None
            ):
                usun.append(poprzedni_rekord)
                poprzedni_rekord = rec
                continue

            # Nowy system - przy imporcie danych z XLS do nowego systemu jest sytuacja, gdy autor
            # zaczął kiedyśtam prace ALE jej nie zakończył:
            if poprzedni_rekord.zakonczyl_prace is None:
                if (
                    rec.rozpoczal_prace is None
                    and poprzedni_rekord.rozpoczal_prace is not None
                ):
                    if rec.zakonczyl_prace == poprzedni_rekord.rozpoczal_prace:
                        usun.append(rec)
                        poprzedni_rekord.rozpoczal_prace = rec.rozpoczal_prace
                        poprzedni_rekord.save()

                    continue

                if rec.rozpoczal_prace >= poprzedni_rekord.rozpoczal_prace:
                    usun.append(rec)
                    poprzedni_rekord.zakonczyl_prace = rec.zakonczyl_prace
                    poprzedni_rekord.save()
                    continue

            if rec.rozpoczal_prace == poprzedni_rekord.zakonczyl_prace + timedelta(
                days=1
            ):
                usun.append(rec)
                poprzedni_rekord.zakonczyl_prace = rec.zakonczyl_prace
                poprzedni_rekord.save()
            else:
                poprzedni_rekord = rec

        for aj in usun:
            aj.delete()


class Autor_Jednostka(models.Model):
    """Powiązanie autora z jednostką"""

    autor = models.ForeignKey(Autor, CASCADE)
    jednostka = models.ForeignKey("bpp.Jednostka", CASCADE)
    rozpoczal_prace = models.DateField(
        "Rozpoczął pracę", blank=True, null=True, db_index=True
    )
    zakonczyl_prace = models.DateField(
        "Zakończył pracę", null=True, blank=True, db_index=True
    )
    funkcja = models.ForeignKey(Funkcja_Autora, CASCADE, null=True, blank=True)

    podstawowe_miejsce_pracy = models.BooleanField(null=True, blank=True, default=None)

    grupa_pracownicza = models.ForeignKey(
        Grupa_Pracownicza, SET_NULL, null=True, blank=True
    )
    wymiar_etatu = models.ForeignKey(Wymiar_Etatu, SET_NULL, null=True, blank=True)

    objects = Autor_Jednostka_Manager()

    def clean(self, exclude=None):
        if self.rozpoczal_prace is not None and self.zakonczyl_prace is not None:
            if self.rozpoczal_prace >= self.zakonczyl_prace:
                raise ValidationError(
                    "Początek pracy późniejszy lub równy, jak zakończenie"
                )

        if self.zakonczyl_prace is not None:
            if self.zakonczyl_prace >= datetime.now().date():
                raise ValidationError(
                    "Czas zakończenia pracy w jednostce nie może być taki sam"
                    " lub większy, jak obecna data"
                )

        if self.podstawowe_miejsce_pracy:
            czy_istnieje = Autor_Jednostka.objects.filter(
                autor_id=self.autor_id, podstawowe_miejsce_pracy=True
            )
            if self.pk:
                czy_istnieje = czy_istnieje.exclude(pk=self.pk)

            if czy_istnieje.exists():
                raise ValidationError(
                    "Ten autor ma już określone podstawowe miejsce pracy. Najpierw usuń podstawowe "
                    f"miejsce pracy (ustaw wartość na 'Nie' dla jednostki '{czy_istnieje.first().jednostka.nazwa}'), "
                    f"następnie zapisz rekord autora, następnie ustaw ponownie właściwe podstawowe miejsce pracy "
                    f"(ustaw wartość na 'Tak') i zapisz po raz kolejny. "
                )

    def __str__(self):
        buf = f"{self.autor} ↔ {self.jednostka.skrot}"
        if self.funkcja:
            buf = f"{self.autor} ↔ {self.funkcja.nazwa}, {self.jednostka.skrot}"
        return buf

    @transaction.atomic
    def ustaw_podstawowe_miejsce_pracy(self):
        """Ustawia to miejsce pracy jako podstawowe i wszystkie pozostałe jako nie-podstawowe"""
        Autor_Jednostka.objects.filter(
            autor=self.autor, podstawowe_miejsce_pracy=True
        ).exclude(pk=self.pk).update(podstawowe_miejsce_pracy=False)
        self.podstawowe_miejsce_pracy = True
        self.save()

    class Meta:
        verbose_name = "powiązanie autor-jednostka"
        verbose_name_plural = "powiązania autor-jednostka"
        ordering = ["autor__nazwisko", "rozpoczal_prace", "jednostka__nazwa"]
        unique_together = [("autor", "jednostka", "rozpoczal_prace")]
        app_label = "bpp"
        constraints = [
            UniqueConstraint(
                fields=["autor_id"],
                condition=Q(podstawowe_miejsce_pracy=True),
                name="jedno_podstawowe_miejsce_pracy_na_autora",
            )
        ]
