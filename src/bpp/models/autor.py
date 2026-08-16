"""
Autorzy
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta

from autoslug import AutoSlugField
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import (
    DateRangeField,
    RangeBoundary,
    RangeOperators,
)
from django.contrib.postgres.search import SearchVectorField as VectorField
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import RegexValidator
from django.db import IntegrityError, models, transaction
from django.db.models import CASCADE, SET_NULL, Count, Func, Q, Sum
from django.urls.base import reverse
from django.utils import timezone
from django_softdelete.managers import DeletedManager, GlobalManager
from django_softdelete.models import SoftDeleteModel
from django_softdelete.signals import post_restore, post_soft_delete
from tinymce.models import HTMLField

from bpp import const
from bpp.core import zbieraj_sloty
from bpp.models import LinkDoPBNMixin, ModelZAdnotacjami, ModelZNazwa, NazwaISkrot
from bpp.models.abstract import ModelZPBN_ID
from bpp.models.soft_delete import (
    BppPkPrzedHardDeleteMixin,
    BppSoftDeleteQuerySet,
    dopisz_znacznik_zmiany,
    raise_if_has_protected_children,
)
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


class AutorQuerySet(BppSoftDeleteQuerySet):
    """Zakresy wyszukiwania autora (spec 2026-07-02).

    Baza to ``BppSoftDeleteQuerySet`` (faza 04), nie ``models.QuerySet`` —
    stąd bierze się gate blokujący bulk ``update(deleted_at=...)`` oraz
    ``restore()`` z domyślnym ``strict=False``. Bez tego przepięcia husk
    autora dałoby się wyprodukować jednym ``update()``, z pominięciem
    ``save()``, sygnałów, reversion i (od fazy 06) ``SoftDeleteLog``.

    Filtrowanie skasowanych NIE siedzi tutaj, tylko w menedżerze — ten sam
    queryset obsługuje ``objects`` (żywi), ``global_objects`` (wszyscy)
    i ``deleted_objects`` (kosz).

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

    def get_queryset(self):
        """Menedżer publiczny autora UKRYWA husk (faza 04).

        Dopisanie ``SoftDeleteModel`` do bazy klasy ``Autor`` samo z siebie
        NIC by tu nie zmieniło: ``objects = AutorManager()`` nadpisuje
        menedżer pakietu, więc bez tego filtra autor skasowany miękko dalej
        wyskakiwałby w autocomplete, na listach i w wyszukiwarce
        pełnotekstowej — czyli „usunięcie" nie usuwałoby niczego widocznego.
        """
        return super().get_queryset().filter(deleted_at__isnull=True)

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
        """Ranking autora = liczba jego autorstw w wydawnictwach ciągłych.

        Liczymy przez ``wydawnictwo_ciagle_autor`` (through-model), a NIE
        przez M2M ``wydawnictwo_ciagle``, z dwóch powodów:

        1. agregat po relacji to JOIN po SUROWEJ tabeli
           ``bpp_wydawnictwo_ciagle_autor`` — manager soft-delete nie jest
           pytany, więc bez ``filter=Q(…__deleted_at__isnull=True)`` husk
           autora (wszystkie autorstwa skasowane) rankowałby się tak samo
           wysoko, jak przed skasowaniem. Predykat MUSI iść tą samą ścieżką
           relacji co agregat, inaczej Django zrobi drugi, nieskorelowany
           JOIN;
        2. przy okazji odpada drugi JOIN (do ``bpp_wydawnictwo_ciagle``) —
           FK z through-modelu jest NOT NULL, więc kardynalność bez niego
           jest ta sama.
        """
        return {
            self.fts_field + "__rank": Count(
                "wydawnictwo_ciagle_autor",
                filter=Q(wydawnictwo_ciagle_autor__deleted_at__isnull=True),
            )
        }


class AutorGlobalManager(GlobalManager):
    """``Autor.global_objects`` — żywi RAZEM z koszem.

    Zwraca ``AutorQuerySet``, a nie generyczny queryset pakietu, żeby
    ``global_objects.aktualnie_zatrudnieni(...)`` i reszta metod domenowych
    działały tak samo jak na ``objects``. Menedżer globalny bez metod
    domenowych to pułapka: kod przełączony „na kosz" wywala się na
    ``AttributeError`` w miejscu niezwiązanym z soft-delete.
    """

    def get_queryset(self):
        return AutorQuerySet(self.model, using=self._db)


class AutorDeletedManager(DeletedManager):
    """``Autor.deleted_objects`` — wyłącznie kosz. Też z metodami domenowymi."""

    def get_queryset(self):
        return AutorQuerySet(self.model, using=self._db).filter(
            deleted_at__isnull=False
        )


