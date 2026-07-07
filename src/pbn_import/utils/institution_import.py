"""Institution import utilities"""

from bpp.models import Jednostka, Jednostka_Rodzic, Wydzial
from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu

from .base import ImportStepBase


def zrob_skrot(s: str) -> str:
    """Create abbreviation from string - extract uppercase and non-alphanumeric"""
    res = ""
    for elem in s:
        if elem.isspace():
            continue
        if not elem.isalnum():
            res += elem
            continue
        if elem.isupper():
            res += elem
    return res


def znajdz_lub_utworz_wydzial_domyslny(uczelnia, nazwa_domyslna="Wydział Domyślny"):
    """Szukaj wydziału zaczynającego się od podanej nazwy (case insensitive).

    Args:
        uczelnia: Obiekt Uczelnia
        nazwa_domyslna: Nazwa do wyszukania (jako prefiks) i utworzenia jeśli nie
            znaleziono

    Returns:
        tuple: (wydzial, created)
    """
    wydzial = Wydzial.objects.filter(
        nazwa__istartswith=nazwa_domyslna,
        uczelnia=uczelnia,
    ).first()
    if wydzial:
        return wydzial, False

    # Multi-hosted: Wydzial.nazwa i .skrot są unique=True GLOBALNIE, a wszystkie
    # uczelnie współdzielą jedną bazę. Nazwę/skrót tworzonego wydziału sufiksujemy
    # skrótem uczelni, żeby druga uczelnia nie wpadła w IntegrityError na "Wydział
    # Domyślny". Ścieżka FIND (istartswith) i tak matchuje legacy rekordy bez
    # sufiksu, więc istniejące instalacje nie widzą churnu.
    return (
        Wydzial.objects.create(
            nazwa=f"{nazwa_domyslna} {uczelnia.skrot}",
            # Wydzial.skrot to varchar(10) — przycinamy, bo uczelnia.skrot bywa
            # dłuższy. Realne skróty uczelni są krótkie, więc forma czytelna
            # przeżywa; przycięcie chroni tylko przed patologicznie długim skrótem.
            skrot=f"{zrob_skrot(nazwa_domyslna)}-{uczelnia.skrot}"[:10],
            uczelnia=uczelnia,
        ),
        True,
    )


def znajdz_lub_utworz_jednostke_domyslna(uczelnia, nazwa_domyslna="Jednostka Domyślna"):
    """Szukaj jednostki zaczynającej się od podanej nazwy (case insensitive).

    Args:
        uczelnia: Obiekt Uczelnia
        nazwa_domyslna: Nazwa do wyszukania (jako prefiks) i utworzenia jeśli nie
            znaleziono

    Returns:
        tuple: (jednostka, created)
    """
    jednostka = Jednostka.objects.filter(
        nazwa__istartswith=nazwa_domyslna,
        uczelnia=uczelnia,
    ).first()
    if jednostka:
        return jednostka, False

    # Multi-hosted: Jednostka.nazwa/.skrot są unique=True GLOBALNIE — sufiksujemy
    # skrótem uczelni, by druga uczelnia nie wpadła w IntegrityError na "Jednostka
    # Domyślna"/"JD". FIND (istartswith) wciąż matchuje legacy rekordy bez sufiksu.
    return (
        Jednostka.objects.create(
            nazwa=f"{nazwa_domyslna} {uczelnia.skrot}",
            # Jednostka.skrot to varchar(128) — przycinamy defensywnie.
            skrot=f"JD-{uczelnia.skrot}"[:128],
            uczelnia=uczelnia,
        ),
        True,
    )


