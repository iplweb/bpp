"""Auto-matching autorów + prefill dyscyplin ze zgłoszeń + tworzenie
brakujących Autor-ów.

Zawiera funkcje wywoływane z ``FetchView.post`` (auto-matching tuż po
pobraniu danych) oraz z ``CreateUnmatchedAuthorsView.post``
(materializacja niedopasowanych autorów jako rekordy ``Autor``).
"""

from django.db import transaction
from django.db.models import Count, Q

from bpp.models import Autor
from crossref_bpp.core import Komparator, StatusPorownania
from import_common.normalization import normalize_doi

from ..models import ImportedAuthor, ImportedAuthor_Candidate


def _orcid_settable_qs(session):
    """Queryset autorów kwalifikujących się do ustawienia ORCID.

    Warunki:
    - ImportedAuthor ma ORCID od dostawcy (niepusty)
    - Jest dopasowany do Autora w BPP
    - Autor w BPP nie ma ORCID (NULL lub "")
    - Ten sam Autor BPP nie jest dopasowany wielokrotnie w sesji
    """
    all_authors = session.authors.all()

    # Znajdź matched_autor_id pojawiające się więcej niż raz
    dupes = (
        all_authors.filter(matched_autor__isnull=False)
        .values("matched_autor")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
        .values_list("matched_autor", flat=True)
    )

    return (
        all_authors.filter(
            ~Q(orcid=""),
            matched_autor__isnull=False,
        )
        .filter(
            Q(matched_autor__orcid__isnull=True) | Q(matched_autor__orcid=""),
        )
        .exclude(
            matched_autor__in=dupes,
        )
    )


def _get_dyscyplina(autor, year):
    """Pobierz dyscyplinę autora dla danego roku."""
    from bpp.models import Autor_Dyscyplina

    try:
        ad = Autor_Dyscyplina.objects.get(autor=autor, rok=year)
        if ad.dyscyplina_naukowa and not ad.subdyscyplina_naukowa:
            return ad.dyscyplina_naukowa
    except Autor_Dyscyplina.DoesNotExist:
        pass
    except Autor_Dyscyplina.MultipleObjectsReturned:
        pass
    return None


def _apply_dyscyplina(imported, bpp_autor, year):
    if not (year and bpp_autor):
        return
    dyscyplina = _get_dyscyplina(bpp_autor, year)
    imported.matched_dyscyplina = dyscyplina
    if dyscyplina:
        imported.dyscyplina_source = ImportedAuthor.DyscyplinaSource.AUTO_JEDYNA


def _auto_match_single_author(session, author_data, order, year):
    """Dopasuj pojedynczego autora i zwróć utworzony ImportedAuthor.

    Wyciągnięte z _auto_match_authors żeby celery task mógł raportować
    postęp po każdej iteracji. Łączy:

    - status na podstawie wyniku Komparator-a (DOKLADNE / LUZNE /
      WYMAGA_INGERENCJI z sugerowanym kandydatem),
    - zapisany_jako domyślnie pre-fillowane z family+given dostawcy,
    - bulk_create kandydatów do ImportedAuthor_Candidate (UI modala).
    """
    # Defense-in-depth: przycinamy do limitow kolumn, zeby zaden wpis (np.
    # zle sparsowane pole author) nie wywalil calego importu przez
    # StringDataRightTruncation (Freshdesk #344). Root-cause naprawiony jest
    # w _parse_authors; tu jest siatka bezpieczenstwa.
    family = (author_data.get("family") or "")[:255]
    given = (author_data.get("given") or "")[:255]
    orcid = (author_data.get("orcid") or "")[:50]
    imported = ImportedAuthor.objects.create(
        session=session,
        order=order,
        family_name=family,
        given_name=given,
        orcid=orcid,
        zapisany_jako=f"{family} {given}".strip()[:512],
    )

    result = Komparator.porownaj_author(author_data)
    bpp_autor = result.sugerowany or result.rekord_po_stronie_bpp

    if result.status == StatusPorownania.DOKLADNE and bpp_autor:
        imported.match_status = ImportedAuthor.MatchStatus.AUTO_EXACT
    elif (
        result.status in (StatusPorownania.LUZNE, StatusPorownania.WYMAGA_INGERENCJI)
        and bpp_autor
    ):
        imported.match_status = ImportedAuthor.MatchStatus.AUTO_LOOSE
    else:
        bpp_autor = None

    if bpp_autor:
        imported.matched_autor = bpp_autor
        imported.matched_jednostka = bpp_autor.aktualna_jednostka
        _apply_dyscyplina(imported, bpp_autor, year)

    imported.save()

    if result.kandydaci:
        ImportedAuthor_Candidate.objects.bulk_create(
            [
                ImportedAuthor_Candidate(
                    imported_author=imported,
                    autor=k.autor,
                    pewnosc=k.pewnosc,
                    powod=k.powod,
                    publikacji_count=k.publikacji,
                )
                for k in result.kandydaci
            ]
        )
    return imported


def _auto_match_authors(session, authors_data, year):
    """Auto-dopasuj autorów z danych dostawcy (thin wrapper, używany
    w testach i w synchronicznych ścieżkach bez progress reporting).
    """
    for i, author_data in enumerate(authors_data):
        _auto_match_single_author(session, author_data, i, year)


