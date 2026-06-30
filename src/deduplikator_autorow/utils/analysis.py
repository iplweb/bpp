"""
Funkcje analizy duplikatów autorów.
"""

import logging

from bpp.models import Autor
from bpp.models.cache import Rekord
from bpp.util import zaloguj_polkniety_wyjatek
from pbn_api.models import OsobaZInstytucji

from .analysis_meta import _name_or_initial_match
from .gender import Gender, plcie_sa_rozne, zgadnij_plec_autora
from .search import szukaj_kopii

logger = logging.getLogger(__name__)

_BRAK_GLOWNEGO_AUTORA = {"error": "Nie można znaleźć głównego autora"}


def _ustal_glownego_autora(osoba_z_instytucji: OsobaZInstytucji):
    """Zwraca głównego autora BPP dla OsobaZInstytucji albo ``None``.

    ``None`` oznacza, że nie udało się ustalić głównego autora (brak
    Scientist, brak rekordu w BPP albo wyjątek przy ustalaniu).
    """
    try:
        scientist = osoba_z_instytucji.personId
        if not scientist:
            return None
        glowny_autor = scientist.rekord_w_bpp
    except Exception:
        zaloguj_polkniety_wyjatek(
            "Ustalanie głównego autora z BPP dla OsobaZInstytucji "
            f"(pk={osoba_z_instytucji.pk}) w analizie duplikatów",
            logger=logger,
            do_rollbar=True,
        )
        return None
    return glowny_autor or None


def _imiona_calkowicie_rozlaczne(glowny_autor: Autor, duplikat: Autor) -> bool:
    """HARD REJECTION: imiona zupełnie rozłączne i to NIE swap.

    Zwraca ``True`` gdy obie strony mają imiona, ale nie ma między nimi
    żadnego punktu wspólnego (pełne imię, 3-prefix, inicjał) ani wykrytej
    pełnej zamiany imię↔nazwisko. 'Jan' nie może być duplikatem 'Agnieszki'
    niezależnie od ORCID, nazwiska czy lat publikacji.
    """
    if not (duplikat.imiona and glowny_autor.imiona):
        return False

    imiona_glowny = glowny_autor.imiona.split()
    imiona_duplikat = duplikat.imiona.split()

    common = sum(
        1
        for ig in imiona_glowny
        for id_ in imiona_duplikat
        if ig.lower() == id_.lower()
    )
    similar = sum(
        1
        for ig in imiona_glowny
        for id_ in imiona_duplikat
        if len(ig) >= 3
        and len(id_) >= 3
        and ig.lower() != id_.lower()
        and (
            ig.lower().startswith(id_.lower()[:3])
            or id_.lower().startswith(ig.lower()[:3])
        )
    )
    initials_g = {ig[0].upper() for ig in imiona_glowny if ig}
    # 'J.' / 'J' / 'Jan' wszystkie dają inicjał na pierwszym znaku
    initials_d = {token[0].upper() for token in imiona_duplikat if token}
    init_count = len(initials_g & initials_d)
    # Inicjały też liczone do swap-detection: 'Jan Kowalski' ↔ 'Kowalski J.'
    # (database swap z inicjałem) musi przejść.
    swap = (
        bool(duplikat.nazwisko)
        and bool(glowny_autor.nazwisko)
        and any(_name_or_initial_match(duplikat.nazwisko, ig) for ig in imiona_glowny)
        and any(
            _name_or_initial_match(glowny_autor.nazwisko, id_)
            for id_ in imiona_duplikat
        )
    )
    return common == 0 and similar == 0 and init_count == 0 and not swap


