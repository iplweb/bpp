"""FD#620: importer — dyscyplina dla autora bez przypisania na rok pracy.

Przyczyna zgłoszenia: modal „Edycja autora" wysyłał do autocomplete dyscyplin
ID autora jako liczbę JSON, a autocomplete przyjmował tylko napis — lista
dyscyplin była pusta (testy w ``bpp/tests/test_typowe_dyscypliny.py``).

Tu: gdy operator wybierze dyscyplinę autorowi, który nie ma przypisania na
rok pracy, przy tworzeniu rekordu powstaje ``Autor_Dyscyplina`` z wpisem
w historii (użytkownik = operator importu).
"""

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from model_bakery import baker
from reversion.models import Version

from bpp.models import Autor, Autor_Dyscyplina
from importer_publikacji.models import ImportedAuthor
from importer_publikacji.tests.test_views_create_publication import (
    _make_session_for_publication,
)
from importer_publikacji.views import _create_publication

ROK = 2024  # rok z _make_session_for_publication


@pytest.fixture
def sesja(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    sesja = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        statusy_korekt,
        typy_odpowiedzialnosci,
    )
    sesja.normalized_data["title"] = "Ochrona ludności. Zarys systemu"
    sesja.save()
    return sesja


@pytest.fixture
def autor():
    return baker.make(Autor, nazwisko="Gromek", imiona="Paweł")


def _dopasuj(sesja, autor, jednostka, dyscyplina):
    return baker.make(
        ImportedAuthor,
        session=sesja,
        order=0,
        family_name="Gromek",
        given_name="Paweł",
        match_status=ImportedAuthor.MatchStatus.MANUAL,
        matched_autor=autor,
        matched_jednostka=jednostka,
        matched_dyscyplina=dyscyplina,
        zapisany_jako="Gromek Paweł",
    )


def _wpisy(obj):
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(obj),
        object_id=str(obj.pk),
    )


@pytest.mark.django_db
def test_autor_bez_przypisania_dostaje_dyscypline_na_rok_pracy(
    sesja, autor, jednostka, dyscyplina1
):
    _dopasuj(sesja, autor, jednostka, dyscyplina1)
    operator = baker.make(
        "bpp.BppUser", username="jbihalowicz", first_name="Jan", last_name="Bihałowicz"
    )

    record = _create_publication(sesja, operator)

    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=ROK)
    assert ad.dyscyplina_naukowa == dyscyplina1
    assert ad.subdyscyplina_naukowa is None
    assert record.autorzy_set.get().dyscyplina_naukowa == dyscyplina1

    komunikat = (
        f"Przypisano dyscyplinę „{dyscyplina1}” na rok {ROK} przez użytkownika "
        f"Jan Bihałowicz (jbihalowicz) podczas importu pracy „Ochrona ludności. "
        f"Zarys systemu” (sesja importu #{sesja.pk}, rekord #{record.pk})"
    )
    wpis_ad = _wpisy(ad).get()
    assert wpis_ad.action_flag == ADDITION
    assert wpis_ad.user == operator
    assert wpis_ad.change_message == komunikat

    wpis_autora = _wpisy(autor).get()
    assert wpis_autora.action_flag == CHANGE
    assert wpis_autora.user == operator
    assert wpis_autora.change_message == komunikat

    wersja = Version.objects.get_for_object(autor).first()
    assert wersja.revision.user == operator
    assert wersja.revision.comment == komunikat


@pytest.mark.django_db
def test_bez_usera_historia_w_imieniu_tworcy_sesji(
    sesja, autor, jednostka, dyscyplina1, importer_user
):
    _dopasuj(sesja, autor, jednostka, dyscyplina1)

    _create_publication(sesja)

    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=ROK)
    assert _wpisy(ad).get().user == importer_user


@pytest.mark.django_db
def test_autor_z_przypisaniem_na_rok_bez_zmian(
    sesja, autor, jednostka, dyscyplina1, dyscyplina2
):
    """Autor MA przypisanie na rok pracy — importer go nie rusza."""
    ad = Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=ROK,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )
    _dopasuj(sesja, autor, jednostka, dyscyplina2)

    record = _create_publication(sesja)

    assert list(Autor_Dyscyplina.objects.filter(autor=autor)) == [ad]
    assert not _wpisy(ad).exists()
    assert not _wpisy(autor).exists()
    assert record.autorzy_set.get().dyscyplina_naukowa == dyscyplina2


@pytest.mark.django_db
def test_autor_bez_dyscypliny_w_imporcie_bez_przypisania(sesja, autor, jednostka):
    _dopasuj(sesja, autor, jednostka, None)

    _create_publication(sesja)

    assert not Autor_Dyscyplina.objects.filter(autor=autor).exists()


@pytest.mark.django_db
def test_wiersz_autora_informuje_o_przypisaniu(sesja, autor, jednostka, dyscyplina1):
    imported = _dopasuj(sesja, autor, jednostka, dyscyplina1)
    ctx = {"session": sesja, "author": imported}

    html = render_to_string("importer_publikacji/partials/author_row.html", ctx)
    assert f"przypiszę na rok {ROK}" in html

    Autor_Dyscyplina.objects.create(
        autor=autor, rok=ROK, dyscyplina_naukowa=dyscyplina1
    )
    html = render_to_string("importer_publikacji/partials/author_row.html", ctx)
    assert "przypiszę na rok" not in html


def test_modal_wysyla_id_autora_jako_napis_i_prosi_o_propozycje():
    """Strażnik przyczyny zgłoszenia: forward z modala ma ID autora jako
    napis i flagę ``typowe`` (propozycja dla autora bez przypisania)."""
    from pathlib import Path

    import importer_publikacji

    szablon = (
        Path(importer_publikacji.__file__).parent
        / "templates/importer_publikacji/partials/step_authors.html"
    ).read_text()
    assert "autor: String(autorId), rok: String(rok), typowe: true" in szablon
    assert "modal-dyscyplina-brak-przypisania" in szablon
