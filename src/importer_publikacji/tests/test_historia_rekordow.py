"""Rekordy utworzone przez importer publikacji mają historię w adminie.

Wcześniej autor i praca utworzone przez importer (CrossRef/BibTeX/PBN)
nie miały żadnego wpisu ``LogEntry`` ani wersji reversion — na stronie
„Historia" w adminie wyglądało to tak, jakby rekord pojawił się znikąd.
"""

from datetime import date

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from bpp.models import Autor, Autor_Jednostka
from bpp.wersjonowanie import zarejestruj_utworzenie
from importer_publikacji.models import ImportedAuthor, ImportSession
from importer_publikacji.tests.test_views_create_publication import (
    _make_session_for_publication,
)
from importer_publikacji.views import _create_publication


def _wpisy(obj):
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(obj),
        object_id=str(obj.pk),
    )


def _sesja(user, **autor):
    session = ImportSession.objects.create(
        created_by=user,
        provider_name="CrossRef",
        identifier="10.1234/historia",
        raw_data={},
        normalized_data={},
    )
    ImportedAuthor.objects.create(
        session=session,
        order=0,
        match_status=ImportedAuthor.MatchStatus.UNMATCHED,
        **autor,
    )
    return session


@pytest.mark.django_db
def test_utworzony_autor_ma_wpis_historii_i_wersje(
    importer_client, importer_user, uczelnia_z_obca_jednostka
):
    session = _sesja(importer_user, family_name="Znikądowski", given_name="Jan")

    response = importer_client.post(
        reverse(
            "importer_publikacji:authors-create-unmatched",
            kwargs={"session_id": session.pk},
        )
    )
    assert response.status_code == 200

    autor = Autor.objects.get(nazwisko="Znikądowski")
    wpis = _wpisy(autor).get()
    assert wpis.action_flag == ADDITION
    assert wpis.user == importer_user
    assert "Importer publikacji (CrossRef)" in wpis.change_message
    assert f"sesja importu nr {session.pk}" in wpis.change_message

    wersja = Version.objects.get_for_object(autor).get()
    assert wersja.revision.user == importer_user
    # Wersja ze świeżego odczytu — z polem wyliczanym przez trigger.
    assert (
        wersja.field_dict["aktualna_jednostka_id"]
        == uczelnia_z_obca_jednostka.obca_jednostka.pk
    )


@pytest.mark.django_db
def test_utworzony_pojedynczo_autor_ma_wpis_historii(
    importer_client, importer_user, uczelnia_z_obca_jednostka
):
    session = _sesja(importer_user, family_name="Pojedynczy", given_name="Adam")
    ia = session.authors.get()

    response = importer_client.post(
        reverse(
            "importer_publikacji:author-create-new",
            kwargs={"session_id": session.pk, "author_id": ia.pk},
        )
    )
    assert response.status_code == 200

    autor = Autor.objects.get(nazwisko="Pojedynczy")
    assert _wpisy(autor).get().user == importer_user


@pytest.mark.django_db
def test_dopasowanie_po_orcid_loguje_dopisanie_jednostki(
    importer_client, importer_user, uczelnia_z_obca_jednostka
):
    existing = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", orcid="0000-0001-2345-6789"
    )
    session = _sesja(
        importer_user,
        family_name="Kowalski",
        given_name="Jan",
        orcid="0000-0001-2345-6789",
    )

    importer_client.post(
        reverse(
            "importer_publikacji:authors-create-unmatched",
            kwargs={"session_id": session.pk},
        )
    )

    wpis = _wpisy(existing).get()
    assert wpis.action_flag == CHANGE
    assert "Dopisano jednostkę" in wpis.change_message


@pytest.mark.django_db
def test_utworzona_praca_ma_wpis_historii(
    importer_user,
    admin_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        statusy_korekt,
        typy_odpowiedzialnosci,
    )

    record = _create_publication(session, user=admin_user)

    wpis = _wpisy(record).get()
    assert wpis.action_flag == ADDITION
    assert wpis.user == admin_user
    assert "Importer publikacji (CrossRef)" in wpis.change_message


@pytest.mark.django_db
def test_utworzona_praca_bez_uzytkownika_przypisana_tworcy_sesji(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        statusy_korekt,
        typy_odpowiedzialnosci,
    )

    record = _create_publication(session)

    assert _wpisy(record).get().user == importer_user


def _importuj_po_orcid(client, session):
    return client.post(
        reverse(
            "importer_publikacji:authors-create-unmatched",
            kwargs={"session_id": session.pk},
        )
    )


