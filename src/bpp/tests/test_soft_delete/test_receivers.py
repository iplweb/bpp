"""Receivery sygnałów soft-delete → ``SoftDeleteLog`` (faza 06)."""

from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django_softdelete.signals import post_hard_delete
from model_bakery import baker

from bpp.models.soft_delete_context import soft_delete_context
from bpp.models.soft_delete_log import SoftDeleteLog


@pytest.fixture
def bez_celery():
    """Kolejkowanie odpala ``task_sprobuj_wyslac_do_pbn.delay()``, a testy
    biegną z ``CELERY_TASK_ALWAYS_EAGER`` — bez tego wysyłka do PBN
    wykonałaby się synchronicznie, w środku ``delete()``.
    """
    with patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn") as mock_task:
        yield mock_task


def _z_pbn_uid(rekord):
    from pbn_api.models import Publication

    rekord.pbn_uid = baker.make(Publication)
    rekord.save()
    return rekord


def _logi(instance, akcja):
    return SoftDeleteLog.objects.filter(
        content_type=ContentType.objects.get_for_model(instance),
        object_id=instance.pk,
        akcja=akcja,
    )


@pytest.mark.django_db
def test_pakiet_zeruje_pk_przed_wyslaniem_post_hard_delete(wydawnictwo_ciagle):
    """Fakt o pakiecie, na którym opiera się cała obsługa HARD_DELETE.

    ``SoftDeleteModel.hard_delete()`` woła ``Model.delete()``, a kolektor
    Django na koniec zeruje ``pk`` skasowanych instancji — ``post_hard_delete``
    leci PO tym. Receiver nie ma więc z czego wziąć ``object_id`` i musi
    dostać ``pk`` zapamiętany wcześniej.

    Ten test jest strażnikiem założenia: gdyby aktualizacja pakietu
    przestawiła kolejność (sygnał przed zerowaniem), zapali się tutaj,
    a nie w postaci logów z ``object_id`` wziętym z zapasowego pola.
    """
    zebrane = []

    def _sonda(sender, instance, **kwargs):
        zebrane.append(instance.pk)

    post_hard_delete.connect(_sonda, dispatch_uid="test.sonda.pk", weak=False)
    try:
        wydawnictwo_ciagle.hard_delete()
    finally:
        post_hard_delete.disconnect(dispatch_uid="test.sonda.pk")

    assert zebrane == [None], (
        "Pakiet zaczął wysyłać post_hard_delete z niewyzerowanym pk — "
        "stash pk w BppPkPrzedHardDeleteMixin można wtedy uprościć."
    )


def test_kazdy_model_soft_delete_zachowuje_pk():
    """KAŻDY model soft-delete musi mieć ``BppPkPrzedHardDeleteMixin``.

    Bez niego ``post_hard_delete`` dostaje instancję z ``pk is None``,
    a ``pk_dla_audytu()`` rzuca ``RuntimeError`` — czyli twarde skasowanie
    takiego modelu przewróciłoby się w produkcji. Ten test przenosi wykrycie
    z produkcji do testów: nowy model soft-delete zapala się TUTAJ.
    """
    from django.apps import apps
    from django_softdelete.models import SoftDeleteModel

    from bpp.models.soft_delete import BppPkPrzedHardDeleteMixin

    bez_mixinu = [
        model._meta.label
        for model in apps.get_models()
        if issubclass(model, SoftDeleteModel)
        and not issubclass(model, BppPkPrzedHardDeleteMixin)
    ]
    assert bez_mixinu == [], (
        "Modele soft-delete bez BppPkPrzedHardDeleteMixin — ich hard_delete() "
        f"wywali sie na pk_dla_audytu(): {bez_mixinu}"
    )


@pytest.mark.django_db
def test_hard_delete_tworzy_log(wydawnictwo_ciagle, superuser):
    pk = wydawnictwo_ciagle.pk
    ct = ContentType.objects.get_for_model(wydawnictwo_ciagle)
    with soft_delete_context(user=superuser, reason="trwałe"):
        wydawnictwo_ciagle.hard_delete()
    log = SoftDeleteLog.objects.get(
        content_type=ct, object_id=pk, akcja=SoftDeleteLog.Akcja.HARD_DELETE
    )
    assert log.user == superuser
    assert log.powod == "trwałe"
    assert log.pbn_queue_entry is None


@pytest.mark.django_db
def test_soft_delete_tworzy_log_z_userem(wydawnictwo_ciagle, superuser):
    """Wariant z jawnym kontekstem — tak woła kod bez własnego ``delete()``."""
    with soft_delete_context(user=superuser, reason="duplikat"):
        wydawnictwo_ciagle.delete()
    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.DELETE).get()
    assert log.user == superuser
    assert log.powod == "duplikat"


