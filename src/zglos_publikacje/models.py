import os
import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from bpp.models import Autor_Dyscyplina, Uczelnia
from bpp.models.abstract import (
    BazaModeluOdpowiedzialnosciAutorow,
    DwaTytuly,
    ModelZDOI,
    ModelZOplataZaPublikacje,
    ModelZRokiem,
)
from bpp.models.autor import _jednostki_uczelni_bez_sztucznych
from bpp.models.soft_delete import (
    BppDzieckoPublikacjiMixin,
    BppSoftDeleteSlownikMixin,
    BppWszystkieWierszeManager,
    BppZywyRodzicManager,
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
    # Kosz jak w reszcie BPP (``docs/deweloper/soft-delete.md``): ``objects``
    # ukrywa kosz, ``global_objects``/``deleted_objects``, ``delete()`` /
    # ``restore()`` bez kaskady pakietu (autorzy i załączniki zostają przy
    # zgłoszeniu i wracają z nim), trigger ``bpp_kosz_straznik`` zamraża
    # zgłoszenie w koszu (migracja ``0031``).
    BppSoftDeleteSlownikMixin,
    ModelZRokiem,
    DwaTytuly,
    ModelZDOI,
    ModelZOplataZaPublikacje,
):
    #: Nic nie blokuje kosza zgłoszenia: autorzy i załączniki znikają razem
    #: z nim (bez własnego kosza), a sesja importu to log — importer i tak
    #: nie domyka zgłoszenia z kosza (``importer_publikacji.zgloszenia``).
    pomijane_relacje_kosza = frozenset(
        {
            "zglos_publikacje.Zgloszenie_Publikacji_Autor.rekord",
            "zglos_publikacje.Zgloszenie_Publikacji_Zalacznik.zgloszenie",
            "importer_publikacji.ImportSession.zgloszenie",
        }
    )

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
        ZAIMPORTOWANY = 6, "zaimportowany przez importer prac"

    status = models.PositiveSmallIntegerField(
        default=Statusy.NOWY, choices=Statusy.choices
    )

    # Audyt domknięcia zgłoszenia importerem prac (FD#443). Denormalizowany
    # na zgłoszeniu — filtrowalny i sortowalny na liście, przeżywa skasowanie
    # sesji importu. Jawne pole czasu, nie ``auto_now``: ``ostatnio_zmieniony``
    # przesuwa każda edycja i nie jest wiarygodnym znacznikiem importu.
    zaimportowano = models.DateTimeField(
        "Zaimportowano", null=True, blank=True, db_index=True
    )
    zaimportowal = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Zaimportował",
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

        # Informacja o opłatach może być opcjonalna, w zależności od ustawień obiektu Uczelnia.
        # Informacja o opłatach może być opcjonalna jeżeli rodzaj zgłaszanej publikacji to "pozostałe"

        # W obydwu przypadkach nie walidujemy (nie uruchamiamy ModelZOplataZaPublikacje.clean)... ale pod jednym
        # warunkiem: pod takim warunkiem, ze NIC nie zostało wpisane jeżeli chodzi o informację o opłatach
        # -- czyli, że zmienna zupelny_brak_informacji_o_oplatach jest False.

        if not hasattr(self, "_uczelnia") or self._uczelnia is None:
            # Multi-hosted: bez przekazanej uczelni NIE zgadujemy przez
            # ``get()`` (crash przy >1 uczelni — Rollbar #400). Gdy nie da
            # się jednoznacznie ustalić, ``_uczelnia_wymaga_oplatach...``
            # obsługuje ``None`` (nie wymusza opłat).
            uczelnia = Uczelnia.objects.get_single_uczelnia_or_none()
        else:
            uczelnia = self._uczelnia

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

    @property
    def czy_zaimportowane(self) -> bool:
        """Czy zgłoszenie zostało domknięte przez importer prac (FD#443)."""
        return self.status == Zgloszenie_Publikacji.Statusy.ZAIMPORTOWANY


