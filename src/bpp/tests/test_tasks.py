from datetime import timedelta
from unittest.mock import Mock

import pytest
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from bpp.models import Wydawnictwo_Ciagle
from bpp.tasks import (
    AXES_ACCESSATTEMPT_RETENTION_DAYS,
    EASYAUDIT_LOGINEVENT_RETENTION_MONTHS,
    _zaktualizuj_liczbe_cytowan,
    remove_file,
    usun_stare_logi_logowania_easyaudit,
    usun_stare_proby_logowania_axes,
)


@pytest.fixture
def report_media(settings, tmp_path):
    """MEDIA_ROOT wskazujący na tmp_path z gotowym katalogiem ``report``."""
    settings.MEDIA_ROOT = str(tmp_path)
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    return tmp_path, report_dir


def test_remove_file_usuwa_plik_z_katalogu_raportow(report_media):
    _, report_dir = report_media
    plik = report_dir / "raport.pdf"
    plik.write_text("dane")

    remove_file(str(plik))

    assert not plik.exists()


def test_remove_file_odrzuca_rodzenstwo_o_wspolnym_prefiksie(report_media):
    """`…/report-evil/x` NIE może zostać usunięte przez startswith('report')."""
    root, _ = report_media
    evil_dir = root / "report-evil"
    evil_dir.mkdir()
    plik = evil_dir / "x.pdf"
    plik.write_text("nie ruszaj")

    remove_file(str(plik))

    assert plik.exists()


def test_remove_file_odrzuca_traversal(report_media):
    """`…/report/../secret` wychodzi poza katalog raportów — odrzucone."""
    root, report_dir = report_media
    secret = root / "secret.txt"
    secret.write_text("tajne")

    remove_file(str(report_dir / ".." / "secret.txt"))

    assert secret.exists()


def test_remove_file_odrzuca_symlink_poza_katalog(report_media):
    """Symlink w katalogu raportów wskazujący na plik na zewnątrz — odrzucony
    (``resolve()`` rozwiązuje dowiązanie zanim sprawdzimy przynależność)."""
    root, report_dir = report_media
    secret = root / "secret.txt"
    secret.write_text("tajne")
    link = report_dir / "link.pdf"
    link.symlink_to(secret)

    remove_file(str(link))

    assert secret.exists()


def test_remove_file_brak_pliku_nie_jest_bledem(report_media):
    """Idempotencja: nieistniejący plik w katalogu raportów nie rzuca."""
    _, report_dir = report_media
    remove_file(str(report_dir / "nie-ma-mnie.pdf"))  # nie powinno rzucić


def test_remove_file_nie_kasuje_samego_katalogu(report_media):
    _, report_dir = report_media
    remove_file(str(report_dir))
    assert report_dir.exists()


@pytest.mark.django_db
def test_zaktualizuj_liczbe_cytowan(uczelnia, wydawnictwo_ciagle, mocker):
    # Rekord musi mieć DOI+PMID, żeby wszedł do korpusu odpytywanego w WoS.
    wydawnictwo_ciagle.doi = "10.1234/test"
    wydawnictwo_ciagle.pubmed_id = "12345"
    wydawnictwo_ciagle.save()

    m = Mock()
    m.query_multiple = Mock(
        return_value=[{wydawnictwo_ciagle.pk: {"timesCited": "31337"}}]
    )

    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    _zaktualizuj_liczbe_cytowan(
        [
            Wydawnictwo_Ciagle,
        ]
    )

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.liczba_cytowan == 31337


@pytest.mark.django_db
def test_zaktualizuj_liczbe_cytowan_bulk_wiele_rekordow(uczelnia, mocker):
    """Wiele rekordów aktualizowanych jednym przebiegiem (bulk_update),
    korpus odpytany raz — bez get()/save() per rekord."""
    from model_bakery import baker

    rekordy = [
        baker.make(
            Wydawnictwo_Ciagle,
            doi=f"10.1/{i}",
            pubmed_id=str(1000 + i),
            liczba_cytowan=0,
        )
        for i in range(3)
    ]

    odpowiedz = {r.pk: {"timesCited": str(10 + idx)} for idx, r in enumerate(rekordy)}
    m = Mock()
    m.query_multiple = Mock(return_value=[odpowiedz])
    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    _zaktualizuj_liczbe_cytowan([Wydawnictwo_Ciagle])

    # Korpus odpytany dokładnie raz (jeden klient WoS), nie per-rekord.
    assert m.query_multiple.call_count == 1
    for idx, r in enumerate(rekordy):
        r.refresh_from_db()
        assert r.liczba_cytowan == 10 + idx


