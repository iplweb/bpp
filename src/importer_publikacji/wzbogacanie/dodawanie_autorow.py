"""Dodawanie brakujących autorów do ISTNIEJĄCEGO rekordu przez krok „Autorzy”
kreatora importera publikacji (FD#517).

Widok „Wzbogać z …” pokazuje, kogo brakuje w rekordzie. Przycisk „Dodaj
brakujących autorów” zakłada sesję importera z samymi brakującymi osobami
i otwiera krok „Autorzy” — ten sam, co przy imporcie (dopasowanie autora,
jednostki i dyscypliny, tworzenie nowych autorów). Po potwierdzeniu autorzy
trafiają do rekordu, z którego przyszedł redaktor; nowy rekord NIE powstaje.

Sesja wzbogacania to zwykła ``ImportSession`` z kluczem ``KLUCZ``
w ``matched_data`` (bez nowej kolumny i migracji). Po dodaniu autorów sesja
jest usuwana — ślad zostaje w historii rekordu.
"""

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse

from bpp.wersjonowanie import zmiana_rekordu

from ..models import ImportedAuthor, ImportSession

KLUCZ = "wzbogacany_rekord"

#: Dopasowanie osób jest synchroniczne (jedno wyszukiwanie na osobę) —
#: powyżej tylu brakujących odsyłamy do zwykłej edycji autorów rekordu.
LIMIT_OSOB = 100


def jest_sesja_wzbogacania(session) -> bool:
    return KLUCZ in (session.matched_data or {})


def odmow_tworzenia_rekordu(session):
    """Twardy guard dla tworzenia rekordu: sesja wzbogacania nigdy nie
    tworzy nowego rekordu."""
    if jest_sesja_wzbogacania(session):
        raise ValidationError(
            "Ta sesja dodaje autorów do istniejącego rekordu — nie tworzy "
            "nowego. Wróć do kroku „Autorzy”."
        )


def rekord_sesji(session):
    """Rekord, do którego sesja dodaje autorów (``None``, gdy to zwykła
    sesja importu albo rekord w międzyczasie usunięto)."""
    cel = (session.matched_data or {}).get(KLUCZ)
    if not cel:
        return None
    model = ContentType.objects.get_for_id(cel["content_type_id"]).model_class()
    return model.objects.filter(pk=cel["object_id"]).first()


def utworz_sesje(user, uczelnia, rekord, nazwa_zrodla, identyfikator, osoby, powrot):
    """Sesja importera na kroku „Autorzy” z osobami ``osoby`` (słowniki
    dostawcy: ``family``/``given``/``orcid``/``pbn_uid``), dopasowanymi
    automatycznie tak jak przy imporcie."""
    from bpp.models import Patent, Wydawnictwo_Zwarte

    from ..views.authors import _auto_match_authors

    session = ImportSession.objects.create(
        created_by=user,
        modified_by=user,
        uczelnia=uczelnia,
        provider_name=nazwa_zrodla,
        identifier=identyfikator,
        status=ImportSession.Status.SOURCE_MATCHED,
        raw_data={},
        normalized_data={
            "title": rekord.tytul_oryginalny,
            "year": rekord.rok,
            "doi": getattr(rekord, "doi", None),
            "authors": osoby,
        },
        matched_data={
            KLUCZ: {
                "content_type_id": ContentType.objects.get_for_model(rekord).pk,
                "object_id": rekord.pk,
                "powrot": powrot,
            }
        },
        charakter_formalny=getattr(rekord, "charakter_formalny", None),
        typ_kbn=getattr(rekord, "typ_kbn", None),
        jezyk=getattr(rekord, "jezyk", None),
        zrodlo=getattr(rekord, "zrodlo", None),
        jest_wydawnictwem_zwartym=isinstance(rekord, Wydawnictwo_Zwarte),
        rodzaj_rekordu=(
            ImportSession.RodzajRekordu.PATENT
            if isinstance(rekord, Patent)
            else ImportSession.RodzajRekordu.CIAGLE
        ),
    )
    _auto_match_authors(session, osoby, rekord.rok)
    return session