def _find_matching_zgloszenie(session):
    """Szukaj pasującego zgłoszenia publikacji po DOI lub tytule.

    Zwraca obiekt Zgloszenie_Publikacji lub None.
    """
    from zglos_publikacje.models import Zgloszenie_Publikacji

    excluded = (
        Zgloszenie_Publikacji.Statusy.ODRZUCONO,
        Zgloszenie_Publikacji.Statusy.SPAM,
    )

    doi = session.normalized_data.get("doi")
    if doi:
        normalized = normalize_doi(doi)
        if normalized:
            zgl = (
                Zgloszenie_Publikacji.objects.filter(
                    doi__iexact=normalized,
                )
                .exclude(status__in=excluded)
                .order_by("-ostatnio_zmieniony")
                .first()
            )
            if zgl:
                return zgl

    title = session.normalized_data.get("title", "")
    if title and len(title) >= 10:
        zgl = (
            Zgloszenie_Publikacji.objects.filter(
                tytul_oryginalny__iexact=title,
            )
            .exclude(status__in=excluded)
            .order_by("-ostatnio_zmieniony")
            .first()
        )
        if zgl:
            return zgl

    return None


def _zgloszenie_dla_prefilla(session):
    """Zgłoszenie, z którego prefill ma brać dyscypliny.

    Gdy sesja jest **związana** ze zgłoszeniem (FD#443: jawny wybór
    operatora albo auto-wiązanie po DOI), prefill używa go wprost —
    inaczej dyscypliny mogłyby przyjść z innego zgłoszenia niż to, które
    import domknie (heurystyka ``_find_matching_zgloszenie`` dopasowuje
    też po tytule).

    Heurystyka zostaje wyłącznie jako fallback dla sesji niezwiązanych —
    ich zachowanie jest bez zmian.
    """
    if session.zgloszenie_id:
        return session.zgloszenie
    return _find_matching_zgloszenie(session)


def _prefill_dyscypliny_z_zgloszen(session):
    """Uzupełnij brakujące dyscypliny z danych zgłoszeń publikacji.

    Bierze zgłoszenie związane z sesją, a gdy takiego nie ma — szuka
    pasującego ``Zgloszenie_Publikacji`` heurystycznie (po DOI/tytule).
    Kopiuje dyscypliny dla autorów, którym brakuje. Nigdy nie nadpisuje
    istniejących wartości.
    """
    from zglos_publikacje.models import Zgloszenie_Publikacji_Autor

    zgloszenie = _zgloszenie_dla_prefilla(session)
    if not zgloszenie:
        return

    zpa_by_autor = {}
    for zpa in Zgloszenie_Publikacji_Autor.objects.filter(
        rekord=zgloszenie,
    ).select_related("dyscyplina_naukowa", "jednostka"):
        zpa_by_autor[zpa.autor_id] = zpa

    to_update = session.authors.filter(
        matched_autor__isnull=False,
        matched_dyscyplina__isnull=True,
    )

    for imported in to_update:
        zpa = zpa_by_autor.get(imported.matched_autor_id)
        if not zpa:
            continue
        if zpa.dyscyplina_naukowa_id:
            imported.matched_dyscyplina = zpa.dyscyplina_naukowa
            imported.dyscyplina_source = ImportedAuthor.DyscyplinaSource.ZGLOSZENIE
        if not imported.matched_jednostka_id and zpa.jednostka_id:
            imported.matched_jednostka = zpa.jednostka
        imported.save()


@transaction.atomic
def _create_single_author(imported, obca):
    """Utwórz (lub dopasuj po ORCID) rekord ``Autor`` dla pojedynczego
    ``ImportedAuthor`` i przypisz go do obcej jednostki.

    Wspólny rdzeń dla masowego ``_create_unmatched_authors`` oraz
    per-wierszowego ``AuthorCreateNewView`` ("Utwórz nowego" z modala
    edycji). Trzymane w jednym miejscu, żeby logika dedupowania po ORCID
    nie rozjechała się między ścieżkami.

    Jeśli dostawca podał ORCID i istnieje już ``Autor`` z tym ORCID-em,
    dopasowuje istniejącego zamiast tworzyć duplikat.
    """
    orcid = imported.orcid.strip() or None

    if orcid:
        existing = Autor.objects.filter(orcid=orcid).first()
        if existing:
            existing.dodaj_jednostke(obca)
            imported.matched_autor = existing
            imported.matched_jednostka = obca
            imported.match_status = ImportedAuthor.MatchStatus.MANUAL
            imported.save()
            return existing

    autor = Autor.objects.create(
        imiona=imported.given_name,
        nazwisko=imported.family_name,
        orcid=orcid,
    )
    autor.dodaj_jednostke(obca)

    imported.matched_autor = autor
    imported.matched_jednostka = obca
    imported.match_status = ImportedAuthor.MatchStatus.MANUAL
    imported.save()
    return autor


@transaction.atomic
def _create_unmatched_authors(session, obca):
    """Utwórz rekordy Autor dla niedopasowanych
    autorów i przypisz do obcej jednostki."""
    unmatched = session.authors.filter(
        match_status=(ImportedAuthor.MatchStatus.UNMATCHED)
    )
    for imported in unmatched:
        _create_single_author(imported, obca)