@pytest.mark.django_db
def test_soft_delete_bez_usera_loguje_none(wydawnictwo_ciagle):
    """Operacja bez zalogowanego usera (celery, skrypt, scalanie duplikatów).

    ``user=None`` jest POPRAWNYM wynikiem, nie awarią — „nie wiadomo kto"
    jest uczciwsze niż podstawienie pierwszego lepszego konta.
    """
    wydawnictwo_ciagle.delete()
    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.DELETE).get()
    assert log.user is None
    assert log.powod == ""


@pytest.mark.django_db
def test_delete_z_argumentem_user_loguje_usera(wydawnictwo_ciagle, superuser):
    """REALNE API: ``delete(user=, reason=)``, bez ręcznego kontekstu.

    Fazy 02/04 przyjmowały te argumenty i je porzucały („konsumuje je
    SoftDeleteLog z fazy 06"). Ten test pilnuje, że faza 06 domknęła
    obietnicę — bez niego cały mechanizm atrybucji działałby wyłącznie dla
    wołających, którzy sami wejdą w context manager, czyli dla nikogo.
    """
    wydawnictwo_ciagle.delete(user=superuser, reason="zdublowany import")
    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.DELETE).get()
    assert log.user == superuser
    assert log.powod == "zdublowany import"


@pytest.mark.django_db
def test_restore_z_argumentem_user_loguje_usera(wydawnictwo_ciagle, superuser):
    wydawnictwo_ciagle.delete(user=superuser, reason="pomyłka")
    wydawnictwo_ciagle.restore(user=superuser)
    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.RESTORE).get()
    assert log.user == superuser


@pytest.mark.django_db
def test_autor_delete_z_userem_loguje_usera(autor_jan_kowalski, superuser):
    """``Autor`` ma własny ``delete()`` (faza 04) — osobna ścieżka do wpięcia."""
    autor_jan_kowalski.delete(user=superuser, reason="duplikat osoby")
    log = _logi(autor_jan_kowalski, SoftDeleteLog.Akcja.DELETE).get()
    assert log.user == superuser
    assert log.powod == "duplikat osoby"


@pytest.mark.django_db
def test_kaskada_autorstw_dziedziczy_usera(wydawnictwo_ciagle_z_autorem, superuser):
    """Kaskada ``*_Autor`` loguje się z tym samym userem i powodem.

    Soft-delete publikacji z N autorami emituje 1 + N sygnałów, bo wąska
    kaskada fazy 02 kasuje każdy wiersz osobno. Log jest wierny sygnałom:
    powstaje wpis dla rekordu i dla każdego autorstwa. Atrybucja przenosi
    się przez reentrancję context managera — gdyby zawiodła, wiersze
    ``*_Autor`` miałyby ``user=None`` mimo świadomej decyzji operatora.
    """
    from bpp.models import Wydawnictwo_Ciagle_Autor

    autorstwo = wydawnictwo_ciagle_z_autorem.autorzy_set.get()
    wydawnictwo_ciagle_z_autorem.delete(user=superuser, reason="wycofany artykuł")

    log_rekordu = _logi(wydawnictwo_ciagle_z_autorem, SoftDeleteLog.Akcja.DELETE).get()
    assert log_rekordu.user == superuser

    log_autorstwa = SoftDeleteLog.objects.get(
        content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle_Autor),
        object_id=autorstwo.pk,
        akcja=SoftDeleteLog.Akcja.DELETE,
    )
    assert log_autorstwa.user == superuser
    assert log_autorstwa.powod == "wycofany artykuł"


# --- Task 6: kolejkowanie PBN z receiverów -----------------------------


@pytest.mark.django_db
def test_soft_delete_z_pbn_uid_kolejkuje_wycofanie(
    wydawnictwo_ciagle, superuser, bez_celery
):
    from pbn_export_queue.models import PBN_Export_Queue

    _z_pbn_uid(wydawnictwo_ciagle)
    wydawnictwo_ciagle.delete(user=superuser, reason="x")

    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.DELETE).get()
    assert log.pbn_queue_entry is not None
    assert log.pbn_status == "WYCOFANIE"
    assert log.pbn_queue_entry.operacja == PBN_Export_Queue.Operacja.WYCOFANIE
    assert log.pbn_queue_entry.zamowil == superuser


@pytest.mark.django_db
def test_soft_delete_bez_pbn_uid_nie_kolejkuje(wydawnictwo_ciagle, superuser):
    """Bez PBN UID nic do PBN nie pojechało, więc nie ma czego wycofywać."""
    wydawnictwo_ciagle.delete(user=superuser)

    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.DELETE).get()
    assert log.pbn_queue_entry is None
    assert log.pbn_status == ""