def znajdz_lub_utworz_obca_jednostke(uczelnia, wydzial=None):
    """Zapewnij obcą jednostkę dla uczelni (multi-hosted, idempotentnie).

    Obca jednostka skupia autorów nie będących pracownikami uczelni; procedury
    importujące przypisują do niej osoby bez znanej afiliacji. Kanonicznym źródłem
    prawdy jest FK ``Uczelnia.obca_jednostka`` — NIE zapytanie po
    ``skupia_pracownikow=False`` (ta flaga jest też zdejmowana dla Studentów /
    Doktorantów / Emerytów, więc dawałaby fałszywe trafienia).

    Kolejność (pierwsze trafienie wygrywa):

    1. ``uczelnia.obca_jednostka`` wskazujące jednostkę tej uczelni.
    2. ``Jednostka`` tej uczelni z ``skupia_pracownikow=False`` i nazwą zaczynającą
       się od "Obca jednostka" (matchuje też legacy rekord bez sufiksu skrótu).
    3. utworzenie nowej — nazwa/skrót sufiksowane skrótem uczelni, bo
       ``Jednostka.nazwa``/``skrot`` są ``unique=True`` GLOBALNIE, a w multi-hosted
       wszystkie uczelnie współdzielą jedną bazę (stąd kolizja "Obca jednostka").

    Następnie (zawsze, idempotentnie): podpięcie do wydziału tej uczelni i
    ustawienie ``uczelnia.obca_jednostka``. ``wydzial`` można podać jawnie (krok
    importu podpina obcą jednostkę pod TEN sam wydział co jednostkę domyślną);
    przy ``None`` helper sam ustala/tworzy "Wydział Domyślny" uczelni. Obca
    jednostka i wydział należą do tej samej uczelni, więc trigger
    ``bpp_jednostka_wydzial_sprawdz_uczelnia_id`` przechodzi.

    Zwraca ``(jednostka, created)`` — ``created`` mówi tylko o utworzeniu samej
    Jednostki (krok 3), nie o ubocznym utworzeniu wydziału / linku / FK.
    """
    obca = None
    created = False

    if uczelnia.obca_jednostka_id:
        candidate = uczelnia.obca_jednostka
        if candidate.uczelnia_id == uczelnia.pk:
            obca = candidate

    if obca is None:
        obca = Jednostka.objects.filter(
            uczelnia=uczelnia,
            skupia_pracownikow=False,
            nazwa__istartswith="Obca jednostka",
        ).first()

    if obca is None:
        obca = Jednostka.objects.create(
            nazwa=f"Obca jednostka {uczelnia.skrot}",
            # Jednostka.skrot to varchar(128) — przycinamy defensywnie.
            skrot=f"Obca {uczelnia.skrot}"[:128],
            uczelnia=uczelnia,
            skupia_pracownikow=False,
        )
        created = True

    # Podepnij do wydziału tej uczelni (idempotentnie). Oba obiekty należą do
    # `uczelnia`, więc trigger spójności uczelni przechodzi.
    if wydzial is None:
        wydzial, _ = znajdz_lub_utworz_wydzial_domyslny(uczelnia)
    # Faza B (#438): metryczka wskazuje węzeł-rodzic; LAZY resolve wydział →
    # węzeł-lustro (tworzony w tym miejscu linkowania, jeśli jeszcze go nie ma).
    wezel, _ = znajdz_lub_utworz_wezel_wydzialu(wydzial)
    Jednostka_Rodzic.objects.get_or_create(jednostka=obca, parent=wezel)

    if uczelnia.obca_jednostka_id != obca.pk:
        uczelnia.obca_jednostka = obca
        uczelnia.save(update_fields=["obca_jednostka"])

    return obca, created


def sprawdz_obca_jednostka(uczelnia):
    """Gate-check: czy uczelnia ma poprawnie skonfigurowaną obcą jednostkę.

    Zwraca czytelny opis problemu (str) albo ``None``, gdy wszystko OK. Używane
    PRZED importem PBN (wejście na dashboard importu i submit formularza nowego
    importu), żeby zgłosić problem zanim import wystartuje — zamiast pozwolić mu
    paść w tle na triggerze spójności uczelni.

    Sprawdza (źródło prawdy = FK ``Uczelnia.obca_jednostka``):

    - FK ustawiony,
    - target należy do tej uczelni,
    - ``skupia_pracownikow is False`` (invariant z ``Uczelnia.clean()``),
    - obca jednostka podpięta do wydziału tej samej uczelni (inaczej import
      trafiłby na trigger przy linkowaniu).
    """
    napraw = " Uruchom: python src/manage.py create_obca_jednostka"

    obca = uczelnia.obca_jednostka
    if obca is None:
        return (
            "Uczelnia nie ma ustawionej obcej jednostki "
            "(Uczelnia.obca_jednostka)." + napraw
        )
    if obca.uczelnia_id != uczelnia.pk:
        return "Obca jednostka uczelni należy do innej uczelni." + napraw
    if obca.skupia_pracownikow:
        return (
            "Obca jednostka ma skupia_pracownikow=True — musi być faktycznie "
            "obca." + napraw
        )
    podpieta = Jednostka_Rodzic.objects.filter(
        jednostka=obca,
        parent__uczelnia=uczelnia,
    ).exists()
    if not podpieta:
        return (
            "Obca jednostka nie jest podpięta do żadnego wydziału tej uczelni." + napraw
        )
    return None


def resolve_default_jednostka(session, uczelnia):
    """Ustal domyślną jednostkę dla sesji importu (multi-hosted).

    Kolejność prób — pierwsze trafienie wygrywa:

    1. ``config["default_jednostka_id"]`` — kanoniczny klucz zapisywany przez
       ``InstitutionImporter`` (krok ``institution_setup``) ORAZ przez formularz
       nowego importu (``StartImportView``).
    2. ``config["jednostka_domyslna_id"]`` — klucz historycznie zapisywany przez
       formularz. Zostawiony jako fallback dla sesji utworzonych przed
       ujednoliceniem kluczy (kompatybilność wsteczna).
    3. uczelnia-aware ``znajdz_lub_utworz_jednostke_domyslna(uczelnia)`` —
       find-or-create domyślnej jednostki NALEŻĄCEJ do ``uczelnia``. Zastępuje
       dawny ślepy fallback ``filter(nazwa="Jednostka Domyślna")`` (dokładne
       dopasowanie nazwy, bez filtra uczelni — w multi-hosted potrafił trafić
       w cudzą jednostkę albo zwrócić ``None`` i wywalić import).

    Przy podanej ``uczelnia`` zawsze zwraca Jednostkę (nigdy ``None``).
    """
    config = session.config or {}
    for key in ("default_jednostka_id", "jednostka_domyslna_id"):
        jednostka_id = config.get(key)
        if jednostka_id:
            jednostka = Jednostka.objects.filter(pk=jednostka_id).first()
            if jednostka is not None:
                return jednostka

    jednostka, _ = znajdz_lub_utworz_jednostke_domyslna(uczelnia)
    return jednostka


