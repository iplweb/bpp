import pytest
from model_bakery import baker

from bpp import const


@pytest.mark.django_db
def test_add_authors_tworzy_redaktora(typy_odpowiedzialnosci):
    from bpp.models import Autor, Jednostka, Wydawnictwo_Zwarte
    from importer_publikacji.models import ImportedAuthor, ImportSession
    from importer_publikacji.views.publikacja import _add_authors_to_record

    session = baker.make(ImportSession)
    baker.make(
        ImportedAuthor,
        session=session,
        order=0,
        match_status=ImportedAuthor.MatchStatus.MANUAL,
        matched_autor=baker.make(Autor, nazwisko="Kowalski", imiona="Jan"),
        matched_jednostka=baker.make(Jednostka),
        zapisany_jako="Kowalski Jan",
        typ_ogolny=const.TO_REDAKTOR,
    )
    rekord = baker.make(Wydawnictwo_Zwarte)
    _add_authors_to_record(session, rekord)

    wiersz = rekord.autorzy_set.get()
    assert wiersz.typ_odpowiedzialnosci.typ_ogolny == const.TO_REDAKTOR


@pytest.mark.django_db
def test_add_authors_domyslnie_autor(typy_odpowiedzialnosci):
    from bpp.models import Autor, Jednostka, Wydawnictwo_Zwarte
    from importer_publikacji.models import ImportedAuthor, ImportSession
    from importer_publikacji.views.publikacja import _add_authors_to_record

    session = baker.make(ImportSession)
    baker.make(
        ImportedAuthor,
        session=session,
        order=0,
        match_status=ImportedAuthor.MatchStatus.MANUAL,
        matched_autor=baker.make(Autor, nazwisko="Nowak", imiona="Anna"),
        matched_jednostka=baker.make(Jednostka),
        zapisany_jako="Nowak Anna",
    )
    rekord = baker.make(Wydawnictwo_Zwarte)
    _add_authors_to_record(session, rekord)

    wiersz = rekord.autorzy_set.get()
    assert wiersz.typ_odpowiedzialnosci.typ_ogolny == const.TO_AUTOR
