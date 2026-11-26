"""Wybór wersji publikacji PBN, z której bierzemy dane (FD#511).

Uczelnia przypina na swoim profilu w PBN konkretną wersję publikacji;
identyfikator tej wersji przychodzi z profilu instytucji jako
``publicationVersion``. Wersja „bieżąca” w repozytorium PBN mogła zostać
zmieniona przez kogoś spoza uczelni, dlatego pierwszeństwo ma przypięta.
"""

from dataclasses import dataclass

PRZYPIETA = "przypięta na profilu instytucji"
BIEZACA_BRAK_PRZYPIETEJ = "bieżąca (profil instytucji nie wskazuje wersji)"
BIEZACA_NIEZNANA_PRZYPIETA = (
    "bieżąca (wersji przypiętej na profilu nie ma w pobranych danych)"
)
BIEZACA_NIEJEDNOZNACZNA = "bieżąca (profil instytucji wskazuje kilka różnych wersji)"


@dataclass
class WybranaWersja:
    #: Element listy ``versions`` publikacji (słownik z kluczem ``object``)
    #: albo ``None``, gdy publikacja nie ma żadnej używalnej wersji.
    wersja: dict | None
    #: Skąd wersja — tekst do raportu (jedna ze stałych powyżej).
    zrodlo: str
    #: ``True``, gdy użyto wersji przypiętej, a w PBN jest inna bieżąca.
    jest_nowsza_biezaca: bool = False

    @property
    def obiekt(self):
        if self.wersja is None:
            return None
        return self.wersja.get("object") or None


def znajdz_wersje(pbn_publication, identyfikator_wersji):
    """Element ``versions`` o podanym ``versionHash`` albo ``None``."""
    if not identyfikator_wersji:
        return None
    szukany = str(identyfikator_wersji).lower()
    for wersja in pbn_publication.versions or []:
        if str(wersja.get("versionHash", "")).lower() == szukany:
            return wersja
    return None


def wybierz_wersje(pbn_publication, przypiete):
    """Wersja do użycia dla publikacji.

    ``przypiete`` — lista identyfikatorów wersji z profilu instytucji (zwykle
    jeden; profil ma wiersz na każdą osobę, więc bywa ich kilka takich
    samych). Reguła: dokładnie jedna przypięta i obecna w ``versions`` →
    ona; w każdym innym wypadku wersja bieżąca, z jawnym powodem w raporcie.
    """
    biezaca = pbn_publication.current_version
    rozne = sorted({str(p).lower() for p in przypiete or [] if p})

    if not rozne:
        return WybranaWersja(biezaca, BIEZACA_BRAK_PRZYPIETEJ)
    if len(rozne) > 1:
        return WybranaWersja(biezaca, BIEZACA_NIEJEDNOZNACZNA)

    przypieta = znajdz_wersje(pbn_publication, rozne[0])
    if przypieta is None:
        return WybranaWersja(biezaca, BIEZACA_NIEZNANA_PRZYPIETA)
    return WybranaWersja(
        przypieta,
        PRZYPIETA,
        jest_nowsza_biezaca=biezaca is not None and biezaca is not przypieta,
    )


class WersjePrzypieteNaProfilu:
    """Wybieracz wersji dla importu masowego (``importuj_z_wersji``).

    Wersje przypięte czyta z lokalnej kopii profilu instytucji
    (``PublikacjaInstytucji``) — pobranej wcześniej z PBN. Publikacji spoza
    profilu tej uczelni nie dotyczy (zostaje wersja bieżąca, bez uwag).

    Po imporcie ``z_przypietej`` i ``z_biezacej`` mówią, z czego powstały
    rekordy prac z profilu; ``z_biezacej`` to ``{pbn_uid: powód}``.
    """

    def __init__(self, uczelnia):
        from pbn_api.models import PublikacjaInstytucji

        self.przypiete = {}
        if uczelnia is not None and uczelnia.pbn_uid_id:
            for pbn_uid, wersja in PublikacjaInstytucji.objects.filter(
                institutionId_id=uczelnia.pbn_uid_id
            ).values_list("publicationId_id", "publicationVersion"):
                self.przypiete.setdefault(pbn_uid, []).append(wersja)
        self.z_przypietej = set()
        self.z_biezacej = {}

    def __call__(self, pbn_publication):
        przypiete = self.przypiete.get(pbn_publication.pk)
        if przypiete is None:
            return None
        wybrana = wybierz_wersje(pbn_publication, przypiete)
        if wybrana.zrodlo == PRZYPIETA:
            self.z_przypietej.add(pbn_publication.pk)
        else:
            self.z_biezacej[pbn_publication.pk] = wybrana.zrodlo
        return wybrana.wersja

    def podsumowanie(self):
        """Tekst do logu importu albo ``None``, gdy nie ma o czym pisać."""
        if not self.z_przypietej and not self.z_biezacej:
            return None
        tekst = (
            f"Prace z profilu instytucji: {len(self.z_przypietej)} wzięto z wersji "
            f"przypiętej na profilu, {len(self.z_biezacej)} z wersji bieżącej."
        )
        if self.z_biezacej:
            tekst += (
                " Wersję bieżącą użyto tam, gdzie profil instytucji nie wskazuje "
                "wersji albo wskazanej wersji nie ma w pobranych danych — "
                "sprawdź te prace: " + ", ".join(sorted(self.z_biezacej)) + "."
            )
        return tekst
