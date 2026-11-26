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
