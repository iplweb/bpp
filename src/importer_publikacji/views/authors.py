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


def _auto_match_authors(session, authors_data, year):
    """Auto-dopasuj autorów z danych dostawcy.

    Dla każdego importowanego autora:

    - DOKLADNE → AUTO_EXACT z preselectowanym bpp_autor
    - LUZNE → AUTO_LOOSE z preselectowanym bpp_autor (niska pewność)
    - WYMAGA_INGERENCJI → AUTO_LOOSE z sugerowanym bpp_autor (user
      powinien potwierdzić; lista kandydatów dostępna w UI)
    - BRAK → UNMATCHED (default)

    Kandydaci z metadanymi (pewnosc, powod, publikacji) są zapisywani
    do ``ImportedAuthor_Candidate`` żeby UI mógł pokazać listę z
    badge'ami.
    """
    for i, author_data in enumerate(authors_data):
        family = author_data.get("family", "")
        given = author_data.get("given", "")
        imported = ImportedAuthor.objects.create(
            session=session,
            order=i,
            family_name=family,
            given_name=given,
            orcid=author_data.get("orcid", ""),
            zapisany_jako=f"{family} {given}".strip(),
        )

        result = Komparator.porownaj_author(author_data)
        bpp_autor = result.sugerowany or result.rekord_po_stronie_bpp

        if result.status == StatusPorownania.DOKLADNE and bpp_autor:
            imported.match_status = ImportedAuthor.MatchStatus.AUTO_EXACT
        elif (
            result.status
            in (StatusPorownania.LUZNE, StatusPorownania.WYMAGA_INGERENCJI)
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


def _prefill_dyscypliny_z_zgloszen(session):
    """Uzupełnij brakujące dyscypliny z danych zgłoszeń publikacji.

    Szuka pasującego Zgloszenie_Publikacji (po DOI/tytule)
    i kopiuje dyscypliny dla autorów, którym brakuje.
    Nigdy nie nadpisuje istniejących wartości.
    """
    from zglos_publikacje.models import Zgloszenie_Publikacji_Autor

    zgloszenie = _find_matching_zgloszenie(session)
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
def _create_unmatched_authors(session, obca):
    """Utwórz rekordy Autor dla niedopasowanych
    autorów i przypisz do obcej jednostki."""
    unmatched = session.authors.filter(
        match_status=(ImportedAuthor.MatchStatus.UNMATCHED)
    )
    for imported in unmatched:
        orcid = imported.orcid.strip() or None

        # Jeśli ORCID podany i istnieje Autor
        # z takim ORCID -- dopasuj istniejącego
        if orcid:
            existing = Autor.objects.filter(orcid=orcid).first()
            if existing:
                imported.matched_autor = existing
                imported.matched_jednostka = obca
                imported.match_status = ImportedAuthor.MatchStatus.MANUAL
                existing.dodaj_jednostke(obca)
                imported.save()
                continue

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