@pytest.mark.django_db
def test_restore_kolejkuje_wysylke(wydawnictwo_ciagle, superuser, bez_celery):
    """RESTORE kolejkuje wysyłkę także BEZ ``pbn_uid``.

    ``zakolejkuj_wysylke`` świadomie nie ma gate'u na ``pbn_uid`` (faza 05a):
    rekord, który nigdy nie był w PBN, po przywróceniu ma prawo pojechać —
    wysyłka dopiero nadaje UID.
    """
    from pbn_export_queue.models import PBN_Export_Queue

    wydawnictwo_ciagle.delete(user=superuser)
    wydawnictwo_ciagle.restore(user=superuser)

    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.RESTORE).get()
    assert log.pbn_queue_entry is not None
    assert log.pbn_status == "WYSYLKA"
    assert log.pbn_queue_entry.operacja == PBN_Export_Queue.Operacja.WYSYLKA


@pytest.mark.django_db
def test_restore_przy_niezakonczonym_wycofaniu_nie_dubluje_wpisu(
    wydawnictwo_ciagle, superuser, bez_celery
):
    """Przywrócenie, gdy wycofanie WCIĄŻ czeka w kolejce, nie tworzy wpisu.

    ``sprobuj_utowrzyc_wpis`` odrzuca drugi AKTYWNY wpis dla tego samego
    rekordu (``AlreadyEnqueuedError`` → ``None``), więc szybkie
    „usuń i cofnij" zostawia w kolejce samo wycofanie. Log mówi wtedy
    ``pbn_status=""``.

    ⚠️ To ta sama pusta wartość, co przy „nie było czego kolejkować" —
    z samego logu nie odróżnisz „pominięto (już w kolejce)" od
    „nie dotyczy". Świadome uproszczenie: obie funkcje kolejkujące zwracają
    ``None`` i receiver nie ma ich jak rozróżnić bez dodatkowego zapytania.
    """
    _z_pbn_uid(wydawnictwo_ciagle)
    wydawnictwo_ciagle.delete(user=superuser)
    wydawnictwo_ciagle.restore(user=superuser)

    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.RESTORE).get()
    assert log.pbn_queue_entry is None
    assert log.pbn_status == ""


@pytest.mark.django_db
def test_restore_po_zakonczonym_wycofaniu_kolejkuje_wysylke(
    wydawnictwo_ciagle, superuser, bez_celery
):
    """Realna sekwencja: wycofanie przetworzone, potem przywrócenie."""
    from pbn_export_queue.models import PBN_Export_Queue

    _z_pbn_uid(wydawnictwo_ciagle)
    wydawnictwo_ciagle.delete(user=superuser)

    wycofanie = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.DELETE).get()
    wycofanie.pbn_queue_entry.wysylke_zakonczono = timezone.now()
    wycofanie.pbn_queue_entry.save()

    wydawnictwo_ciagle.restore(user=superuser)

    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.RESTORE).get()
    assert log.pbn_status == "WYSYLKA"
    assert log.pbn_queue_entry.operacja == PBN_Export_Queue.Operacja.WYSYLKA


@pytest.mark.django_db
def test_autor_z_pbn_uid_nie_trafia_do_kolejki(
    autor_jan_kowalski, superuser, bez_celery
):
    """``Autor`` MA ``pbn_uid`` — gate na sam atrybut byłby błędny.

    Plan fazy 06 twierdzi (jako fakt zweryfikowany), że „Autor i *_Autor nie
    mają pbn_uid", i na tym opiera uniwersalny gate
    ``getattr(instance, "pbn_uid_id", None)``. W kodzie ``Autor.pbn_uid``
    jest zwykłym FK (``autor.py``), więc tamten gate wstawiłby AUTORA do
    kolejki eksportu PUBLIKACJI i odpalił dla niego wysyłkę do PBN.
    Gate idzie po typie: wyłącznie ``BppPublikacjaSoftDeleteMixin``.
    """
    from pbn_api.models import Scientist
    from pbn_export_queue.models import PBN_Export_Queue

    autor_jan_kowalski.pbn_uid = baker.make(Scientist)
    autor_jan_kowalski.save()
    assert autor_jan_kowalski.pbn_uid_id is not None

    autor_jan_kowalski.delete(user=superuser, reason="duplikat")

    log = _logi(autor_jan_kowalski, SoftDeleteLog.Akcja.DELETE).get()
    assert log.pbn_queue_entry is None
    assert log.pbn_status == ""
    assert not PBN_Export_Queue.objects.exists()
    bez_celery.delay.assert_not_called()


