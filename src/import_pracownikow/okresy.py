"""Resolver okresu zatrudnienia (``Autor_Jednostka``) po „dacie od" (§7 spec
``2026-07-13-import-pracownikow-synchronizacja-dat-zatrudnienia``).

„Data od" = TOŻSAMOŚĆ okresu zatrudnienia (zgodne z ``unique_together =
(autor, jednostka, rozpoczal_prace)``). Ta sama data od → ten sam okres → do
niego synchronizujemy „data do"; inna data od → NOWY okres = nowy AJ.

Jedno źródło prawdy dla analizy (``analyze._przetworz_wiersz``), rekonstrukcji
po zmianie autora (``pewnosc.odtworz_autor_jednostka``) oraz porównywarki
podglądu (``models.ImportPracownikowRow.porownaj_z_baza``) — podgląd nie może
zapowiadać innego okresu niż utworzy commit.
"""

from datetime import date


def _wybierz_aktywny_najswiezszy(aj_lista):
    """Deterministyczny wybór ``Autor_Jednostka`` z gotowej listy (bez ORM).

    Parytet z dawnym SQL ``order_by("-rozpoczal_prace")`` (PostgreSQL przy
    ``DESC`` daje NULLS FIRST → ``rozpoczal_prace = NULL`` traktowany jako
    „najświeższy"): preferuje AKTYWNY etat (``zakonczyl_prace IS NULL``); w
    puli ``rozpoczal_prace = None`` jest „największe", potem najświeższy
    ``rozpoczal_prace``; tie-break po ``pk`` (SQL go nie gwarantował — tu
    wzmacniamy determinizm). Zwraca ``None`` dla pustej listy.

    Klucz na ``max`` MUSI unikać ``TypeError`` (porównanie ``date`` z ``None``),
    dlatego ``None`` mapujemy na ``(True, date.min)`` przez oś boolowską.
    """
    if not aj_lista:
        return None
    aktywne = [aj for aj in aj_lista if aj.zakonczyl_prace is None]
    pula = aktywne or aj_lista
    return max(
        pula,
        key=lambda aj: (
            aj.rozpoczal_prace is None,
            aj.rozpoczal_prace or date.min,
            aj.pk or 0,
        ),
    )


def rozwiaz_okres_zatrudnienia(autor, jednostka, plik_od, *, aj_lista=None):
    """Rozstrzyga docelowy okres zatrudnienia dla ``(autor, jednostka, plik_od)``.

    Zwraca:
    - ``("istniejacy", aj)`` — dopasowany okres (ta sama data od) lub okres
      niedatowany (``rozpoczal_prace = NULL``) do wypełnienia;
    - ``("nowy", rozpoczal_prace | None)`` — utwórz nowy AJ z tą datą od
      (``None`` = pusty ``plik_od`` → fallback ``data zmian → dziś`` przy
      materializacji).

    ``plik_od`` MUSI być ``date | None`` — ISO-string dałby ``rozpoczal_prace ==
    "2020-01-01"`` zawsze ``False`` → cichy fałszywy „nowy okres" + duplikat AJ.

    ``aj_lista`` (opcjonalnie) to już pobrana lista okresów ``(autor, jednostka)``
    — pozwala wołającemu wykonać JEDNO zapytanie i współdzielić je z porównywarką
    (bez N+1). Gdy ``None`` — resolver odpytuje bazę sam.
    """
    if aj_lista is None:
        from bpp.models import Autor_Jednostka

        aj_lista = list(
            Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka)
        )

    if plik_od is not None:
        exact = [aj for aj in aj_lista if aj.rozpoczal_prace == plik_od]
        if exact:
            return ("istniejacy", exact[0])
        niedatowane = sorted(
            (aj for aj in aj_lista if aj.rozpoczal_prace is None),
            key=lambda aj: aj.pk or 0,
        )
        if niedatowane:
            return ("istniejacy", niedatowane[0])
        aktywne = [aj for aj in aj_lista if aj.zakonczyl_prace is None]
        if aktywne:
            # Istnieje OTWARTY (trwający) okres: nowy otwarty okres byłby i tak
            # scalony z powrotem przez ``Autor.defragmentuj_jednostke`` (dwa
            # równoległe zatrudnienia w jednej jednostce to sprzeczność). Celujemy
            # więc w aktywny okres — różnicę „data od" POKAZUJEMY w podglądzie, ale
            # NIE tworzymy nowego okresu i NIE domykamy starego (decyzja usera:
            # „nowy okres tylko gdy stary zamknięty"; spójne z P2).
            return ("istniejacy", _wybierz_aktywny_najswiezszy(aktywne))
        # Wszystkie istniejące okresy zamknięte (osoba odeszła i wraca) → nowy
        # okres nie nakłada się na aktywny, defragmentuj go nie scali.
        return ("nowy", plik_od)

    aj = _wybierz_aktywny_najswiezszy(aj_lista)
    if aj is not None:
        return ("istniejacy", aj)
    return ("nowy", None)
