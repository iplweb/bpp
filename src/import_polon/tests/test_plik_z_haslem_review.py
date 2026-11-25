"""Poprawki po przeglądzie: plik z hasłem nie może zostać na serwerze ani dać
się przetworzyć drugi raz żadną ścieżką; uszkodzone/za duże pliki z hasłem
i hasło w raportach błędów."""

import os
import sys
from datetime import timedelta
from unittest import mock

import olefile
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from django.views.debug import ExceptionReporter
from liveops.testing import MockProgress
from model_bakery import baker

from import_polon.models import ImportPlikuAbsencji, ImportPlikuPolon
from import_polon.tasks import (
    usun_zalegle_pliki_z_haslem,
    usun_zalegle_pliki_z_haslem_importu_polon,
)
from import_polon.tests.test_plik_z_haslem import (
    HASLO,
    NAGLOWKI_POLON,
    XLSX_CT,
    _form_polon,
    _xlsx,
    _zaszyfruj,
)
from import_polon.tests.test_plik_z_haslem_usuwanie import (
    ANALIZA_ABSENCJI,
    ANALIZA_POLON,
    _import,
    _zakonczony_podglad,
)

POLON = ("importplikupolon", ImportPlikuPolon)
ABSENCJE = ("importplikuabsencji", ImportPlikuAbsencji)


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    return tmp_path


# --------------------------------------------------------------------------
# 1. Plik zostaje, gdy przebieg nie ruszy: anulowanie przed startem,
#    nieudane enqueue(), twardo zabity worker
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_anulowanie_przed_startem_plik_sprzata_zadanie(admin_user):
    """Runner liveops przy ``cancel_requested`` kończy operację BEZ ``run()``
    — plik zostaje; sprząta go zadanie cykliczne."""
    from liveops.runner import task_run

    imp = _import(ImportPlikuPolon, admin_user, zaszyfrowany=True)
    sciezka = imp.plik.path
    imp.cancel_requested = True
    imp.save(update_fields=["cancel_requested"])

    with mock.patch.object(ImportPlikuPolon, "run") as run:
        task_run(imp, MockProgress(imp))
    run.assert_not_called()
    imp.refresh_from_db()
    assert imp.cancelled and imp.finished_on
    assert os.path.exists(sciezka)  # przebieg nie ruszył — plik został

    assert usun_zalegle_pliki_z_haslem_importu_polon() == 1
    imp.refresh_from_db()
    assert not imp.plik
    assert not os.path.exists(sciezka)


@pytest.mark.django_db
@pytest.mark.parametrize("model", [ImportPlikuPolon, ImportPlikuAbsencji])
def test_zadanie_sprzata_stare_i_zakonczone_zostawia_reszte(model, admin_user):
    teraz = timezone.now()
    zakonczony = _import(model, admin_user, True, nazwa="z.xlsx", finished_on=teraz)
    stary = _import(model, admin_user, True, nazwa="s.xlsx")
    model.objects.filter(pk=stary.pk).update(created_on=teraz - timedelta(hours=25))
    # Czeka w kolejce / właśnie ruszył — 2 h to za mało, żeby zabrać plik.
    w_kolejce = _import(model, admin_user, True, nazwa="k.xlsx")
    model.objects.filter(pk=w_kolejce.pk).update(created_on=teraz - timedelta(hours=2))
    w_toku = _import(model, admin_user, True, nazwa="w.xlsx", started_on=teraz)
    zwykly = _import(model, admin_user, False, nazwa="n.xlsx", finished_on=teraz)
    sciezki = {
        o.pk: o.plik.path for o in (zakonczony, stary, w_kolejce, w_toku, zwykly)
    }

    assert usun_zalegle_pliki_z_haslem() == 2

    assert not os.path.exists(sciezki[zakonczony.pk])
    assert not os.path.exists(sciezki[stary.pk])
    assert os.path.exists(sciezki[w_kolejce.pk])
    assert os.path.exists(sciezki[w_toku.pk])
    assert os.path.exists(sciezki[zwykly.pk])