def _ocena_plci(
    glowny_autor: Autor, plec_glowny: Gender, duplikat: Autor
) -> tuple[int, list[str]]:
    """Jeśli płcie są na pewno różne, to NIE mogą być duplikatami."""
    plec_duplikat = zgadnij_plec_autora(duplikat.imiona, duplikat.plec)
    if not plcie_sa_rozne(plec_glowny, plec_duplikat):
        return 0, []

    plec_glowny_str = "mężczyzna" if plec_glowny == Gender.MALE else "kobieta"
    plec_duplikat_str = "mężczyzna" if plec_duplikat == Gender.MALE else "kobieta"
    # Bardzo silna kara - praktycznie wyklucza duplikat
    return -100, [
        f"RÓŻNA PŁEĆ: główny autor to {plec_glowny_str} "
        f"({glowny_autor.imiona or '?'}), "
        f"duplikat to {plec_duplikat_str} ({duplikat.imiona or '?'}) "
        "- NIE MOGĄ być tą samą osobą"
    ]


def _ocena_liczby_publikacji(
    glowny_autor: Autor, duplikat: Autor
) -> tuple[int, list[str]]:
    """Autorzy z wieloma publikacjami rzadziej są duplikatami."""
    publikacje_duplikat = Rekord.objects.prace_autora(duplikat).count()
    publikacje_glowny = Rekord.objects.prace_autora(glowny_autor).count()

    if publikacje_duplikat > publikacje_glowny and publikacje_duplikat > 3:
        return -30, [
            f"duplikat ma więcej publikacji ({publikacje_duplikat}) niż główny "
            f"({publikacje_glowny}) - prawdopodobnie NIE jest duplikatem"
        ]
    if publikacje_duplikat > 10:
        return -20, [
            f"wiele publikacji ({publikacje_duplikat}) - mało prawdopodobny duplikat"
        ]
    if publikacje_duplikat > 5:
        return -10, [f"średnio publikacji ({publikacje_duplikat}) - możliwy duplikat"]
    # publikacje_duplikat <= 5
    return 10, [f"mało publikacji ({publikacje_duplikat}) - prawdopodobny duplikat"]


def _ocena_tytulu(glowny_autor: Autor, duplikat: Autor) -> tuple[int, list[str]]:
    """Analiza tytułu naukowego."""
    if not duplikat.tytul and glowny_autor.tytul:
        return 15, ["brak tytułu naukowego - prawdopodobny duplikat"]
    if duplikat.tytul and glowny_autor.tytul:
        if duplikat.tytul == glowny_autor.tytul:
            return 10, ["identyczny tytuł naukowy"]
        return -15, ["różny tytuł naukowy - mniej prawdopodobny duplikat"]
    return 0, []


def _ocena_orcid(glowny_autor: Autor, duplikat: Autor) -> tuple[int, list[str]]:
    """Analiza ORCID."""
    if not duplikat.orcid and glowny_autor.orcid:
        return 15, ["brak ORCID - prawdopodobny duplikat"]
    if duplikat.orcid and glowny_autor.orcid:
        if duplikat.orcid == glowny_autor.orcid:
            return 50, ["identyczny ORCID - to ten sam autor"]
        return -50, ["różny ORCID - to różni autorzy"]
    return 0, []


def _ocena_nazwiska(glowny_autor: Autor, duplikat: Autor) -> tuple[int, list[str]]:
    """Analiza nazwiska."""
    if not (duplikat.nazwisko and glowny_autor.nazwisko):
        return 0, []
    dup = duplikat.nazwisko.lower()
    glw = glowny_autor.nazwisko.lower()
    if dup == glw:
        return 40, ["identyczne nazwisko"]
    if glw in dup or dup in glw:
        return 30, ["podobne nazwisko"]
    return 0, []


