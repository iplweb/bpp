"""FD#443 — zapis zwrotny na zgłoszeniu po udanym imporcie.

Po ``COMPLETED`` zgłoszenie ma dostać status ``ZAIMPORTOWANY``, znacznik
czasu, operatora (``session.created_by``, nie ``modified_by``) oraz
GenericFK do utworzonego rekordu.

Testy sprawdzają dwie warstwy:

* jednostkowo ``zgloszenia.oznacz_jako_zaimportowane`` (idempotencja,
  soft-delete, brak wiązania, faktyczny zapis GenericFK do bazy),
* integracyjnie ``tasks.create_publication_task`` (gałąź sukcesu vs
  gałąź błędu, ponowienie zadania).
"""

from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from importer_publikacji.models import ImportSession
from importer_publikacji.tasks import create_publication_task
from importer_publikacji.zgloszenia import oznacz_jako_zaimportowane

STATUS_NOWY = 0
STATUS_ZAIMPORTOWANY = 6


def _zgl(status=STATUS_NOWY, **kwargs):
    return baker.make(
        "zglos_publikacje.Zgloszenie_Publikacji",
        doi="10.1234/fd443.zapis",
        tytul_oryginalny="Praca zgłoszona przez formularz zgłoszeniowy",
        status=status,
        rok=2024,
        rodzaj_zglaszanej_publikacji=1,
        **kwargs,
    )


def _sesja(user, zgloszenie=None, status=ImportSession.Status.REVIEW, **kwargs):
    return ImportSession.objects.create(
        created_by=user,
        provider_name="CrossRef",
        identifier="10.1234/fd443.zapis",
        status=status,
        raw_data={},
        normalized_data={
            "title": "Praca zgłoszona przez formularz zgłoszeniowy",
            "doi": "10.1234/fd443.zapis",
            "year": 2024,
            "authors": [],
        },
        zgloszenie=zgloszenie,
        **kwargs,
    )


def _rekord():
    return baker.make(Wydawnictwo_Ciagle, rok=2024)


@pytest.fixture
def rekord(db):
    return _rekord()


# --------------------------------------------------------------------------
# oznacz_jako_zaimportowane — jednostkowo
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_oznacza_status_date_i_operatora(importer_user, rekord):
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)

    assert oznacz_jako_zaimportowane(session, rekord) is True

    zgl.refresh_from_db()
    assert zgl.status == STATUS_ZAIMPORTOWANY
    assert zgl.zaimportowano is not None
    assert zgl.zaimportowal_id == importer_user.pk


@pytest.mark.django_db
def test_zaimportowal_z_created_by_nie_modified_by(
    importer_user, django_user_model, rekord
):
    """„Kto to zrobił" = kto uruchomił import, nie kto ostatnio dotknął."""
    inny = baker.make(django_user_model)
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)
    session.modified_by = inny
    session.save(update_fields=["modified_by"])

    oznacz_jako_zaimportowane(session, rekord)

    zgl.refresh_from_db()
    assert zgl.zaimportowal_id == importer_user.pk
    assert zgl.zaimportowal_id != inny.pk


@pytest.mark.django_db
def test_generic_fk_faktycznie_zapisany_w_bazie(importer_user, rekord):
    """``update_fields`` MUSI zawierać ``content_type`` i ``object_id``.

    Sam atrybut ``odpowiednik_w_bpp`` w pamięci nic nie dowodzi — GenericFK
    zapisuje się przez dwie kolumny; pominięcie ich w ``update_fields``
    zostawiłoby w bazie NULL-e.
    """
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)

    oznacz_jako_zaimportowane(session, rekord)

    z_bazy = type(zgl).objects.get(pk=zgl.pk)
    assert z_bazy.object_id == rekord.pk
    assert z_bazy.content_type == ContentType.objects.get_for_model(rekord)
    assert z_bazy.odpowiednik_w_bpp == rekord


@pytest.mark.django_db
def test_idempotencja_drugie_wywolanie_nic_nie_zmienia(
    importer_user, django_user_model, rekord
):
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)

    assert oznacz_jako_zaimportowane(session, rekord) is True
    zgl.refresh_from_db()
    data_pierwsza = zgl.zaimportowano
    operator_pierwszy = zgl.zaimportowal_id

    # Ponowienie zadania pod innym userem i z innym rekordem — guard
    # statusu ma zablokować przestemplowanie audytu.
    session.created_by = baker.make(django_user_model)
    session.save(update_fields=["created_by"])
    session = ImportSession.objects.get(pk=session.pk)

    assert oznacz_jako_zaimportowane(session, _rekord()) is False

    zgl.refresh_from_db()
    assert zgl.zaimportowano == data_pierwsza
    assert zgl.zaimportowal_id == operator_pierwszy
    assert zgl.object_id == rekord.pk


def _soft_usun_bez_kaskady(zgl):
    """Ustaw ``deleted_at`` z pominięciem ``instance.delete()``.

    ``django_softdelete`` w ``delete()`` emuluje ``on_delete`` relacji
    odwrotnych — dla ``ImportSession.zgloszenie`` (``SET_NULL``) zeruje
    FK, więc zwykłe ``zgl.delete()`` NIE ustawia sceny dla guardu
    ``deleted_at``. Wiersz z ``deleted_at`` i żywym FK powstaje na
    ścieżkach omijających ``delete()``: ``UPDATE`` z migracji danych,
    surowy SQL, wyścig między dwoma transakcjami. Guard jest dokładnie
    dla nich — i to sprawdza ten helper.
    """
    from django.utils import timezone

    type(zgl).global_objects.filter(pk=zgl.pk).update(deleted_at=timezone.now())