class Zgloszenie_Publikacji_Autor(
    # Bez własnego kosza: ``objects`` ukrywa autorów zgłoszeń z kosza,
    # ``all_objects`` widzi wszystko (jak ``*_Autor`` publikacji).
    BppDzieckoPublikacjiMixin,
    BazaModeluOdpowiedzialnosciAutorow,
):
    rekord = models.ForeignKey(Zgloszenie_Publikacji, on_delete=models.CASCADE)

    rok = models.PositiveSmallIntegerField()

    # FD#640: zgłoszenie to dane niezweryfikowane — zapis autora zgłoszenia NIE
    # zakłada mu powiązania z jednostką. Wcześniej wybranie jednostki uczelni
    # przy autorze obcym dopisywało go do niej (stawała się jego „aktualną
    # jednostką”), a przez to autor obcy zaczynał wyglądać jak autor uczelni.
    # Powiązanie powstanie dopiero przy zapisie pracy przez redakcję.
    dodawaj_jednostke_autorowi_przy_zapisie = False

    class Meta:
        verbose_name = "autor w zgłoszeniu publikacji"
        verbose_name_plural = "autorzy w zgłoszeniu publikacji"
        ordering = ("kolejnosc",)

    def __str__(self):
        return f"autor {self.autor} dla zgłoszenia publikacji {self.rekord.tytul_oryginalny}"

    def uczelnia_zgloszenia(self):
        """Uczelnia, do której trafia zgłoszenie.

        Formularz publiczny ustawia ``_uczelnia`` z requestu i ta wartość
        jest wiążąca — także ``None`` (wtedy fail-closed: nikt nie jest
        autorem uczelni), żeby zgłaszający nie mógł wybrać uczelni wyborem
        jednostki. Poza formularzem (kod, testy): uczelnia wybranej
        jednostki, w ostateczności jedyna uczelnia w systemie."""
        if hasattr(self, "_uczelnia"):
            return self._uczelnia
        if self.jednostka_id is not None:
            return self.jednostka.uczelnia
        return Uczelnia.objects.get_single_uczelnia_or_none()

    def autor_jest_autorem_uczelni(self):
        """FD#640: dyscyplinę i jednostkę uczelni określamy wyłącznie
        autorom uczelni (``Autor.jest_autorem_uczelni``)."""
        return self.autor.jest_autorem_uczelni(self.uczelnia_zgloszenia())

    def jednostka_jest_jednostka_uczelni(self):
        """Czy wybrana jednostka to „nasza” jednostka uczelni zgłoszenia —
        ta sama granica, która czyni autora autorem uczelni
        (``AutorQuerySet.autorzy_uczelni``: bez ``Uczelnia.obca_jednostka``
        i jednostek o pk < 0)."""
        uczelnia = self.uczelnia_zgloszenia()
        if self.jednostka_id is None or uczelnia is None:
            return False
        return (
            _jednostki_uczelni_bez_sztucznych(uczelnia)
            .filter(pk=self.jednostka_id)
            .exists()
        )

    def jednostka_dla_redakcji(self):
        """Jednostka ze zgłoszenia do podpowiedzi przy zatwierdzaniu
        (importer, „Dodaj wyd. …” w adminie). FD#640: obcemu autorowi NIE
        podpowiadamy jednostki uczelni (stare zgłoszenia mogły ją mieć) —
        zapis pracy założyłby mu ``Autor_Jednostka`` i „zrobił” z niego
        autora uczelni. Jednostkę obcą albo innej uczelni podpowiadamy."""
        if self.jednostka_id is None:
            return None
        if self.jednostka_jest_jednostka_uczelni() and (
            not self.autor_jest_autorem_uczelni()
        ):
            return None
        return self.jednostka

    def dyscyplina_dla_redakcji(self):
        """Dyscyplina-propozycja ze zgłoszenia do podpowiedzi przy
        zatwierdzaniu — tylko dla autora uczelni (FD#640)."""
        if self.dyscyplina_naukowa_id is None:
            return None
        if not self.autor_jest_autorem_uczelni():
            return None
        return self.dyscyplina_naukowa

    def _waliduj_jednostke_obcego(self):
        """FD#640: autor spoza uczelni nie może dostać w zgłoszeniu jednostki
        uczelni — tylko jednostkę obcą (``Uczelnia.obca_jednostka``). Gdy
        uczelnia nie ma skonfigurowanej obcej jednostki, nie ma czego
        zaproponować w zamian — wtedy nie blokujemy (zgłoszenie i tak nie
        zakłada autorowi powiązania z jednostką, a redakcja przy
        zatwierdzaniu nie dostaje podpowiedzi jednostki uczelni)."""
        uczelnia = self.uczelnia_zgloszenia()
        if uczelnia is None or uczelnia.obca_jednostka_id is None:
            return
        if not self.jednostka_jest_jednostka_uczelni():
            return
        raise ValidationError(
            {
                "jednostka": f"Autor {self.autor} nie jest autorem uczelni "
                "(nie jest ani nie był przypisany do żadnej jej jednostki) — "
                "nie można go przypisać do jednostki uczelni. Wybierz "
                f"jednostkę „{uczelnia.obca_jednostka}”."
            }
        )

    def clean(self):
        if self.autor_id is None:
            raise ValidationError({"autor": "Wybierz jakiegoś autora"})

        if not self.autor_jest_autorem_uczelni():
            # FD#640: autorowi spoza uczelni nie określamy dyscypliny — ani
            # nie wymagamy jej, ani nie przyjmujemy — i nie przypisujemy go
            # do jednostki uczelni.
            if self.dyscyplina_naukowa_id is not None:
                raise ValidationError(
                    {
                        "dyscyplina_naukowa": f"Autor {self.autor} nie jest "
                        "autorem uczelni (nie jest ani nie był przypisany do "
                        "żadnej jej jednostki) — dla autorów spoza uczelni "
                        "nie podaje się dyscypliny. Pozostaw to pole puste."
                    }
                )
            self._waliduj_jednostke_obcego()
            return

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

        if (
            self.dyscyplina_naukowa is not None
            and getattr(self, "dopusc_propozycje_dyscypliny", False)
            and not przypisanie_na_rok_istnieje
        ):
            # FD#620/FD#640: formularz zgłoszenia — autor bez przypisania na
            # rok pracy może dostać dyscyplinę z podpowiadanej listy. To tylko
            # PROPOZYCJA zapisana w zgłoszeniu: ``Autor_Dyscyplina`` zakłada
            # dopiero redakcja przy zatwierdzaniu (importer publikacji).
            from zglos_publikacje.dyscypliny import (
                dyscyplina_z_propozycji,
                ma_przypisanie_na_rok,
            )

            if not ma_przypisanie_na_rok(self.autor_id, self.rok):
                if dyscyplina_z_propozycji(
                    self.autor_id, self.rok, self.dyscyplina_naukowa
                ):
                    return
                raise ValidationError(
                    {
                        "dyscyplina_naukowa": f"Autor {self.autor} nie ma "
                        f"przypisanej dyscypliny na rok {self.rok}. Wybierz "
                        "dyscyplinę z podpowiadanej listy."
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


class ZywyRodzicZalacznikaManager(BppZywyRodzicManager):
    """``objects`` załącznika: ukrywa załączniki zgłoszeń z kosza.

    Osobna klasa z domyślnym ``pole_rodzica``: menedżer relacji odwrotnej
    (``zgloszenie.zalaczniki``) Django tworzy z KLASY domyślnego menedżera,
    bez argumentów — z bazowym ``"rekord"`` filtr byłby błędny.
    """

    def __init__(self, pole_rodzica="zgloszenie"):
        super().__init__(pole_rodzica)


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

    # Bez własnego kosza — znika i wraca razem ze zgłoszeniem.
    objects = ZywyRodzicZalacznikaManager()
    all_objects = BppWszystkieWierszeManager()

    class Meta:
        verbose_name = "załącznik zgłoszenia publikacji"
        verbose_name_plural = "załączniki zgłoszenia publikacji"
        ordering = ("kolejnosc",)

    def __str__(self):
        return f"Załącznik {self.oryginalna_nazwa_pliku} do {self.zgloszenie}"


class Obslugujacy_Zgloszenia_WydzialowManager(models.Manager):
    def emaile_dla_obslugujacego(self, jednostka_root):
        # Faza B (#438) II-2: ``wydzial`` to teraz FK→Jednostka (korzeń
        # drzewa). Jeżeli jest ktokolwiek przypisany do tego korzenia, zwróć
        # jego maile.
        if self.filter(wydzial=jednostka_root).exists():
            ret = []
            for email in (
                self.filter(wydzial=jednostka_root)
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
    # Faza B (#438) II-2: FK→Jednostka (korzeń drzewa, mirror dawnego
    # Wydzial). Nazwa pola zostaje — patrz brief II-2. ``verbose_name`` jest
    # zgodny z etykietą formularza w adminie: przypisanie obejmuje jednostkę
    # razem z jej jednostkami podrzędnymi.
    wydzial = models.ForeignKey(
        "bpp.Jednostka", models.CASCADE, verbose_name="Jednostka (i podrzędne)"
    )

    objects = Obslugujacy_Zgloszenia_WydzialowManager()

    class Meta:
        # Rzeczownik o bierniku równym mianownikowi — admin buduje z tego
        # „Dodaj …" / „Zmień …", więc „przydział" czyta się poprawnie.
        verbose_name = "przydział obsługi zgłoszeń"
        verbose_name_plural = "przydziały obsługi zgłoszeń"
        ordering = ("user__username", "wydzial__nazwa")
        unique_together = [("user", "wydzial")]