def resolve_default_jezyk(session):
    """Ustal domyślny język dla sesji importu publikacji.

    Język używany, gdy PBN nie poda języka publikacji (``mainLanguage``) albo
    poda kod nieobecny w słowniku ``Jezyk``. Kolejność — pierwsze trafienie:

    1. ``config["default_jezyk_id"]`` — wybór z formularza nowego importu
       (``StartImportView``).
    2. polski (``get_jezyk_polski``) — deterministyczny default, gdy nic nie
       wybrano albo wybór jest nieaktualny.

    Języki są globalne (nie per-uczelnia), więc — inaczej niż
    ``resolve_default_jednostka`` — resolver nie potrzebuje ``Uczelnia``.
    """
    from bpp.models import Jezyk
    from pbn_integrator.importer.helpers import get_jezyk_polski

    config = session.config or {}
    jezyk_id = config.get("default_jezyk_id")
    if jezyk_id:
        jezyk = Jezyk.objects.filter(pk=jezyk_id).first()
        if jezyk is not None:
            return jezyk

    return get_jezyk_polski()


class InstitutionImporter(ImportStepBase):
    """Setup default institutions and departments"""

    step_name = "institution_setup"
    step_description = "Konfiguracja jednostek i wydziałów"

    def __init__(
        self,
        session,
        client=None,
        uczelnia=None,
        wydzial_domyslny="Wydział Domyślny",
        wydzial_domyslny_skrot=None,
    ):
        super().__init__(session, client, uczelnia=uczelnia)
        self.wydzial_domyslny = wydzial_domyslny
        self.wydzial_domyslny_skrot = wydzial_domyslny_skrot or zrob_skrot(
            wydzial_domyslny
        )

    def run(self, uczelnia=None):
        """Setup default institutions"""
        if uczelnia is None:
            uczelnia = self.uczelnia

        if not uczelnia:
            raise ValueError(
                "Nie znaleziono domyślnej Uczelni. Nie można kontynuować konfiguracji instytucji."
            )

        # Create default department
        self.update_progress(0, 3, "Tworzenie domyślnego wydziału")
        wydzial, created = znajdz_lub_utworz_wydzial_domyslny(
            uczelnia, self.wydzial_domyslny
        )

        if created:
            self.log("info", f"Created default department: {wydzial.nazwa}")
        else:
            self.log("info", f"Using existing department: {wydzial.nazwa}")

        # Create default unit
        self.update_progress(1, 3, "Tworzenie jednostki domyślnej")
        jednostka, created = znajdz_lub_utworz_jednostke_domyslna(uczelnia)

        if created:
            self.log("info", "Created default unit: Jednostka Domyślna")

        # Link unit to department. Faza B (#438): LAZY resolve wydział →
        # węzeł-rodzic (tworzony tu, jeśli jeszcze nie istnieje).
        wezel, _ = znajdz_lub_utworz_wezel_wydzialu(wydzial)
        jw, created = Jednostka_Rodzic.objects.get_or_create(
            jednostka=jednostka, parent=wezel
        )
        if created:
            self.log(
                "info", f"Linked unit {jednostka.nazwa} to department {wydzial.nazwa}"
            )

        # Create foreign unit. Multi-hosted: delegujemy do współdzielonego,
        # idempotentnego helpera (uczelnia-scoped nazwa/skrót, podpięcie do
        # wydziału, ustawienie FK Uczelnia.obca_jednostka). Wcześniejszy
        # get_or_create(nazwa="Obca jednostka") trafiał w cudzą obcą jednostkę
        # (nazwa unique GLOBALNIE) i wywalał trigger spójności uczelni.
        self.update_progress(2, 3, "Tworzenie obcej jednostki")
        obca_jednostka, created = znajdz_lub_utworz_obca_jednostke(
            uczelnia, wydzial=wydzial
        )
        if created:
            self.log("info", f"Created foreign unit: {obca_jednostka.nazwa}")

        self.update_progress(3, 3, "Zakończono konfigurację jednostek")

        # Store in session config
        self.session.config.update(
            {
                "default_jednostka_id": jednostka.id,
                "obca_jednostka_id": obca_jednostka.id,
                "wydzial_id": wydzial.id,
            }
        )
        self.session.save()

        return {
            "wydzial": wydzial,
            "jednostka": jednostka,
            "obca_jednostka": obca_jednostka,
        }