@pytest.mark.django_db
def test_soft_usuniete_zgloszenie_nie_zostaje_oznaczone(importer_user, rekord):
    """Dostęp przez FK idzie ``_base_manager`` — nie filtruje usuniętych."""
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)
    _soft_usun_bez_kaskady(zgl)

    # Świeży odczyt: FK i tak zwróci soft-usunięty wiersz.
    session = ImportSession.objects.get(pk=session.pk)
    assert session.zgloszenie is not None
    assert session.zgloszenie.deleted_at is not None

    assert oznacz_jako_zaimportowane(session, rekord) is False

    z_bazy = type(zgl).global_objects.get(pk=zgl.pk)
    assert z_bazy.status == STATUS_NOWY
    assert z_bazy.zaimportowano is None
    assert z_bazy.object_id is None


@pytest.mark.django_db
def test_skasowanie_zgloszenia_zeruje_wiazanie_sesji(importer_user, rekord):
    """Charakteryzacja: ``zgl.delete()`` zeruje ``ImportSession.zgloszenie``.

    ``django_softdelete`` emuluje ``on_delete=SET_NULL`` przy soft-delete,
    więc typowa ścieżka (operator kasuje zgłoszenie w module redagowania)
    rozbraja wiązanie jeszcze przed guardem ``deleted_at``. Efekt netto
    jest ten sam — zgłoszenie nie zostaje oznaczone.
    """
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)

    zgl.delete()

    session = ImportSession.objects.get(pk=session.pk)
    assert session.zgloszenie_id is None
    assert oznacz_jako_zaimportowane(session, rekord) is False

    z_bazy = type(zgl).global_objects.get(pk=zgl.pk)
    assert z_bazy.status == STATUS_NOWY


@pytest.mark.django_db
def test_brak_wiazania_to_no_op(importer_user, rekord):
    session = _sesja(importer_user, zgloszenie=None)

    assert oznacz_jako_zaimportowane(session, rekord) is False


# --------------------------------------------------------------------------
# create_publication_task — integracyjnie
# --------------------------------------------------------------------------


def _uruchom_task(session):
    rekord = _rekord()
    with patch("importer_publikacji.tasks._create_publication") as mock_create:
        mock_create.return_value = rekord
        create_publication_task.apply(
            args=[session.pk, session.created_by_id, False]
        ).get()
    return rekord


@pytest.mark.django_db
def test_task_oznacza_zgloszenie_po_completed(importer_user):
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)

    rekord = _uruchom_task(session)

    session.refresh_from_db()
    assert session.status == ImportSession.Status.COMPLETED

    zgl.refresh_from_db()
    assert zgl.status == STATUS_ZAIMPORTOWANY
    assert zgl.zaimportowano is not None
    assert zgl.zaimportowal_id == importer_user.pk
    assert zgl.odpowiednik_w_bpp == rekord


@pytest.mark.django_db
def test_task_bez_wiazania_nie_rusza_zadnego_zgloszenia(importer_user):
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=None)

    _uruchom_task(session)

    zgl.refresh_from_db()
    assert zgl.status == STATUS_NOWY
    assert zgl.zaimportowano is None


@pytest.mark.django_db
def test_task_zakonczony_bledem_nie_zmienia_statusu_zgloszenia(importer_user):
    """Zapis zwrotny siedzi w gałęzi sukcesu, przed blokiem ``except``."""
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)

    with patch("importer_publikacji.tasks._create_publication") as mock_create:
        mock_create.side_effect = RuntimeError("create exploded")
        with pytest.raises(RuntimeError, match="create exploded"):
            create_publication_task.apply(
                args=[session.pk, session.created_by_id, False]
            ).get()

    session.refresh_from_db()
    assert session.status == ImportSession.Status.IMPORT_FAILED

    zgl.refresh_from_db()
    assert zgl.status == STATUS_NOWY
    assert zgl.zaimportowano is None
    assert zgl.zaimportowal_id is None
    assert zgl.object_id is None


@pytest.mark.django_db
def test_ponowienie_taska_nie_przesuwa_daty(importer_user):
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)

    pierwszy_rekord = _uruchom_task(session)
    zgl.refresh_from_db()
    data_pierwsza = zgl.zaimportowano

    session.status = ImportSession.Status.REVIEW
    session.save(update_fields=["status"])
    _uruchom_task(session)

    zgl.refresh_from_db()
    assert zgl.zaimportowano == data_pierwsza
    assert zgl.odpowiednik_w_bpp == pierwszy_rekord


@pytest.mark.django_db
def test_task_pomija_soft_usuniete_zgloszenie(importer_user):
    """Soft-delete w trakcie importu → rekord powstaje, zgłoszenie nietknięte."""
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)
    _soft_usun_bez_kaskady(zgl)

    _uruchom_task(session)

    session.refresh_from_db()
    assert session.status == ImportSession.Status.COMPLETED

    z_bazy = type(zgl).global_objects.get(pk=zgl.pk)
    assert z_bazy.status == STATUS_NOWY
    assert z_bazy.zaimportowano is None