@pytest.mark.django_db
def test_usun_stare_logi_logowania_easyaudit():
    """Kasuje LoginEvent starsze niż 24 mies., zostawia nowsze, nie rusza
    CRUDEvent (historia edycji)."""
    from django.contrib.contenttypes.models import ContentType
    from easyaudit.models import CRUDEvent, LoginEvent

    now = timezone.now()
    stary = LoginEvent.objects.create(login_type=LoginEvent.LOGIN, username="a")
    nowy = LoginEvent.objects.create(login_type=LoginEvent.LOGIN, username="b")
    crud = CRUDEvent.objects.create(
        event_type=CRUDEvent.CREATE,
        object_repr="x",
        object_id=1,
        # content_type_id na sztywno łamie się po pierwszym flushu na workerze
        # (content types odtwarzają się na zjitterowanych sekwencjach) — bierzemy
        # realny ContentType istniejącego modelu.
        content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
    )
    # auto_now_add ustawia datetime na teraz — przestawiamy ręcznie przez update()
    cutoff = now - relativedelta(months=EASYAUDIT_LOGINEVENT_RETENTION_MONTHS)
    LoginEvent.objects.filter(pk=stary.pk).update(datetime=cutoff - timedelta(days=1))
    LoginEvent.objects.filter(pk=nowy.pk).update(datetime=now - timedelta(days=1))

    deleted = usun_stare_logi_logowania_easyaudit()

    assert deleted == 1
    assert not LoginEvent.objects.filter(pk=stary.pk).exists()
    assert LoginEvent.objects.filter(pk=nowy.pk).exists()
    # CRUDEvent nietknięty
    assert CRUDEvent.objects.filter(pk=crud.pk).exists()


@pytest.mark.django_db
def test_usun_stare_proby_logowania_axes():
    """Kasuje AccessAttempt starsze niż retencja, zostawia świeże i nie rusza
    AccessLog (udane logowania)."""
    from axes.models import AccessAttempt, AccessLog

    now = timezone.now()

    def _attempt(username):
        return AccessAttempt.objects.create(
            username=username,
            ip_address="10.0.0.1",
            user_agent="bot",
            get_data="",
            post_data="",
            failures_since_start=1,
        )

    stary = _attempt("bot-skanujacy")
    nowy = _attempt("swiezy")
    log = AccessLog.objects.create(
        username="ktos", ip_address="10.0.0.2", user_agent="firefox"
    )

    # attempt_time to auto_now_add — przestawiamy ręcznie przez update()
    cutoff = now - timedelta(days=AXES_ACCESSATTEMPT_RETENTION_DAYS)
    AccessAttempt.objects.filter(pk=stary.pk).update(
        attempt_time=cutoff - timedelta(days=1)
    )
    AccessAttempt.objects.filter(pk=nowy.pk).update(
        attempt_time=now - timedelta(days=1)
    )

    deleted = usun_stare_proby_logowania_axes()

    assert deleted == 1
    assert not AccessAttempt.objects.filter(pk=stary.pk).exists()
    assert AccessAttempt.objects.filter(pk=nowy.pk).exists()
    # AccessLog (udane logowania) nietknięty
    assert AccessLog.objects.filter(pk=log.pk).exists()


@pytest.mark.django_db
def test_usun_stare_proby_logowania_axes_respektuje_parametr_days():
    """Parametr `days` przesuwa próg — ten sam wpis raz przeżywa, raz nie."""
    from axes.models import AccessAttempt

    attempt = AccessAttempt.objects.create(
        username="bot",
        ip_address="10.0.0.1",
        user_agent="bot",
        get_data="",
        post_data="",
        failures_since_start=1,
    )
    AccessAttempt.objects.filter(pk=attempt.pk).update(
        attempt_time=timezone.now() - timedelta(days=10)
    )

    # Retencja 30 dni — wpis 10-dniowy zostaje.
    assert usun_stare_proby_logowania_axes(days=30) == 0
    assert AccessAttempt.objects.filter(pk=attempt.pk).exists()

    # Retencja 5 dni — ten sam wpis wypada.
    assert usun_stare_proby_logowania_axes(days=5) == 1
    assert not AccessAttempt.objects.filter(pk=attempt.pk).exists()
