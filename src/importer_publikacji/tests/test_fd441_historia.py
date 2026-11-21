"""FD#441: rekord utworzony przez importer publikacji zostawia ślad na
stronie „Historia" w adminie (``LogEntry`` ADDITION w imieniu importującego,
z informacją o sesji i źródle danych)."""

import pytest
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from bpp.models import Autor, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from importer_publikacji.historia import komunikat_utworzenia
from importer_publikacji.models import ImportSession
from importer_publikacji.tasks import create_publication_task
from importer_publikacji.tests.test_views_authors import (
    _make_session_with_unmatched,
)
from importer_publikacji.tests.test_views_create_publication import (
    _make_session_for_publication,
)
from importer_publikacji.views import _create_publication


@pytest.fixture
def sesja(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    return _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        statusy_korekt,
        typy_odpowiedzialnosci,
    )


def _wpisy(obj):
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(obj),
        object_id=str(obj.pk),
    )


def test_komunikat_utworzenia_bez_zgloszenia():
    sesja = ImportSession(pk=12, provider_name="CrossRef")
    assert komunikat_utworzenia(sesja) == (
        "Utworzono przez importer publikacji (sesja #12, źródło: CrossRef)"
    )


def test_komunikat_utworzenia_ze_zgloszeniem():
    sesja = ImportSession(pk=12, provider_name="PBN", zgloszenie_id=34)
    assert komunikat_utworzenia(sesja) == (
        "Utworzono przez importer publikacji (sesja #12, źródło: PBN, zgłoszenie #34)"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "zwarte,model", [(False, Wydawnictwo_Ciagle), (True, Wydawnictwo_Zwarte)]
)
def test_create_publication_zapisuje_logentry(sesja, zwarte, model):
    sesja.jest_wydawnictwem_zwartym = zwarte
    sesja.save()
    inny = baker.make("bpp.BppUser")

    record = _create_publication(sesja, inny)

    assert isinstance(record, model)
    wpis = _wpisy(record).get()
    assert wpis.action_flag == ADDITION
    assert wpis.user == inny
    assert wpis.change_message == (
        f"Utworzono przez importer publikacji (sesja #{sesja.pk}, źródło: CrossRef)"
    )


@pytest.mark.django_db
def test_create_publication_bez_usera_bierze_tworce_sesji(sesja, importer_user):
    record = _create_publication(sesja)

    assert _wpisy(record).get().user == importer_user


@pytest.mark.django_db
def test_create_publication_task_zapisuje_logentry_w_imieniu_zlecajacego(sesja):
    zlecajacy = baker.make("bpp.BppUser")

    create_publication_task.apply(args=[sesja.pk, zlecajacy.pk, False]).get()

    sesja.refresh_from_db()
    record = sesja.created_record
    wpis = _wpisy(record).get()
    assert wpis.action_flag == ADDITION
    assert wpis.user == zlecajacy
    assert f"sesja #{sesja.pk}" in wpis.change_message


@pytest.mark.django_db
def test_historia_w_adminie_pokazuje_wpis_importera(sesja, importer_user, admin_client):
    record = _create_publication(sesja)

    res = admin_client.get(
        reverse("admin:bpp_wydawnictwo_ciagle_history", args=[record.pk])
    )

    assert res.status_code == 200
    tresc = res.content.decode()
    assert f"Utworzono przez importer publikacji (sesja #{sesja.pk}" in tresc
    assert importer_user.username in tresc


@pytest.mark.django_db
def test_autor_utworzony_przez_importer_ma_historie(
    importer_client, importer_user, uczelnia_z_obca_jednostka, admin_client
):
    sesja = _make_session_with_unmatched(importer_user, count=1)

    res = importer_client.post(
        reverse(
            "importer_publikacji:authors-create-unmatched",
            kwargs={"session_id": sesja.pk},
        )
    )
    assert res.status_code == 200

    autor = Autor.objects.get(nazwisko="Testowy0")
    komunikat = komunikat_utworzenia(sesja)
    wpis = _wpisy(autor).get()
    assert wpis.action_flag == ADDITION
    assert wpis.user == importer_user
    assert wpis.change_message == komunikat

    wersja = Version.objects.get_for_object(autor).get()
    assert wersja.revision.comment == komunikat
    assert wersja.revision.user == importer_user

    res = admin_client.get(reverse("admin:bpp_autor_history", args=[autor.pk]))
    assert res.status_code == 200
    assert komunikat in res.content.decode()