#: Relacje, których istnienie BLOKUJE skasowanie autora (faza 04).
#:
#: Autor bez prac to „husk" — pusta skorupa po scaleniu duplikatów, którą
#: wolno schować do kosza. Autor z jakąkolwiek pracą schować się nie da, bo
#: praca zostałaby bez autora.
#:
#: ``Projekt_Autor`` jest tu mimo że NIE jest modelem soft-delete: to pole
#: ma ``PROTECT`` od dawna, więc już dziś ``autor.delete()`` na uczestniku
#: projektu jest odmawiane. Pominięcie go zamieniłoby istniejącą gwarancję
#: w ciche powodzenie — a scalanie autorów zaczęłoby zostawiać projekty
#: wskazujące na husk.
#:
#: Krotki, nie nazwy relacji odwrotnych: helper liczy przez
#: ``Model.global_objects``, a reverse manager takiego menedżera nie wystawia.
def _relacje_chronione_autora():
    from bpp.models import (
        Patent_Autor,
        Praca_Doktorska,
        Praca_Habilitacyjna,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )
    from bpp.models.projekt import Projekt_Autor

    return [
        (Wydawnictwo_Ciagle_Autor, "autor"),
        (Wydawnictwo_Zwarte_Autor, "autor"),
        (Patent_Autor, "autor"),
        (Praca_Doktorska, "autor"),
        (Praca_Habilitacyjna, "autor"),
        (Projekt_Autor, "autor"),
    ]


