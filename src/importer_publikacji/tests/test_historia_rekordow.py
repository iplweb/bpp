"""Rekordy utworzone przez importer publikacji mają historię w adminie.

Wcześniej autor i praca utworzone przez importer (CrossRef/BibTeX/PBN)
nie miały żadnego wpisu ``LogEntry`` ani wersji reversion — na stronie
„Historia" w adminie wyglądało to tak, jakby rekord pojawił się znikąd.
"""

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from bpp.models import Autor
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