def test_zadanie_jest_w_harmonogramie(settings):
    zadania = {w["task"] for w in settings.CELERYBEAT_SCHEDULE.values()}
    assert "import_polon.tasks.usun_zalegle_pliki_z_haslem_importu_polon" in zadania


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url,dane",
    [
        ("import_polon:utworz-import", {"rok": 2023}),
        ("import_polon:utworz-import-absencji", {}),
    ],
)
def test_nieudane_enqueue_nie_zostawia_pliku(url, dane, admin_client, media_root):
    if "absencji" in url:
        from import_polon.tests.test_plik_z_haslem import NAGLOWKI_ABSENCJI

        zawartosc = _zaszyfruj(_xlsx(NAGLOWKI_ABSENCJI))
    else:
        zawartosc = _zaszyfruj(_xlsx(NAGLOWKI_POLON))
    dane = {
        **dane,
        "zapisz_zmiany_do_bazy": "",
        "haslo_do_pliku": HASLO,
        "plik": SimpleUploadedFile("raport.xlsx", zawartosc, content_type=XLSX_CT),
    }

    with (
        mock.patch(
            "liveops.models.LiveOperation.enqueue",
            side_effect=ConnectionError("broker niedostępny"),
        ),
        pytest.raises(ConnectionError),
    ):
        admin_client.post(reverse(url), dane)

    media = media_root / "media"
    pliki = [p for p in media.rglob("*") if p.is_file()] if media.exists() else []
    assert pliki == []


# --------------------------------------------------------------------------
# 2 + 3. Każda ścieżka restartu / zapisu odrzuca import z pliku z hasłem —
#        także centralny liveops:restart i w oknie, gdy plik jeszcze leży
# --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("prefix,model", [POLON, ABSENCJE])
def test_centralny_restart_liveops_odrzuca_import_z_haslem(
    prefix, model, admin_client, admin_user
):
    imp = _zakonczony_podglad(model, admin_user, zaszyfrowany=True)
    imp.get_details_set().model.objects.create(parent=imp, nr_wiersza=1)
    url = reverse(
        "liveops:restart", kwargs={"op_type": model.op_type_key(), "pk": imp.pk}
    )

    with mock.patch.object(model, "enqueue") as enqueue:
        res = admin_client.post(url, HTTP_HX_REQUEST="true")

    assert res.status_code == 403
    enqueue.assert_not_called()
    imp.refresh_from_db()
    assert imp.finished_successfully is True
    assert imp.get_details_set().count() == 1  # wyniki nietknięte


@pytest.mark.django_db
def test_centralny_restart_zwyklego_importu_dziala(admin_client, admin_user):
    imp = _zakonczony_podglad(ImportPlikuPolon, admin_user, zaszyfrowany=False)
    url = reverse(
        "liveops:restart",
        kwargs={"op_type": ImportPlikuPolon.op_type_key(), "pk": imp.pk},
    )
    with mock.patch.object(ImportPlikuPolon, "enqueue") as enqueue:
        res = admin_client.post(url)
    assert res.status_code == 302
    enqueue.assert_called_once()


@pytest.mark.django_db
@pytest.mark.parametrize("prefix,model", [POLON, ABSENCJE])
def test_zapis_i_restart_zablokowane_gdy_plik_jeszcze_lezy(
    prefix, model, admin_client, admin_user, django_capture_on_commit_callbacks
):
    """Okno między ``p.result()`` a skasowaniem pliku: import jest już
    „zakończony pomyślnie”, plik jeszcze na dysku — i tak blokujemy."""
    imp = _zakonczony_podglad(model, admin_user, zaszyfrowany=True)
    assert os.path.exists(imp.plik.path)

    zapis = reverse(f"import_polon:{prefix}-zapisz-do-bazy", args=[imp.pk])
    res = admin_client.get(zapis)
    assert 'id="id_submit"' not in res.content.decode()

    with django_capture_on_commit_callbacks() as callbacks:
        admin_client.post(zapis)
    assert not any("enqueue" in cb.__qualname__ for cb in callbacks)

    with mock.patch.object(model, "enqueue") as enqueue:
        admin_client.post(reverse(f"import_polon:{prefix}-restart", args=[imp.pk]))
    enqueue.assert_not_called()

    imp.refresh_from_db()
    assert imp.zapisz_zmiany_do_bazy is False
    assert imp.finished_successfully is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,analiza",
    [(ImportPlikuPolon, ANALIZA_POLON), (ImportPlikuAbsencji, ANALIZA_ABSENCJI)],
)
def test_plik_kasowany_przed_oznaczeniem_sukcesu(model, analiza, admin_user):
    imp = _import(model, admin_user, zaszyfrowany=True)
    sciezka = imp.plik.path
    p = MockProgress(imp)
    w_chwili_sukcesu = []
    oryginal = p.result

    def result(*args, **kwargs):
        w_chwili_sukcesu.append(os.path.exists(sciezka))
        return oryginal(*args, **kwargs)

    p.result = result
    with mock.patch(analiza, return_value=None):
        imp.run(p)

    assert w_chwili_sukcesu == [False]


# --------------------------------------------------------------------------
# 4. Uszkodzone metadane szyfrowania
# --------------------------------------------------------------------------


