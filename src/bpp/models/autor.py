"""
Autorzy
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from autoslug import AutoSlugField
from django.contrib.postgres.search import SearchVectorField as VectorField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import IntegrityError, models, transaction
from django.db.models import CASCADE, SET_NULL, Count, Q, Sum
from django.urls.base import reverse
from django.utils import timezone
from tinymce.models import HTMLField

from bpp import const
from bpp.core import zbieraj_sloty
from bpp.models import LinkDoPBNMixin, ModelZAdnotacjami, ModelZNazwa, NazwaISkrot
from bpp.models.abstract import ModelZPBN_ID
from bpp.util import FulltextSearchMixin, zaloguj_polkniety_wyjatek

logger = logging.getLogger(__name__)


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


class AutorQuerySet(models.QuerySet):
    """Zakresy wyszukiwania autora (spec 2026-07-02).

    Kategorie semantyczne — obowiązują tak samo w single- i multi-host (NIE
    przechodzą przez guard ``tylko_jedna_uczelnia``; to wybór kategorii autora,
    nie izolacja rekordów). ``uczelnia=None`` → fail-closed (pusty queryset).
    Zakres WSZYSCY = zwykłe ``Autor.objects.all()`` (bez metody).
    """

    def aktualnie_zatrudnieni(self, uczelnia):
        """Autorzy aktualnie zatrudnieni w uczelni (realna jednostka)."""
        if uczelnia is None:
            return self.none()
        return self.filter(
            aktualna_jednostka__uczelnia=uczelnia,
            aktualna_jednostka__skupia_pracownikow=True,
        )

    def kiedykolwiek_zwiazani(self, uczelnia):
        """Autorzy związani z uczelnią obecnie LUB historycznie."""
        if uczelnia is None:
            return self.none()
        return self.filter(
            Q(aktualna_jednostka__uczelnia=uczelnia)
            | Q(autor_jednostka__jednostka__uczelnia=uczelnia)
        ).distinct()

    def kiedykolwiek_zatrudnieni(self, uczelnia):
        """Autorzy zatrudnieni w uczelni obecnie LUB historycznie, w REALNEJ
        jednostce (``skupia_pracownikow=True``).

        Różnica względem ``kiedykolwiek_zwiazani``: liczą się TYLKO powiązania
        przez jednostki skupiające pracowników — jednostki obce/techniczne
        (``skupia_pracownikow=False``) są pomijane, także gdy ich uczelnia to
        bieżąca uczelnia (lustrzana jednostka obca o nazwie naszej uczelni NIE
        kwalifikuje autora). Realność sprawdzana per-strona OR: albo aktualna
        jednostka jest realna, albo któraś jednostka historyczna jest realna —
        powiązanie wyłącznie przez jednostkę obcą nie łapie autora.
        """
        if uczelnia is None:
            return self.none()
        return self.filter(
            Q(
                aktualna_jednostka__uczelnia=uczelnia,
                aktualna_jednostka__skupia_pracownikow=True,
            )
            | Q(
                autor_jednostka__jednostka__uczelnia=uczelnia,
                autor_jednostka__jednostka__skupia_pracownikow=True,
            )
        ).distinct()


class AutorManager(FulltextSearchMixin, models.Manager.from_queryset(AutorQuerySet)):
    # Nie włączaj websearch gdy podano minus (podwójne nazwiska z myślnikiem)
    fts_enable_websearch_on_minus_or_quote = False

    def create_from_string(self, text, uczelnia=None):
        """Tworzy rekord autora z ciągu znaków. Używane, gdy dysponujemy
        wpisanym ciągiem znaków z np AutorAutocomplete i chcemy utworzyć
        autora z nazwiskiem i imieniem w poprawny sposób.

        ``uczelnia`` (multi-hosted): uczelnia z requestu wołającego — z niej
        czytamy ``nowy_autor_z_formularza_pokazuj``. Bez niej próbujemy
        JEDYNEJ w systemie (single → ona; 0/>1 → None → ``pokazuj=False``).
        NIE zgadujemy pierwszej-z-brzegu (dawny footgun ``.first()`` na
        managerze Uczelni).
        """

        text = autor_split_string(text)

        # Sprawdź ustawienie w modelu Uczelnia, czy nowy autor ma być widoczny
        from bpp.models.uczelnia import Uczelnia

        if uczelnia is None:
            uczelnia = Uczelnia.objects.get_single_uczelnia_or_none()
        pokazuj = uczelnia.nowy_autor_z_formularza_pokazuj if uczelnia else False

        return self.create(
            **dict(nazwisko=text[0].title(), imiona=text[1].title(), pokazuj=pokazuj)
        )

    def fulltext_annotate(self, search_query, normalization):
        return {self.fts_field + "__rank": Count("wydawnictwo_ciagle")}


class Autor(LinkDoPBNMixin, ModelZAdnotacjami, ModelZPBN_ID):
    url_do_pbn = const.LINK_PBN_DO_AUTORA

    imiona = models.CharField(max_length=512, db_index=True)
    nazwisko = models.CharField(max_length=256, db_index=True)
    tytul = models.ForeignKey(Tytul, CASCADE, blank=True, null=True)
    stopien_sluzbowy = models.ForeignKey(
        "bpp.StopienSluzbowy",
        SET_NULL,
        blank=True,
        null=True,
        verbose_name="stopień służbowy",
    )
    pseudonim = models.CharField(
        max_length=300,
        blank=True,
        default="",
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

    pokazuj_siec_powiazan = models.BooleanField(
        verbose_name="Pokazuj sieć powiązań",
        null=True,
        blank=True,
        default=None,
        help_text="Czy udostępniać sieć współautorstwa dla tego autora. "
        "Puste = użyj ustawienia uczelni; TAK/NIE nadpisuje je dla tego autora.",
    )

    email = models.EmailField("E-mail", max_length=128, blank=True, default="")
    www = models.URLField("WWW", max_length=1024, blank=True, default="")

    plec = models.ForeignKey(Plec, CASCADE, null=True, blank=True)

    urodzony = models.DateField(blank=True, null=True)
    zmarl = models.DateField(blank=True, null=True)

    opis = HTMLField(blank=True, null=True)  # models.TextField(blank=True, null=True)
    pokazuj_opis = models.BooleanField(
        default=False, help_text="""Czy pokazywać tekst z pola 'Opis' na stronie?"""
    )
    poprzednie_nazwiska = models.CharField(
        max_length=1024,
        blank=True,
        default="",
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
        help_text="Open Researcher and Contributor ID, vide http://www.orcid.org",
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

    def czy_pokazywac_siec_powiazan(self, uczelnia):
        """Efektywne ustawienie "pokazuj sieć powiązań" dla tego autora.

        Tri-state per-autor (`pokazuj_siec_powiazan`): TAK/NIE nadpisuje
        ustawienie uczelni, a wartość pusta (None) deleguje do niej. Gdy nie
        ma uczelni — domyślnie pokazuj (True). `uczelnia` podaje wołający
        (np. przez Uczelnia.objects.get_for_request), żeby nie robić ukrytego
        zapytania per autor.
        """
        if self.pokazuj_siec_powiazan is not None:
            return self.pokazuj_siec_powiazan
        if uczelnia is None:
            return True
        return bool(uczelnia.pokazuj_siec_powiazan)

    class Meta:
        verbose_name = "autor"
        verbose_name_plural = "autorzy"
        ordering = ["sort"]
        app_label = "bpp"

    def aktualna_dyscyplina(self, pole="dyscyplina_naukowa"):
        from bpp.models import Autor_Dyscyplina

        try:
            # Spróbuj pobrać wpis Autor_Dyscyplina dla obecnego roku
            ret = Autor_Dyscyplina.objects.get(
                autor=self, rok=timezone.now().date().year
            )
        except Autor_Dyscyplina.DoesNotExist:
            return

        return getattr(ret, pole)

    def aktualna_subdyscyplina(self):
        return self.aktualna_dyscyplina(pole="subdyscyplina_naukowa")

    def __str__(self):
        buf = f"{self.nazwisko} {self.imiona}"

        if self.poprzednie_nazwiska and self.pokazuj_poprzednie_nazwiska:
            buf += f" ({self.poprzednie_nazwiska})"

        if self.tytul is not None:
            buf += ", " + self.tytul.skrot

        if self.pseudonim:
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
            # Wlasny savepoint: ponizszy ``except IntegrityError`` istnial tu
            # od dawna, ale bez atomic() BYL martwy — w PostgreSQL blad
            # integralnosci uniewaznia cala otaczajaca transakcje, wiec
            # "polkniecie" wyjatku zostawialo polamana transakcje. Odkad
            # (autor, jednostka) z pusta data rozpoczecia jest chronione
            # czesciowym UniqueConstraintem, ta sciezka realnie potrafi
            # zlapac wyjatek (wywolanie ``dodaj_jednostke`` bez ``rok``).
            with transaction.atomic():
                ret = Autor_Jednostka.objects.create(
                    autor=self,
                    jednostka=jednostka,
                    funkcja=funkcja,
                    rozpoczal_prace=start_pracy,
                    zakonczyl_prace=koniec_pracy,
                )
        except IntegrityError:
            # Wyscig: rownolegly zapis utworzyl DOKLADNIE ten sam wiersz
            # (autor, jednostka, rozpoczal_prace=start_pracy) w okienku miedzy
            # exists() a create(). Chroni go unique_together (autor, jednostka,
            # rozpoczal_prace) — dla start_pracy=None dodatkowo czesciowy
            # UniqueConstraint (rozpoczal_prace IS NULL). Post-check pyta o
            # dokladnie ta trojke: dla braku roku (start_pracy=None) Django
            # tlumaczy filter(rozpoczal_prace=None) na IS NULL, a dla podanego
            # roku porownuje z konkretna data — wiec jedno wyrazenie obsluguje
            # oba przypadki. Jesli wiersz faktycznie juz istnieje — stan
            # docelowy jest osiagniety, wiec zachowujemy sie jak dotad
            # (return None). Jesli jednak nadal go nie ma, IntegrityError mowil
            # o czyms INNYM (np. zerwany FK) i musi poleciec dalej — inaczej
            # realny blad danych podczas importu znikalby bez sladu jako cichy
            # no-op.
            if not Autor_Jednostka.objects.filter(
                autor=self,
                jednostka=jednostka,
                rozpoczal_prace=start_pracy,
            ).exists():
                raise
            logger.debug(
                "Powiazanie autor=%s jednostka=%s utworzone rownolegle "
                "przez inna transakcje — pomijam.",
                self.pk,
                jednostka.pk,
            )
            return None
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
            Q(jednostka__wydzial=wydzial) | Q(jednostka=wydzial),
            autor=self,
            rozpoczal_prace__lte=start_pracy,
            zakonczyl_prace__gte=koniec_pracy,
        ):
            return True

        # A może ma wpisaną tylko datę początku pracy? W takiej sytuacji
        # stwierdzamy, że autor NADAL tam pracuje, bo nie ma końca, więc:
        if Autor_Jednostka.objects.filter(
            Q(jednostka__wydzial=wydzial) | Q(jednostka=wydzial),
            autor=self,
            rozpoczal_prace__lte=start_pracy,
            zakonczyl_prace=None,
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

        if Autor_Jednostka.objects.filter(
            Q(jednostka__wydzial=wydzial) | Q(jednostka=wydzial), autor=self
        ):
            return True

    def get_full_name(self):
        buf = f"{self.imiona} {self.nazwisko}"
        if self.poprzednie_nazwiska:
            buf += f" ({self.poprzednie_nazwiska})"
        return buf

    def get_full_name_surname_first(self):
        buf = f"{self.nazwisko}"
        if self.poprzednie_nazwiska:
            buf += f" ({self.poprzednie_nazwiska})"
        buf += f" {self.imiona}"
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
        uczelnia_id=None,
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
            uczelnia_id=uczelnia_id,
        )

    @property
    def jest_w_polon(self):
        """Sprawdza czy autor jest w systemie POL-on poprzez sprawdzenie
        czy istnieje rekord OsobaZInstytucji z personId_id równym pbn_uid_id autora."""
        if not self.pbn_uid_id:
            return False

        from pbn_api.models import OsobaZInstytucji

        return OsobaZInstytucji.objects.filter(personId_id=self.pbn_uid_id).exists()


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


class StopienSluzbowy(NazwaISkrot):
    """Stopień służbowy (np. pożarniczy: kpt., bryg.) — słownik na autorze."""

    class Meta:
        verbose_name = "stopień służbowy"
        verbose_name_plural = "stopnie służbowe"
        ordering = ["nazwa"]
        app_label = "bpp"


class StanowiskoDydaktyczne(NazwaISkrot):
    """Stanowisko dydaktyczne (np. adiunkt, profesor) — słownik na
    powiązaniu autor-jednostka."""

    class Meta:
        verbose_name = "stanowisko dydaktyczne"
        verbose_name_plural = "stanowiska dydaktyczne"
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
    def _is_empty_record(self, record):
        """Sprawdza czy rekord jest pusty (obie daty None)"""
        return record.rozpoczal_prace is None and record.zakonczyl_prace is None

    def _can_merge_consecutive(self, previous, current):
        """Sprawdza czy rekordy są kolejnymi dniami i można je połączyć"""
        if previous.zakonczyl_prace is None:
            return False
        return current.rozpoczal_prace == previous.zakonczyl_prace + timedelta(days=1)

    def _merge_with_open_end(self, previous, current, to_remove):
        """Obsługuje łączenie rekordów gdy poprzedni ma otwarty koniec (zakonczyl_prace is None)"""
        if previous.zakonczyl_prace is not None:
            return False

        # Sprawdź specjalny przypadek z importu
        if current.rozpoczal_prace is None and previous.rozpoczal_prace is not None:
            if current.zakonczyl_prace == previous.rozpoczal_prace:
                to_remove.append(current)
                previous.rozpoczal_prace = current.rozpoczal_prace
                previous.save()
            return True

        # Sprawdź czy obecny rekord można włączyć do poprzedniego
        if current.rozpoczal_prace >= previous.rozpoczal_prace:
            to_remove.append(current)
            previous.zakonczyl_prace = current.zakonczyl_prace
            previous.save()
            return True

        return False

    def defragmentuj(self, autor, jednostka):
        poprzedni_rekord = None
        usun = []

        for rec in Autor_Jednostka.objects.filter(
            autor=autor, jednostka=jednostka
        ).order_by("rozpoczal_prace"):
            if poprzedni_rekord is None:
                poprzedni_rekord = rec
                continue

            # Usuń puste rekordy (nie pierwszy)
            if self._is_empty_record(rec):
                usun.append(rec)
                continue

            # Przy imporcie danych z XLS - zamień pusty poprzedni rekord na obecny
            if self._is_empty_record(poprzedni_rekord):
                usun.append(poprzedni_rekord)
                poprzedni_rekord = rec
                continue

            # Obsłuż rekordy z otwartym końcem
            if self._merge_with_open_end(poprzedni_rekord, rec, usun):
                continue

            # Połącz kolejne dni
            if self._can_merge_consecutive(poprzedni_rekord, rec):
                usun.append(rec)
                poprzedni_rekord.zakonczyl_prace = rec.zakonczyl_prace
                poprzedni_rekord.save()
            else:
                poprzedni_rekord = rec

        for aj in usun:
            aj.delete()


class Autor_Jednostka(models.Model):
    """Powiązanie autora z jednostką"""

    # db_index=False: redundantny względem unique_together
    # (autor, jednostka, rozpoczal_prace) — autor jest wiodącą kolumną tego
    # złożonego indeksu, więc auto-indeks FK jest zbędny.
    autor = models.ForeignKey("bpp.Autor", CASCADE, db_index=False)
    jednostka = models.ForeignKey("bpp.Jednostka", CASCADE)
    rozpoczal_prace = models.DateField(
        "Rozpoczął pracę", blank=True, null=True, db_index=True
    )
    zakonczyl_prace = models.DateField(
        "Zakończył pracę", null=True, blank=True, db_index=True
    )
    funkcja = models.ForeignKey("bpp.Funkcja_Autora", CASCADE, null=True, blank=True)
    stanowisko = models.ForeignKey(
        "bpp.StanowiskoDydaktyczne",
        SET_NULL,
        null=True,
        blank=True,
        verbose_name="stanowisko dydaktyczne",
    )

    podstawowe_miejsce_pracy = models.BooleanField(null=True, blank=True, default=None)

    grupa_pracownicza = models.ForeignKey(
        "bpp.Grupa_Pracownicza", SET_NULL, null=True, blank=True
    )
    wymiar_etatu = models.ForeignKey(
        "bpp.Wymiar_Etatu", SET_NULL, null=True, blank=True
    )

    objects = Autor_Jednostka_Manager()

    class Meta:
        verbose_name = "powiązanie autor-jednostka"
        verbose_name_plural = "powiązania autor-jednostka"
        ordering = ["autor__nazwisko", "rozpoczal_prace", "jednostka__nazwa"]
        unique_together = [("autor", "jednostka", "rozpoczal_prace")]
        constraints = [
            # unique_together powyzej deklaruje niezmiennik "jedno powiazanie
            # na trojke", ale w PostgreSQL NULL-e w indeksie unikalnym sa
            # wzajemnie rozroznialne — wiersze z rozpoczal_prace IS NULL nie
            # byly wiec chronione niczym. Tymczasem check-then-create w
            # bpp.models.abstract.authors (save() KAZDEGO autorstwa) tworzy
            # dokladnie takie wiersze. Ten czesciowy indeks domyka luke;
            # dotyczy WYLACZNIE wierszy z NULL-owa data rozpoczecia, wiec
            # wielokrotne (datowane) okresy zatrudnienia sa nadal legalne.
            models.UniqueConstraint(
                fields=("autor", "jednostka"),
                condition=models.Q(rozpoczal_prace__isnull=True),
                name="bpp_autor_jednostka_bez_daty_unikalne",
            ),
        ]
        app_label = "bpp"
        # Niezmiennik "co najwyzej jedno podstawowe miejsce pracy na autora" NIE
        # jest tu egzekwowany przez UniqueConstraint (partial unique index byl
        # natychmiastowy/per-statement i wysadzal legalne przelaczanie domyslnego
        # miejsca pracy w obrebie jednej transakcji). Zamiast tego pilnuje go
        # DEFERRED constraint trigger sprawdzajacy stan KONCOWY przy COMMIT —
        # patrz migracja 0444_deferred_podstawowe_miejsce_pracy.

    def __str__(self):
        try:
            autor_str = str(self.autor) if self.autor_id else "???"
            jednostka_str = self.jednostka.skrot if self.jednostka_id else "???"

            buf = f"{autor_str} ↔ {jednostka_str}"
            if self.funkcja_id and self.funkcja:
                buf = f"{autor_str} ↔ {self.funkcja.nazwa}, {jednostka_str}"
            return buf
        except Exception:
            zaloguj_polkniety_wyjatek(
                f"Budowanie reprezentacji tekstowej Autor_Jednostka (pk={self.pk})",
                logger=logger,
            )
            # Fallback w przypadku jakichkolwiek błędów podczas usuwania
            return f"Autor_Jednostka #{self.pk if self.pk else 'nowy'}"

    def clean(self, exclude=None):
        if self.rozpoczal_prace is not None and self.zakonczyl_prace is not None:
            if self.rozpoczal_prace >= self.zakonczyl_prace:
                raise ValidationError(
                    "Początek pracy późniejszy lub równy, jak zakończenie"
                )

        # UWAGA: świadomie NIE odrzucamy daty zakończenia w przyszłości —
        # zatrudnienie bywa planowane naprzód („pan X pracuje do zaplanowanej
        # daty"). Jest to spójne z triggerem `bpp_autor_ustaw_jednostka_aktualna`,
        # który dla przyszłej daty „do" i tak liczy `aktualny = True`. Dawny
        # zakaz (model + DB-owy CHECK `bez_dat_do_w_przyszlosci`) zdjęty w
        # migracji 0469; w bazie zastąpiony odpornym na czas CHECK
        # `rozpoczal_prace < zakonczyl_prace`.

        # UWAGA: niezmiennik "jedno podstawowe miejsce pracy na autora" NIE jest
        # tu walidowany per-instancja. Eager .exists() (widzacy stan sprzed
        # zapisu) blokowal legalne przelaczanie domyslnego miejsca pracy, bo
        # przejsciowo istnialy dwa rekordy True. Stan KONCOWY pilnuje DEFERRED
        # constraint trigger (przy COMMIT), a przyjazny komunikat dla wielu
        # zaznaczonych naraz daje walidacja formsetu w adminie
        # (Autor_JednostkaInlineFormSet).

    @transaction.atomic
    def ustaw_podstawowe_miejsce_pracy(self):
        """Ustawia to miejsce pracy jako podstawowe i wszystkie pozostałe jako nie-podstawowe"""
        Autor_Jednostka.objects.filter(
            autor=self.autor, podstawowe_miejsce_pracy=True
        ).exclude(pk=self.pk).update(podstawowe_miejsce_pracy=False)
        self.podstawowe_miejsce_pracy = True
        self.save()
