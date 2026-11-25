"""Odszyfrowana kopia pliku zabezpieczonego hasłem nie zostaje na serwerze.

Po KAŻDYM przebiegu importu (podgląd, zapis, błąd) plik jest kasowany, a pole
``plik`` czyszczone. „Zapisz do bazy” i restart takiego importu dają czytelny
komunikat zamiast wyjątku. Osobno: usunięcie rekordu importu kasuje jego plik
z dysku (dotyczy wszystkich importów).
"""

import os
from unittest import mock

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from liveops.testing import MockProgress
from model_bakery import baker

from import_polon.models import (
    KOMUNIKAT_PLIK_Z_HASLEM_USUNIETY,
    NAZWA_USUNIETEGO_PLIKU_Z_HASLEM,
    ImportPlikuAbsencji,
    ImportPlikuPolon,
)
from import_polon.tests.test_plik_z_haslem import (
    HASLO,
    NAGLOWKI_ABSENCJI,
    NAGLOWKI_POLON,
    _form_absencji,
    _form_polon,
    _xlsx,
    _zaszyfruj,
)

ANALIZA_POLON = "import_polon.core.analyze_file_import_polon"
ANALIZA_ABSENCJI = "import_polon.core.import_absencji.analyze_file_import_absencji"


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path


def _import(model, owner, zaszyfrowany, nazwa="raport.xlsx", **extra):
    if model is ImportPlikuPolon:
        extra.setdefault("rok", 2023)
    imp = baker.make(model, owner=owner, plik_byl_zaszyfrowany=zaszyfrowany, **extra)
    imp.plik.save(nazwa, ContentFile(b"dane"), save=True)
    return imp


def _zakonczony_podglad(model, owner, zaszyfrowany):
    return _import(
        model,
        owner,
        zaszyfrowany,
        zapisz_zmiany_do_bazy=False,
        started_on=timezone.now(),
        finished_on=timezone.now(),
        finished_successfully=True,
    )


def _plik_usuniety(imp, sciezka):
    imp.refresh_from_db()
    return not imp.plik and not os.path.exists(sciezka)


# --------------------------------------------------------------------------
# run(): kasowanie po każdym przebiegu
# --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,analiza",
    [(ImportPlikuPolon, ANALIZA_POLON), (ImportPlikuAbsencji, ANALIZA_ABSENCJI)],
)
def test_run_kasuje_plik_z_haslem_po_sukcesie(model, analiza, admin_user):
    imp = _import(model, admin_user, zaszyfrowany=True)
    sciezka = imp.plik.path

    with mock.patch(analiza, return_value=None) as analyze:
        imp.run(MockProgress(imp))

    analyze.assert_called_once()
    assert _plik_usuniety(imp, sciezka)
    assert imp.plik_byl_zaszyfrowany is True
    assert imp.nazwa_pliku == NAZWA_USUNIETEGO_PLIKU_Z_HASLEM


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,analiza",
    [(ImportPlikuPolon, ANALIZA_POLON), (ImportPlikuAbsencji, ANALIZA_ABSENCJI)],
)
def test_run_kasuje_plik_z_haslem_po_bledzie(model, analiza, admin_user):
    imp = _import(model, admin_user, zaszyfrowany=True)
    sciezka = imp.plik.path

    with (
        mock.patch(analiza, side_effect=RuntimeError("awaria")),
        mock.patch("bpp.zglaszanie_bledow.capture_exception"),
        pytest.raises(RuntimeError),
    ):
        imp.run(MockProgress(imp))

    assert _plik_usuniety(imp, sciezka)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,analiza",
    [(ImportPlikuPolon, ANALIZA_POLON), (ImportPlikuAbsencji, ANALIZA_ABSENCJI)],
)
def test_run_zostawia_zwykly_plik(model, analiza, admin_user):
    imp = _import(model, admin_user, zaszyfrowany=False)
    sciezka = imp.plik.path

    with mock.patch(analiza, return_value=None):
        imp.run(MockProgress(imp))

    imp.refresh_from_db()
    assert imp.plik
    assert os.path.exists(sciezka)