def _ocena_zamiany_imienia_nazwiska(
    glowny_autor: Autor, duplikat: Autor
) -> tuple[int, list[str]]:
    """Analiza zamiany imienia z nazwiskiem (name-surname swap detection).

    Punktuje tylko pełną zamianę (OBE strony muszą się zgadzać) - dokładnie
    LUB jako inicjał (np. 'J.' do 'Jan'). Częściowa zamiana nie istnieje.
    """
    if not (
        duplikat.nazwisko
        and duplikat.imiona
        and glowny_autor.nazwisko
        and glowny_autor.imiona
    ):
        return 0, []

    imiona_glowny = glowny_autor.imiona.split()
    imiona_duplikat = duplikat.imiona.split()

    zamiana_nazwisko_duplikat = any(
        _name_or_initial_match(duplikat.nazwisko, imie_g) for imie_g in imiona_glowny
    )
    zamiana_nazwisko_glowny = any(
        _name_or_initial_match(glowny_autor.nazwisko, imie_d)
        for imie_d in imiona_duplikat
    )

    if zamiana_nazwisko_duplikat and zamiana_nazwisko_glowny:
        return 50, [
            f"wykryto pełną zamianę imienia z nazwiskiem "
            f"('{glowny_autor.nazwisko} {glowny_autor.imiona}' ↔ "
            f"'{duplikat.nazwisko} {duplikat.imiona}')"
        ]
    return 0, []


def _inicjaly_duplikatu(imiona: str) -> list[str]:
    """Wyodrębnia inicjały z duplikatu (obsługa 'J.', 'J. M.', 'Jan M.' itp.)."""
    inicjaly = []
    for token in imiona.split():
        if len(token) == 1 or (len(token) == 2 and token.endswith(".")):
            # To jest inicjał
            inicjaly.append(token[0].upper())
        elif len(token) > 1 and not token.endswith("."):
            # To jest pełne imię
            inicjaly.append(token[0].upper())
    return inicjaly


def _ocena_imion(glowny_autor: Autor, duplikat: Autor) -> tuple[int, list[str]]:
    """Analiza imion: dokładne dopasowania, podobne imiona, inicjały."""
    if not glowny_autor.imiona:
        return 0, []
    if not duplikat.imiona:
        return 10, ["brak imion w duplikacie"]

    imiona_glowny = glowny_autor.imiona.split()
    imiona_duplikat = duplikat.imiona.split()

    pewnosc = 0
    powody: list[str] = []

    dokladne_dopasowania = sum(
        1
        for imie_g in imiona_glowny
        for imie_d in imiona_duplikat
        if imie_g.lower() == imie_d.lower()
    )
    if dokladne_dopasowania > 0:
        powody.append(f"wspólne imię ({dokladne_dopasowania})")
        pewnosc += 30 * dokladne_dopasowania

    podobne_dopasowania = sum(
        1
        for imie_g in imiona_glowny
        for imie_d in imiona_duplikat
        if len(imie_g) >= 3
        and len(imie_d) >= 3
        and (
            imie_g.lower().startswith(imie_d.lower()[:3])
            or imie_d.lower().startswith(imie_g.lower()[:3])
        )
        and imie_g.lower() != imie_d.lower()
    )
    if podobne_dopasowania > 0:
        powody.append(f"podobne imię ({podobne_dopasowania})")
        pewnosc += 15 * podobne_dopasowania

    inicjaly_glowny = [imie[0].upper() for imie in imiona_glowny if len(imie) > 0]
    inicjaly_duplikat = _inicjaly_duplikatu(duplikat.imiona)
    dopasowania_inicjalow = sum(
        1
        for inicjal_g in inicjaly_glowny
        for inicjal_d in inicjaly_duplikat
        if inicjal_g == inicjal_d
    )
    if dopasowania_inicjalow > 0:
        powody.append(f"pasujące inicjały ({dopasowania_inicjalow})")
        pewnosc += 5 * dopasowania_inicjalow

    return pewnosc, powody


def _lata_publikacji(autor: Autor) -> set:
    return set(
        Rekord.objects.prace_autora(autor)
        .filter(rok__isnull=False)
        .values_list("rok", flat=True)
    )