class Autor(
    BppPkPrzedHardDeleteMixin,
    LinkDoPBNMixin,
    ModelZAdnotacjami,
    ModelZPBN_ID,
    SoftDeleteModel,
):
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

    # Kolejność ma znaczenie: pierwszy zdefiniowany menedżer jest domyślny.
    # ``_base_manager`` zostaje przy tym zwykłym, NIEFILTRUJĄCYM menedżerem
    # Django (``base_manager_name`` nie jest ustawione) — i tak ma zostać:
    # to przez niego rozwiązują się deskryptory FK, więc ``autorstwo.autor``
    # ma zwracać husk, a nie ``DoesNotExist``.
    objects = AutorManager()
    global_objects = AutorGlobalManager()
    deleted_objects = AutorDeletedManager()

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
        indexes = [
            # Indeks CZĘŚCIOWY (`WHERE deleted_at IS NOT NULL`) — ten sam
            # wzorzec i to samo uzasadnienie, co przy `wc_deleted_at_idx`
            # (faza 02): predykat `deleted_at IS NULL`, którym `objects`
            # filtruje KAŻDE zapytanie o autora, pasuje do ~100% wierszy,
            # więc planner i tak wybierze seq scan — pełny btree byłby
            # wyłącznie kosztem. Selektywne jest zapytanie ODWROTNE (kosz,
            # audyt, `deleted_objects`) i to ono dostaje tu indeks
            # rozmiaru „tyle, ile husków".
            models.Index(
                fields=["deleted_at"],
                name="autor_deleted_at_idx",
                condition=Q(deleted_at__isnull=False),
            ),
        ]

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
            #
            # Sciezka PRZEDZIALOWA (datowana): rownolegly zapis mogl utworzyc
            # okres POKRYWAJACY zadany [start_pracy, koniec_pracy] o INNYM
            # rozpoczal_prace, lamiac ExclusionConstraint
            # 'bpp_autor_jednostka_okresy_bez_nakladan' (a nie unique_together,
            # bo trojka sie rozni). Post-check ponizej pyta o dokladny start,
            # wiec by go NIE zlapal i bledny re-raise poszedlby jako 500. Tak
            # jak czy_juz_istnieje na wejsciu: jesli jakis wiersz pokrywa juz
            # zadany zakres, stan docelowy jest osiagniety — zwracamy go.
            # NULL-owy start pomijamy (predykat przedzialowy i tak nic nie
            # zlapie; ten przypadek obsluguje wylacznie post-check nizej).
            if start_pracy is not None:
                pokrywajacy = Autor_Jednostka.objects.filter(
                    autor=self,
                    jednostka=jednostka,
                    rozpoczal_prace__lte=start_pracy,
                    zakonczyl_prace__gte=koniec_pracy,
                ).first()
                if pokrywajacy is not None:
                    return pokrywajacy
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

        # Soft-delete i restore MUSZĄ podbić ``ostatnio_zmieniony`` — ten sam
        # kontrakt PINNED, co w mixinach faz 01/02 (pełne uzasadnienie
        # w docstringu ``dopisz_znacznik_zmiany``). Bez tego autor zniknięty
        # z bazy byłby nieodpytywalny przez harvest przyrostowy.
        update_fields = kw.get("update_fields")
        if update_fields:
            kw["update_fields"] = dopisz_znacznik_zmiany(self, update_fields)

        ret = super().save(*args, **kw)

        for jednostka in self.jednostki.all():
            self.defragmentuj_jednostke(jednostka)

        return ret

    def delete(self, *args, user=None, reason="", **kwargs):
        """Soft-delete autora — DOZWOLONY wyłącznie dla autora bez prac.

        NIE WOŁAMY ``super().delete()`` — i to jest najważniejsza decyzja
        w tej metodzie. ``SoftDeleteModel.delete()`` pakietu przechodzi po
        WSZYSTKICH relacjach odwrotnych i dla dziecka z ``CASCADE``, które
        samo nie jest modelem soft-delete, woła zwykłe ``delete()``, czyli
        kasuje je TWARDO (``django_softdelete/models.py``, gałąź
        ``on_delete == models.CASCADE``). ``Autor`` ma 27 takich dzieci —
        m.in. ``Autor_Jednostka``, ``Autor_Dyscyplina`` i ``Autor_Absencja``
        — więc delegacja wymazałaby zatrudnienie i dyscypliny osoby, a husk
        przestałby dać się sensownie przywrócić. Faza 02 rozstrzygnęła ten
        sam dylemat identycznie dla publikacji (``BppPublikacjaSoftDelete
        Mixin.delete()``): kaskadę pakietu odrzucamy, ``deleted_at`` piszemy
        sami.

        Konsekwencja jest zamierzona: skasowanie autora NIE rusza jego
        autorstw (spec §1, §10.1). Autor z autorstwami i tak tu nie dojdzie
        — zatrzyma go guard.

        ``user``/``reason`` są tylko przepuszczane; konsumuje je
        ``SoftDeleteLog`` z fazy 06. W sygnaturze muszą być już teraz
        (kontrakt PINNED).
        """
        raise_if_has_protected_children(
            self,
            _relacje_chronione_autora(),
            label="autora",
        )

        txid = kwargs.pop("transaction_id", None) or uuid.uuid4()
        with transaction.atomic():
            self.deleted_at = timezone.now()
            self.restored_at = None
            self.transaction_id = txid
            self.save(update_fields=["deleted_at", "restored_at", "transaction_id"])
            post_soft_delete.send(sender=self.__class__, instance=self)
        return 1, {self._meta.label: 1}

    delete.alters_data = True

    def restore(self, *args, strict: bool = False, user=None, **kwargs):
        """Przywrócenie husku autora.

        ``strict`` przyjmujemy i ignorujemy świadomie — przekazują go ścieżki
        queryset-owe (``global_objects``/``deleted_objects``). Pakietowy
        ``restore()`` ma domyślnie ``strict=True`` i sprawdza KAŻDE pole
        z ``related_model``, także zwykłe FK w przód; ``Autor`` ma FK m.in.
        do ``Tytul``, więc rzuciłby ``SoftDeleteException`` i przywrócenie
        husku byłoby niemożliwe. Nie wołamy go wcale, więc wyjątek nie ma
        jak polecieć (inwariant z docstringu ``bpp/models/soft_delete.py``).

        Nie przywracamy niczego „razem z autorem": jego skasowanie niczego
        nie zabrało, więc nie ma czego wskrzeszać.
        """
        txid = self.transaction_id
        with transaction.atomic():
            self.deleted_at = None
            self.restored_at = timezone.now()
            self.transaction_id = None
            self.save(update_fields=["deleted_at", "restored_at", "transaction_id"])
            post_restore.send(sender=self.__class__, instance=self, transaction_id=txid)

    restore.alters_data = True

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

        # Sprawdź czy obecny rekord można włączyć do poprzedniego. Tak jak przy
        # scalaniu kolejnych dni: kasujemy wchłaniany rekord PRZED domknięciem
        # otwartego końca poprzedniego, żeby chwilowo nie powstały dwa
        # nakładające się okresy łamiące ExclusionConstraint (IMMEDIATE).
        if current.rozpoczal_prace >= previous.rozpoczal_prace:
            nowy_koniec = current.zakonczyl_prace
            current.delete()
            previous.zakonczyl_prace = nowy_koniec
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
                # Wchłaniany rekord kasujemy PRZED rozszerzeniem ocalałego.
                # ExclusionConstraint 'bpp_autor_jednostka_okresy_bez_nakladan'
                # jest IMMEDIATE — gdyby poprzedni_rekord urósł o zakres rec
                # ZANIM rec zniknie, przez moment istniałyby dwa nakładające się
                # okresy tej samej pary (autor, jednostka) i save() poleciałby
                # IntegrityError. Obiekt rec żyje dalej w pamięci, więc jego
                # daty czytamy bez problemu po delete().
                nowy_koniec = rec.zakonczyl_prace
                rec.delete()
                poprzedni_rekord.zakonczyl_prace = nowy_koniec
                poprzedni_rekord.save()
            else:
                poprzedni_rekord = rec

        for aj in usun:
            aj.delete()