@pytest.mark.django_db
def test_kaskada_autorstw_nie_kolejkuje_osobno(
    wydawnictwo_ciagle_z_autorem, superuser, bez_celery
):
    """Publikacja z N autorami → DOKŁADNIE JEDEN wpis kolejki.

    Kaskada fazy 02 emituje 1 + N sygnałów. Gdyby receiver kolejkował dla
    każdego, powstałoby N zbędnych wpisów dla wierszy ``*_Autor`` — a przy
    RESTORE szczególnie łatwo, bo ``zakolejkuj_wysylke`` nie ma gate'u na
    ``pbn_uid`` i przyjęłaby cokolwiek.
    """
    from pbn_export_queue.models import PBN_Export_Queue

    _z_pbn_uid(wydawnictwo_ciagle_z_autorem)
    wydawnictwo_ciagle_z_autorem.delete(user=superuser)

    assert PBN_Export_Queue.objects.count() == 1
    wpis = PBN_Export_Queue.objects.get()
    assert wpis.rekord_do_wysylki == wydawnictwo_ciagle_z_autorem


# --- Task 6: uczelnia wyprowadzona z rekordu ---------------------------


@pytest.mark.django_db
def test_wpis_kolejki_dostaje_uczelnie_rekordu(
    wydawnictwo_ciagle_z_autorem, uczelnia, superuser, bez_celery
):
    """Wpis z receivera niesie uczelnię — inaczej multi-hosted by go nie wysłał.

    Wszyscy pozostali wołający kolejki biorą uczelnię z requestu
    (``Uczelnia.objects.get_for_request``). Receiver requestu nie ma, więc
    odwraca regułę przynależności z fazy 05b (``naleza_wydawnictwa``):
    uczelnia jednostek autorów rekordu. Bez tego ``_pozyskaj_klienta_pbn``
    spadłby na ``get_single_uczelnia_or_fail()`` i przy dwóch uczelniach
    wycofanie kończyłoby się ``FINISHED_ERROR``.
    """
    from pbn_export_queue.models import PBN_Export_Queue

    _z_pbn_uid(wydawnictwo_ciagle_z_autorem)
    wydawnictwo_ciagle_z_autorem.delete(user=superuser)

    wpis = PBN_Export_Queue.objects.get()
    assert wpis.uczelnia == uczelnia


@pytest.mark.django_db
def test_uczelnia_czytana_mimo_skasowanych_autorstw(
    wydawnictwo_ciagle_z_autorem, uczelnia, superuser, bez_celery
):
    """Atrybucja MUSI iść przez ``global_objects``, nie ``objects``.

    Wąska kaskada fazy 02 kasuje wiersze ``*_Autor`` PRZED wysłaniem
    ``post_soft_delete`` rodzica. Gdy receiver pyta o uczelnię, autorstwa
    są już w koszu — odczyt przez ``objects`` zwróciłby pustkę i uczelnia
    wychodziłaby ``None`` przy KAŻDYM kasowaniu, czyli dokładnie wtedy,
    gdy jest potrzebna.
    """
    from pbn_export_queue.models import PBN_Export_Queue

    _z_pbn_uid(wydawnictwo_ciagle_z_autorem)
    wydawnictwo_ciagle_z_autorem.delete(user=superuser)

    assert not wydawnictwo_ciagle_z_autorem.autorzy_set.exists()
    assert PBN_Export_Queue.objects.get().uczelnia == uczelnia


@pytest.mark.django_db
def test_uczelnia_niejednoznaczna_daje_none(
    wydawnictwo_ciagle_z_autorem,
    autor_uczelnia2,
    jednostka_uczelnia2,
    typy_odpowiedzialnosci,
    superuser,
    bez_celery,
):
    """Praca współautorska między uczelniami → ``uczelnia=None``, nie zgadywanie.

    Wybranie „pierwszej z brzegu" wysłałoby wycofanie przez konto PBN
    niewłaściwego tenanta. ``None`` degraduje do zachowania sprzed fazy 06:
    jedna uczelnia w bazie → działa, kilka → głośny błąd na wpisie kolejki.
    """
    from pbn_export_queue.models import PBN_Export_Queue

    wydawnictwo_ciagle_z_autorem.dodaj_autora(autor_uczelnia2, jednostka_uczelnia2)
    _z_pbn_uid(wydawnictwo_ciagle_z_autorem)
    wydawnictwo_ciagle_z_autorem.delete(user=superuser)

    assert PBN_Export_Queue.objects.get().uczelnia is None


@pytest.mark.django_db
def test_praca_doktorska_bierze_uczelnie_z_jednostki(
    praca_doktorska, uczelnia, superuser, bez_celery
):
    """Prace dyplomowe nie mają through-modelu — atrybucja przez FK jednostki.

    Ta sama dwoistość, którą faza 05b rozstrzygnęła w ``naleza_prace``
    kontra ``naleza_wydawnictwa``.
    """
    from pbn_export_queue.models import PBN_Export_Queue

    _z_pbn_uid(praca_doktorska)
    praca_doktorska.delete(user=superuser)

    assert PBN_Export_Queue.objects.get().uczelnia == uczelnia