def _ocena_temporalna(glowny_autor: Autor, duplikat: Autor) -> tuple[int, list[str]]:
    """Analiza temporalna - porównanie lat publikacji."""
    lata_glowny = _lata_publikacji(glowny_autor)
    lata_duplikat = _lata_publikacji(duplikat)

    if not (lata_glowny and lata_duplikat):
        return 0, []

    wspolne_lata = lata_glowny & lata_duplikat
    if wspolne_lata:
        return 20, [f"wspólne lata publikacji: {sorted(wspolne_lata)}"]

    min_odleglosc = min(
        abs(rok_glowny - rok_duplikat)
        for rok_glowny in lata_glowny
        for rok_duplikat in lata_duplikat
    )
    if min_odleglosc <= 2:
        return 15, [
            f"bliskie lata publikacji (różnica {min_odleglosc} lat) "
            "- prawdopodobny duplikat"
        ]
    if min_odleglosc <= 7:
        return -5, [
            f"średnia odległość lat publikacji ({min_odleglosc} lat) - możliwy duplikat"
        ]
    return -20, [
        f"duża odległość lat publikacji ({min_odleglosc} lat) "
        "- mało prawdopodobny duplikat"
    ]


# Kolejność MA znaczenie - definiuje kolejność wpisów w "powody_podobienstwa".
_OCENY = (
    _ocena_liczby_publikacji,
    _ocena_tytulu,
    _ocena_orcid,
    _ocena_nazwiska,
    _ocena_zamiany_imienia_nazwiska,
    _ocena_imion,
    _ocena_temporalna,
)


def _analizuj_duplikat(
    glowny_autor: Autor, plec_glowny: Gender, duplikat: Autor
) -> dict | None:
    """Zwraca słownik analizy pojedynczego duplikatu albo ``None``.

    ``None`` oznacza hard rejection (imiona całkowicie rozłączne).
    """
    if _imiona_calkowicie_rozlaczne(glowny_autor, duplikat):
        return None

    analiza = {"autor": duplikat, "powody_podobienstwa": [], "pewnosc": 0}  # 0-100%

    oceny = [_ocena_plci(glowny_autor, plec_glowny, duplikat)]
    oceny += [ocena(glowny_autor, duplikat) for ocena in _OCENY]

    for delta, powody in oceny:
        analiza["pewnosc"] += delta
        analiza["powody_podobienstwa"].extend(powody)

    return analiza


def analiza_duplikatow(osoba_z_instytucji: OsobaZInstytucji) -> dict:
    """
    Przeprowadza szczegółową analizę znalezionych duplikatów.

    Args:
        osoba_z_instytucji: Obiekt OsobaZInstytucji jako punkt odniesienia

    Returns:
        dict: Słownik z analizą duplikatów zawierający:
            - glowny_autor: główny autor z BPP
            - duplikaty: lista znalezionych duplikatów
            - analiza: szczegółowa analiza każdego duplikatu
    """
    glowny_autor = _ustal_glownego_autora(osoba_z_instytucji)
    if glowny_autor is None:
        return dict(_BRAK_GLOWNEGO_AUTORA)

    duplikaty = szukaj_kopii(osoba_z_instytucji)

    # Zgadnij płeć głównego autora (raz, przed pętlą)
    plec_glowny = zgadnij_plec_autora(glowny_autor.imiona, glowny_autor.plec)

    analiza_duplikatow_lista = [
        analiza
        for duplikat in duplikaty
        if (analiza := _analizuj_duplikat(glowny_autor, plec_glowny, duplikat))
        is not None
    ]

    # Sortuj duplikaty według pewności
    analiza_duplikatow_lista.sort(key=lambda x: x["pewnosc"], reverse=True)

    return {
        "glowny_autor": glowny_autor,
        "duplikaty": duplikaty,
        "analiza": analiza_duplikatow_lista,
        "ilosc_duplikatow": duplikaty.count(),
    }


def autor_ma_publikacje_z_lat(
    autor: Autor, lata_od: int = 2022, lata_do: int = 2025
) -> bool:
    """
    Sprawdza czy autor ma publikacje z określonego zakresu lat.

    Args:
        autor: Obiekt Autor do sprawdzenia
        lata_od: Rok początkowy (domyślnie 2022)
        lata_do: Rok końcowy (domyślnie 2025)

    Returns:
        bool: True jeśli autor ma publikacje z tego okresu, False w przeciwnym przypadku
    """
    return (
        Rekord.objects.prace_autora(autor)
        .filter(rok__gte=lata_od, rok__lte=lata_do)
        .exists()
    )