class DateRange(Func):
    """``daterange(rozpoczal, zakonczyl, '[]')`` jako wyrażenie ORM.

    Granice DOMKNIETE obustronnie (``'[]'``) — spójnie z semantyką domeny:
    ``dodaj_jednostke`` traktuje obie daty inkluzywnie (``__lte``/``__gte``),
    a ``zakonczyl_prace`` to OSTATNI dzień pracy (np. rok → 31.12). Dzięki temu
    dwa okresy dzielące skrajny dzień (…-12-31 i 12-31-…) liczą się jako
    NAKŁADAJĄCE, a przylegające (…-12-31 i następny 01-01) — już nie. NULL-owy
    ``zakonczyl_prace`` daje zakres otwarty w prawo ``[rozpoczal, )``.
    """

    function = "DATERANGE"
    output_field = DateRangeField()

    def __init__(self, lower, upper):
        super().__init__(
            lower,
            upper,
            RangeBoundary(inclusive_lower=True, inclusive_upper=True),
        )


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
            # Wariant PRZEDZIALOWY (poz. 1.7 audytu). ``dodaj_jednostke`` robi
            # check-then-create z predykatem przedzialowym — dwa rownolegle
            # wywolania tworza NAKLADAJACE sie okresy tego samego autora w tej
            # samej jednostce. Zwykly UniqueConstraint tego nie wyrazi; potrzeba
            # EXCLUDE z btree_gist (operator ``=`` na FK w GiST) + ``&&`` na
            # daterange. Warunek ``rozpoczal_prace IS NOT NULL`` sprawia, ze ten
            # constraint i partial-unique wyzej (IS NULL) IDEALNIE partycjonuja
            # wiersze: zadnego pokrycia ani luki. Wiersze bez daty startu pilnuje
            # tamten (jeden na pare), wiersze z data — ten (brak nakladan).
            ExclusionConstraint(
                name="bpp_autor_jednostka_okresy_bez_nakladan",
                expressions=[
                    ("autor", RangeOperators.EQUAL),
                    ("jednostka", RangeOperators.EQUAL),
                    (
                        DateRange("rozpoczal_prace", "zakonczyl_prace"),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                condition=models.Q(rozpoczal_prace__isnull=False),
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
        komunikat = f"Budowanie reprezentacji tekstowej Autor_Jednostka (pk={self.pk})"
        fallback = f"Autor_Jednostka #{self.pk if self.pk else 'nowy'}"

        try:
            autor_str = str(self.autor) if self.autor_id else "???"
            jednostka_str = self.jednostka.skrot if self.jednostka_id else "???"

            buf = f"{autor_str} ↔ {jednostka_str}"
            if self.funkcja_id and self.funkcja:
                buf = f"{autor_str} ↔ {self.funkcja.nazwa}, {jednostka_str}"
            return buf
        except ObjectDoesNotExist:
            # SPODZIEWANE, nie błąd aplikacji: str() bywa wołany na obiekcie,
            # który wciąż żyje w pamięci, choć jego wiersz — i wiersz po
            # drugiej stronie FK — już zniknął. Najpewniejszy znany nam
            # wywołujący to audyt easyaudit, liczący ``object_repr`` w
            # ``transaction.on_commit`` (ten sam mechanizm opisuje komentarz
            # przy ``Jednostka.__str__``); traceback z Rollbara nie zawiera
            # ramek wywołującego, więc nie zgadujemy dalej.
            #
            # Nie raportujemy tego do Rollbara: hash itemu obejmuje numer
            # linii, więc KAŻDY deploy zakładał nowy item i alert szedł od
            # nowa, mimo że aplikacja zachowywała się poprawnie.
            #
            # Uwaga: logger ``bpp.*`` nie ma dziś własnego handlera w
            # ustawieniach, więc ten ślad ląduje na stderr przez
            # ``logging.lastResort``. Diagnostyka jest zatem słaba — ale to
            # osobny temat (konfiguracja LOGGING), nie powód, by zostawiać
            # fałszywy alarm w Rollbarze.
            zaloguj_polkniety_wyjatek(komunikat, logger=logger, do_rollbar=False)
            return fallback
        except Exception:
            # Cokolwiek innego jest naprawdę nieoczekiwane — raportuj.
            zaloguj_polkniety_wyjatek(komunikat, logger=logger)
            return fallback

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