@pytest.fixture
def uszkodzony_zaszyfrowany(tmp_path):
    p = tmp_path / "uszkodzony.xlsx"
    p.write_bytes(_zaszyfruj(_xlsx(NAGLOWKI_POLON)))
    ole = olefile.OleFileIO(str(p), write_mode=True)
    dane = ole.openstream("EncryptionInfo").read()
    # Ta sama długość strumienia, ale XML bez <keyData> → msoffcrypto: IndexError
    ole.write_stream("EncryptionInfo", dane.replace(b"<keyData ", b"<keyDatX "))
    ole.close()
    return p.read_bytes()


def test_detektor_nie_wywraca_sie_na_uszkodzonym_pliku(uszkodzony_zaszyfrowany):
    import io

    from import_common.util import czy_plik_zaszyfrowany

    assert czy_plik_zaszyfrowany(io.BytesIO(uszkodzony_zaszyfrowany)) is True


@pytest.mark.django_db
def test_uszkodzony_plik_z_haslem_daje_blad_walidacji(uszkodzony_zaszyfrowany):
    form = _form_polon(uszkodzony_zaszyfrowany, haslo=HASLO)
    assert not form.is_valid()
    blad = form.errors["plik"][0]
    assert "uszkodzony" in blad
    assert HASLO not in blad

    form = _form_polon(uszkodzony_zaszyfrowany)
    assert not form.is_valid()
    assert "zabezpieczony hasłem" in form.errors["plik"][0]


# --------------------------------------------------------------------------
# 5. Limit rozmiaru pliku z hasłem
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_za_duzy_plik_z_haslem_odrzucony_przed_odszyfrowaniem():
    dane = _zaszyfruj(_xlsx(NAGLOWKI_POLON))
    with (
        mock.patch("import_common.util.MAX_ROZMIAR_PLIKU_Z_HASLEM", 1024),
        mock.patch("msoffcrypto.OfficeFile") as office,
    ):
        form = _form_polon(dane, haslo=HASLO)
        assert not form.is_valid()
    office.assert_not_called()
    assert "za duży" in form.errors["plik"][0]


def test_limit_pliku_z_haslem_10_mb():
    from import_common.util import MAX_ROZMIAR_PLIKU, MAX_ROZMIAR_PLIKU_Z_HASLEM

    assert MAX_ROZMIAR_PLIKU_Z_HASLEM == 10 * 1024 * 1024
    assert MAX_ROZMIAR_PLIKU_Z_HASLEM < MAX_ROZMIAR_PLIKU


# --------------------------------------------------------------------------
# 6. Kasowanie po przebiegu nie rusza pliku współdzielonego
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_kasowanie_po_przebiegu_nie_rusza_pliku_wspoldzielonego(admin_user):
    imp = _import(ImportPlikuPolon, admin_user, zaszyfrowany=True)
    sciezka = imp.plik.path
    inny = baker.make(ImportPlikuAbsencji, owner=admin_user, plik=imp.plik.name)

    with mock.patch(ANALIZA_POLON, return_value=None):
        imp.run(MockProgress(imp))

    imp.refresh_from_db()
    assert not imp.plik
    assert os.path.exists(sciezka)
    inny.refresh_from_db()
    assert inny.plik


# --------------------------------------------------------------------------
# 7. Hasło w raporcie błędu Django (strona debug / e-mail do ADMINS)
# --------------------------------------------------------------------------


def _wybuch(*args, **kwargs):
    raise RuntimeError("awaria biblioteki")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "widok,dane",
    [
        ("import_polon.views.plik_polon.UtworzImportPlikuPolon", {"rok": "2023"}),
        ("import_polon.views.plik_absencji.UtworzImportPlikuAbsencji", {}),
    ],
)
def test_haslo_zamaskowane_w_raporcie_bledu(widok, dane, admin_user):
    from django.utils.module_loading import import_string

    request = RequestFactory().post(
        "/import_polon/",
        {
            **dane,
            "haslo_do_pliku": HASLO,
            "plik": SimpleUploadedFile(
                "raport.xlsx", _zaszyfruj(_xlsx(NAGLOWKI_POLON)), content_type=XLSX_CT
            ),
        },
    )
    request.user = admin_user

    with (
        mock.patch("msoffcrypto.OfficeFile", _wybuch),
        pytest.raises(RuntimeError),
    ):
        try:
            import_string(widok).as_view()(request)
        except RuntimeError:
            raport = ExceptionReporter(request, *sys.exc_info()).get_traceback_text()
            raise

    assert "awaria biblioteki" in raport
    assert "haslo_do_pliku" in raport
    assert HASLO not in raport