def _waliduj(session, rekord):
    from ..dyscypliny import waliduj_dyscypliny_sesji
    from ..views.publikacja import waliduj_afiliacje_sesji

    waliduj_afiliacje_sesji(session)
    waliduj_dyscypliny_sesji(session)

    w_rekordzie = set(rekord.autorzy_set.values_list("autor_id", flat=True))
    juz_sa = [
        str(ia.matched_autor)
        for ia in session.authors.select_related("matched_autor")
        if ia.matched_autor_id in w_rekordzie
    ]
    if juz_sa:
        raise ValidationError(
            "Ci autorzy są już na liście autorów rekordu: "
            f"{', '.join(juz_sa)}. Dopasuj te osoby do innych autorów albo "
            "usuń je z listy poniżej."
        )
    bez_jednostki = [
        str(ia.matched_autor)
        for ia in session.authors.exclude(
            match_status=ImportedAuthor.MatchStatus.UNMATCHED
        ).select_related("matched_autor")
        if ia.matched_autor_id and not ia.matched_jednostka_id
    ]
    if bez_jednostki:
        raise ValidationError(
            f"Wskaż jednostkę dla: {', '.join(bez_jednostki)} — bez niej autor "
            "nie zostanie dodany do rekordu."
        )


def dodaj_autorow_do_rekordu(session, user):
    """Dodaj dopasowanych autorów sesji do jej rekordu, z wpisem w historii.

    Zwraca ``(rekord, lista nazw dodanych autorów)``. ``ValidationError`` —
    gdy autorów nie da się dodać (tekst dla redaktora); nic nie jest wtedy
    zapisane."""
    from ..dyscypliny import przypisz_brakujace_dyscypliny
    from ..views.publikacja import _add_authors_to_record

    rekord = rekord_sesji(session)
    if rekord is None:
        raise ValidationError(
            "Rekord, do którego miały trafić autorzy, już nie istnieje — "
            "anuluj tę sesję."
        )
    _waliduj(session, rekord)
    nazwa = session.provider_name
    with (
        transaction.atomic(),
        zmiana_rekordu(user, rekord, "") as zmiana,
    ):
        przed = set(rekord.autorzy_set.values_list("pk", flat=True))
        przypisz_brakujace_dyscypliny(session, rekord, user)
        _add_authors_to_record(session, rekord)
        dodani = [
            str(wa.autor)
            for wa in rekord.autorzy_set.exclude(pk__in=przed)
            .select_related("autor")
            .order_by("kolejnosc", "pk")
        ]
        if dodani:
            zmiana.komentarz = (
                f"Dodano autorów z {nazwa} (kreator importera publikacji): "
                f"{', '.join(dodani)}"
            )
        else:
            zmiana.pomin = True
    return rekord, dodani


def potwierdz(request, session, pokaz_krok_autorow):
    """Obsługa „Dodaj autorów do rekordu” na kroku „Autorzy” sesji
    wzbogacania: dodaje autorów i wraca do porównania; przy błędzie pokazuje
    krok „Autorzy” z komunikatem."""
    powrot = session.matched_data[KLUCZ].get("powrot") or "/"
    try:
        _rekord, dodani = dodaj_autorow_do_rekordu(session, request.user)
    except ValidationError as e:
        return pokaz_krok_autorow(request, session, error=" ".join(e.messages))
    if dodani:
        messages.success(
            request,
            f"Dodano autorów do rekordu: {', '.join(dodani)}. Trafili na koniec "
            "listy — kolejność popraw w formularzu rekordu. Zmiana jest "
            "w historii rekordu.",
        )
    else:
        messages.warning(request, "Nie dodano żadnego autora.")
    session.delete()
    response = HttpResponse(status=200)
    response["HX-Redirect"] = powrot
    return response