@pytest.mark.django_db
def test_dopisanie_jednostki_widoczne_w_historii_autora_z_wersjami(
    importer_client, importer_user, admin_client, uczelnia_z_obca_jednostka
):
    """Autor z wcześniejszymi wersjami: strona „Historia" pokazuje LogEntry
    tylko sprzed pierwszej wersji, więc dopisanie jednostki musi dostać
    własną wersję — inaczej byłoby niewidoczne."""
    existing = baker.make(
        Autor, nazwisko="Wersjonowany", imiona="Jan", orcid="0000-0002-0000-0001"
    )
    zarejestruj_utworzenie(importer_user, existing, "Wcześniejsza wersja.")
    session = _sesja(
        importer_user,
        family_name="Wersjonowany",
        given_name="Jan",
        orcid="0000-0002-0000-0001",
    )

    _importuj_po_orcid(importer_client, session)

    wersje = Version.objects.get_for_object(existing)
    assert wersje.count() == 2
    # Wersja ze świeżego odczytu — z aktualna_jednostka po triggerze.
    assert (
        wersje.first().field_dict["aktualna_jednostka_id"]
        == uczelnia_z_obca_jednostka.obca_jednostka.pk
    )
    resp = admin_client.get(reverse("admin:bpp_autor_history", args=[existing.pk]))
    assert resp.status_code == 200
    assert "Dopisano jednostkę" in resp.content.decode()


@pytest.mark.django_db
def test_brak_falszywego_wpisu_gdy_defragmentacja_scala_zatrudnienie(
    importer_client, importer_user, uczelnia_z_obca_jednostka
):
    """Przy zamkniętym zatrudnieniu w obcej jednostce ``dodaj_jednostke``
    zwraca nowy wiersz bez dat, który ``defragmentuj`` od razu usuwa — stan
    zatrudnień się nie zmienia, więc nie może powstać wpis „Dopisano
    jednostkę" (zwrócony obiekt nie istnieje już w bazie)."""
    obca = uczelnia_z_obca_jednostka.obca_jednostka
    existing = baker.make(
        Autor, nazwisko="Zamkniety", imiona="Jan", orcid="0000-0002-0000-0002"
    )
    Autor_Jednostka.objects.create(
        autor=existing,
        jednostka=obca,
        rozpoczal_prace=date(2020, 1, 1),
        zakonczyl_prace=date(2021, 12, 31),
    )
    session = _sesja(
        importer_user,
        family_name="Zamkniety",
        given_name="Jan",
        orcid="0000-0002-0000-0002",
    )

    _importuj_po_orcid(importer_client, session)

    assert Autor_Jednostka.objects.filter(autor=existing).count() == 1
    assert not _wpisy(existing).exists()


@pytest.mark.django_db
def test_brak_wpisu_gdy_jednostka_juz_przypisana(
    importer_client, importer_user, uczelnia_z_obca_jednostka
):
    existing = baker.make(
        Autor, nazwisko="Przypisany", imiona="Jan", orcid="0000-0002-0000-0003"
    )
    existing.dodaj_jednostke(uczelnia_z_obca_jednostka.obca_jednostka)
    session = _sesja(
        importer_user,
        family_name="Przypisany",
        given_name="Jan",
        orcid="0000-0002-0000-0003",
    )

    _importuj_po_orcid(importer_client, session)

    assert not _wpisy(existing).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("zbiorczo", [False, True])
def test_ustawienie_orcid_z_importera_trafia_do_historii(
    importer_client, importer_user, zbiorczo
):
    autor = baker.make(Autor, nazwisko="Bezorcidowy", imiona="Jan", orcid=None)
    session = _sesja(
        importer_user,
        family_name="Bezorcidowy",
        given_name="Jan",
        orcid="0000-0002-0000-0004",
    )
    ia = session.authors.get()
    ia.matched_autor = autor
    ia.match_status = ImportedAuthor.MatchStatus.MANUAL
    ia.save()

    if zbiorczo:
        url = reverse(
            "importer_publikacji:authors-set-orcids",
            kwargs={"session_id": session.pk},
        )
    else:
        url = reverse(
            "importer_publikacji:author-set-orcid",
            kwargs={"session_id": session.pk, "author_id": ia.pk},
        )
    assert importer_client.post(url).status_code == 200

    autor.refresh_from_db()
    assert autor.orcid == "0000-0002-0000-0004"
    wpis = _wpisy(autor).get()
    assert wpis.action_flag == CHANGE
    assert wpis.user == importer_user
    assert "Ustawiono ORCID 0000-0002-0000-0004" in wpis.change_message
    # Wersja początkowa (stan bez ORCID) + wersja po zmianie.
    wersje = Version.objects.get_for_object(autor)
    assert [w.field_dict["orcid"] for w in wersje] == [
        "0000-0002-0000-0004",
        None,
    ]


@pytest.mark.django_db
def test_task_przypisuje_prace_operatorowi_nie_tworcy_sesji(
    importer_user,
    admin_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    from importer_publikacji.tasks import create_publication_task

    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        statusy_korekt,
        typy_odpowiedzialnosci,
    )

    create_publication_task.apply(args=[session.pk, admin_user.pk, False]).get()

    session.refresh_from_db()
    assert session.status == ImportSession.Status.COMPLETED
    record = session.created_record_content_type.get_object_for_this_type(
        pk=session.created_record_id
    )
    assert _wpisy(record).get().user == admin_user


@pytest.mark.django_db
def test_utworzony_patent_ma_wpis_historii(importer_user, statusy_korekt):
    from bpp.models import Patent
    from importer_publikacji.tests.test_create_patent import _make_patent_session

    record = _create_publication(_make_patent_session(importer_user))

    assert isinstance(record, Patent)
    wpis = _wpisy(record).get()
    assert wpis.action_flag == ADDITION
    assert wpis.user == importer_user