@pytest.mark.django_db
def test_run_prawdziwy_import_absencji_z_haslem(admin_user, fn_test_import_absencji):
    """Cała ścieżka: formularz z hasłem → zapis → run() czyta odszyfrowany plik
    → plik znika z dysku."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from import_polon.forms import NowyImportAbsencjiForm

    dane = _zaszyfruj(fn_test_import_absencji.read_bytes())
    form = NowyImportAbsencjiForm(
        data={"zapisz_zmiany_do_bazy": False, "haslo_do_pliku": HASLO},
        files={"plik": SimpleUploadedFile("absencje.xlsx", dane)},
    )
    assert form.is_valid(), form.errors
    form.instance.owner = admin_user
    imp = form.save()
    assert imp.plik_byl_zaszyfrowany is True
    sciezka = imp.plik.path
    assert os.path.exists(sciezka)

    p = MockProgress(imp)
    imp.run(p)

    assert p.error_message is None
    assert imp.get_details_set().count() > 0
    assert _plik_usuniety(imp, sciezka)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,analiza",
    [(ImportPlikuPolon, ANALIZA_POLON), (ImportPlikuAbsencji, ANALIZA_ABSENCJI)],
)
def test_run_bez_pliku_daje_komunikat_nie_wyjatek(model, analiza, admin_user):
    """Restart (np. przycisk „Ponów” liveops) importu z usuniętym plikiem."""
    imp = baker.make(model, owner=admin_user, plik_byl_zaszyfrowany=True, plik="")
    if model is ImportPlikuPolon:
        imp.rok = 2023
        imp.save()
    p = MockProgress(imp)

    with (
        mock.patch(analiza) as analyze,
        mock.patch("bpp.zglaszanie_bledow.capture_exception") as capture,
    ):
        imp.run(p)

    analyze.assert_not_called()
    capture.assert_not_called()
    assert p.error_message == KOMUNIKAT_PLIK_Z_HASLEM_USUNIETY


@pytest.mark.django_db
def test_formularz_oznacza_plik_z_haslem():
    form = _form_polon(_zaszyfruj(_xlsx(NAGLOWKI_POLON)), haslo=HASLO)
    assert form.is_valid(), form.errors
    assert form.instance.plik_byl_zaszyfrowany is True

    form = _form_absencji(_xlsx(NAGLOWKI_ABSENCJI), haslo=HASLO)
    assert form.is_valid(), form.errors
    assert form.instance.plik_byl_zaszyfrowany is False


# --------------------------------------------------------------------------
# Widoki z usuniętym plikiem
# --------------------------------------------------------------------------

POLON = ("importplikupolon", ImportPlikuPolon)
ABSENCJE = ("importplikuabsencji", ImportPlikuAbsencji)


def _po_przebiegu(model, owner):
    """Zakończony podgląd importu z hasłem — plik już skasowany."""
    imp = _zakonczony_podglad(model, owner, zaszyfrowany=True)
    imp.usun_plik_jesli_byl_zaszyfrowany()
    imp.refresh_from_db()
    assert not imp.plik
    return imp


@pytest.mark.django_db
@pytest.mark.parametrize("prefix,model", [POLON, ABSENCJE])
def test_wyniki_i_strona_live_bez_pliku(prefix, model, admin_client, admin_user):
    imp = _po_przebiegu(model, admin_user)

    res = admin_client.get(reverse(f"import_polon:{prefix}-results", args=[imp.pk]))
    assert res.status_code == 200
    tresc = res.content.decode()
    assert "plik-z-haslem-usuniety" in tresc
    assert "Ze względów bezpieczeństwa danych" in tresc
    assert "hasło nie zostało nigdzie zapisane" in tresc
    assert reverse(f"import_polon:{prefix}-zapisz-do-bazy", args=[imp.pk]) not in tresc

    res = admin_client.get(imp.get_absolute_url())
    assert res.status_code == 200
    tresc = res.content.decode()
    assert "plik-z-haslem-usuniety" in tresc
    assert reverse(f"import_polon:{prefix}-zapisz-do-bazy", args=[imp.pk]) not in tresc


@pytest.mark.django_db
@pytest.mark.parametrize(
    "index,model",
    [("index", ImportPlikuPolon), ("index-absencji", ImportPlikuAbsencji)],
)
def test_lista_importow_bez_pliku(index, model, admin_client, admin_user):
    _po_przebiegu(model, admin_user)

    res = admin_client.get(reverse(f"import_polon:{index}"))
    assert res.status_code == 200
    assert "usunięty po przetworzeniu" in res.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("prefix,model", [POLON, ABSENCJE])
def test_zapisz_do_bazy_bez_pliku(
    prefix, model, admin_client, admin_user, django_capture_on_commit_callbacks
):
    imp = _po_przebiegu(model, admin_user)
    url = reverse(f"import_polon:{prefix}-zapisz-do-bazy", args=[imp.pk])

    res = admin_client.get(url)
    assert res.status_code == 200
    assert "Ze względów bezpieczeństwa danych" in res.content.decode()
    assert 'id="id_submit"' not in res.content.decode()

    with django_capture_on_commit_callbacks() as callbacks:
        res = admin_client.post(url, follow=True)

    assert res.status_code == 200
    assert "zabezpieczony hasłem" in res.content.decode()
    assert not any("enqueue" in cb.__qualname__ for cb in callbacks)
    imp.refresh_from_db()
    assert imp.zapisz_zmiany_do_bazy is False
    assert imp.finished_successfully is True


@pytest.mark.django_db
@pytest.mark.parametrize("prefix,model", [POLON, ABSENCJE])
def test_restart_bez_pliku(prefix, model, admin_client, admin_user):
    imp = _po_przebiegu(model, admin_user)
    url = reverse(f"import_polon:{prefix}-restart", args=[imp.pk])

    with mock.patch.object(model, "enqueue") as enqueue:
        res = admin_client.post(url, follow=True)

    assert res.status_code == 200
    assert "zabezpieczony hasłem" in res.content.decode()
    enqueue.assert_not_called()
    imp.refresh_from_db()
    assert imp.finished_successfully is True


@pytest.mark.django_db
def test_zwykly_podglad_nadal_ma_przycisk_zapisu(admin_client, admin_user):
    imp = _zakonczony_podglad(ImportPlikuPolon, admin_user, zaszyfrowany=False)

    res = admin_client.get(
        reverse("import_polon:importplikupolon-results", args=[imp.pk])
    )
    tresc = res.content.decode()
    assert (
        reverse("import_polon:importplikupolon-zapisz-do-bazy", args=[imp.pk]) in tresc
    )
    assert "plik-z-haslem-usuniety" not in tresc


# --------------------------------------------------------------------------
# post_delete: plik znika razem z rekordem importu
# --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("model", [ImportPlikuPolon, ImportPlikuAbsencji])
def test_usuniecie_importu_kasuje_plik(
    model, admin_user, django_capture_on_commit_callbacks
):
    imp = _import(model, admin_user, zaszyfrowany=False)
    sciezka = imp.plik.path

    with django_capture_on_commit_callbacks(execute=True):
        imp.delete()

    assert not os.path.exists(sciezka)


@pytest.mark.django_db
def test_usuniecie_importu_nie_kasuje_pliku_wspoldzielonego(
    admin_user, django_capture_on_commit_callbacks
):
    imp = _import(ImportPlikuPolon, admin_user, zaszyfrowany=False)
    sciezka = imp.plik.path
    inny = baker.make(ImportPlikuAbsencji, owner=admin_user, plik=imp.plik.name)

    with django_capture_on_commit_callbacks(execute=True):
        imp.delete()

    assert os.path.exists(sciezka)
    inny.refresh_from_db()
    assert inny.plik.name == imp.plik.name


@pytest.mark.django_db
def test_usuniecie_importu_bez_pliku_na_dysku(
    admin_user, django_capture_on_commit_callbacks
):
    imp = _import(ImportPlikuPolon, admin_user, zaszyfrowany=False)
    os.unlink(imp.plik.path)
    pusty = baker.make(ImportPlikuAbsencji, owner=admin_user, plik="")

    with django_capture_on_commit_callbacks(execute=True):
        imp.delete()
        pusty.delete()


@pytest.mark.django_db
def test_lista_usuwa_stare_importy_razem_z_plikami(
    admin_client, admin_user, django_capture_on_commit_callbacks
):
    """Lista trzyma 10 ostatnich importów — starsze kasuje razem z plikami."""
    importy = [
        _import(ImportPlikuAbsencji, admin_user, zaszyfrowany=False, nazwa=f"a{i}.xlsx")
        for i in range(12)
    ]
    sciezki = [i.plik.path for i in importy]

    with django_capture_on_commit_callbacks(execute=True):
        res = admin_client.get(reverse("import_polon:index-absencji"))
    assert res.status_code == 200

    istnieje = [os.path.exists(s) for s in sciezki]
    assert istnieje.count(True) == 10
