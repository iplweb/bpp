"""Multi-hosted: kolejka eksportu PBN widoczna tylko dla uczelni z domeny.

Uczelnia X loguje się do PBN na profil instytucji X i tylko tam może wysłać
pracę — wpisy uczelni Y są dla niej bezużyteczne, a ich podgląd i ponowna
wysyłka to wyciek danych między uczelniami. Każdy widok kolejki (lista,
liczniki, szczegóły, akcje pojedyncze i masowe) działa więc wyłącznie na
wpisach uczelni ustalonej z domeny requestu — także dla superusera.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from pbn_export_queue.models import PBN_Export_Queue, RodzajBledu


def _wpis(uczelnia, user, **kw):
    rekord = baker.make("bpp.Wydawnictwo_Ciagle", rok=2024)
    return baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=rekord,
        zamowil=user,
        uczelnia=uczelnia,
        **kw,
    )


@pytest.fixture
def wpisy(uczelnia1, uczelnia2, superuser_multisite):
    blad = {"zakonczono_pomyslnie": False, "rodzaj_bledu": RodzajBledu.TECHNICZNY}
    return {
        "u1": _wpis(uczelnia1, superuser_multisite, **blad),
        "u2": _wpis(uczelnia2, superuser_multisite, **blad),
        "null": _wpis(None, superuser_multisite, **blad),
    }


@pytest.fixture
def zalogowany(client, superuser_multisite, settings):
    # Domeny site1/site2 (``uczelniaN.localhost``) spoza domyślnych hostów.
    settings.ALLOWED_HOSTS = ["*"]
    client.force_login(superuser_multisite)
    return client


# --- QuerySet.dla_uczelni ---------------------------------------------------


@pytest.mark.django_db
def test_dla_uczelni_multi_tylko_wpisy_tej_uczelni(wpisy, uczelnia1):
    qs = PBN_Export_Queue.objects.dla_uczelni(uczelnia1)
    assert set(qs) == {wpisy["u1"]}


@pytest.mark.django_db
def test_dla_uczelni_multi_none_pusto(wpisy):
    """Nieustalona uczelnia przy >1 uczelni → nic (fail-closed)."""
    assert not PBN_Export_Queue.objects.dla_uczelni(None).exists()


@pytest.mark.django_db
def test_dla_uczelni_jedna_uczelnia_cala_kolejka(uczelnia1, superuser_multisite):
    """Instalacja z jedną uczelnią: cała kolejka (też legacy NULL) jest jej."""
    wlasny = _wpis(uczelnia1, superuser_multisite)
    legacy = _wpis(None, superuser_multisite)
    qs = PBN_Export_Queue.objects.dla_uczelni(uczelnia1)
    assert set(qs) == {wlasny, legacy}


@pytest.mark.django_db
def test_dla_uczelni_da_sie_lancuchowac(wpisy, uczelnia1):
    qs = PBN_Export_Queue.objects.filter(zakonczono_pomyslnie=False).dla_uczelni(
        uczelnia1
    )
    assert set(qs) == {wpisy["u1"]}


# --- widoki odczytu -----------------------------------------------------------


@pytest.mark.django_db
def test_lista_pokazuje_tylko_wpisy_uczelni_z_domeny(zalogowany, wpisy, site1):
    res = zalogowany.get(
        reverse("pbn_export_queue:export-queue-list"), HTTP_HOST=site1.domain
    )
    assert res.status_code == 200
    assert list(res.context["export_queue_items"]) == [wpisy["u1"]]
    assert res.context["total_count"] == 1
    assert res.context["error_count"] == 1
    assert res.context["error_techniczny_count"] == 1


@pytest.mark.django_db
def test_tabela_htmx_pokazuje_tylko_wpisy_uczelni(zalogowany, wpisy, site2):
    res = zalogowany.get(
        reverse("pbn_export_queue:export-queue-table"), HTTP_HOST=site2.domain
    )
    assert list(res.context["export_queue_items"]) == [wpisy["u2"]]


@pytest.mark.django_db
def test_liczniki_json_tylko_uczelnia_z_domeny(zalogowany, wpisy, site1):
    res = zalogowany.get(
        reverse("pbn_export_queue:export-queue-counts"), HTTP_HOST=site1.domain
    )
    dane = res.json()
    assert dane["total_count"] == 1
    assert dane["error_count"] == 1


@pytest.mark.django_db
def test_szczegoly_cudzego_wpisu_404(zalogowany, wpisy, site1):
    url = reverse("pbn_export_queue:export-queue-detail", args=[wpisy["u2"].pk])
    assert zalogowany.get(url, HTTP_HOST=site1.domain).status_code == 404


@pytest.mark.django_db
def test_szczegoly_wlasnego_wpisu_200(zalogowany, wpisy, site1):
    url = reverse("pbn_export_queue:export-queue-detail", args=[wpisy["u1"].pk])
    assert zalogowany.get(url, HTTP_HOST=site1.domain).status_code == 200


# --- akcje pojedyncze ---------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "nazwa",
    [
        "export-queue-resend",
        "export-queue-prepare-resend",
        "export-queue-try-send",
    ],
)
def test_akcja_na_cudzym_wpisie_404_bez_wysylki(
    zalogowany, wpisy, site1, mocker, nazwa
):
    delay = mocker.patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay")
    url = reverse(f"pbn_export_queue:{nazwa}", args=[wpisy["u2"].pk])
    assert zalogowany.post(url, HTTP_HOST=site1.domain).status_code == 404
    delay.assert_not_called()


@pytest.mark.django_db
def test_usuniecie_cudzego_wpisu_404_i_wpis_zostaje(zalogowany, wpisy, site1):
    url = reverse("pbn_export_queue:export-queue-delete", args=[wpisy["u2"].pk])
    assert zalogowany.post(url, HTTP_HOST=site1.domain).status_code == 404
    assert PBN_Export_Queue.objects.filter(pk=wpisy["u2"].pk).exists()


@pytest.mark.django_db
def test_usuniecie_wlasnego_wpisu_dziala(zalogowany, wpisy, site1):
    url = reverse("pbn_export_queue:export-queue-delete", args=[wpisy["u1"].pk])
    assert zalogowany.post(url, HTTP_HOST=site1.domain).status_code == 302
    assert not PBN_Export_Queue.objects.filter(pk=wpisy["u1"].pk).exists()


# --- akcje masowe ---------------------------------------------------------------


def _wyslane_pk(delay):
    return {c.args[0] for c in delay.call_args_list}


@pytest.mark.django_db
def test_ponow_bledy_techniczne_tylko_uczelnia_z_domeny(
    zalogowany, wpisy, site1, mocker
):
    delay = mocker.patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay")
    zalogowany.post(
        reverse("pbn_export_queue:export-queue-resend-all-errors"),
        HTTP_HOST=site1.domain,
    )
    assert _wyslane_pk(delay) == {wpisy["u1"].pk}


@pytest.mark.django_db
def test_ponow_oczekujace_tylko_uczelnia_z_domeny(
    zalogowany, uczelnia1, uczelnia2, superuser_multisite, site1, mocker
):
    w1 = _wpis(uczelnia1, superuser_multisite, retry_after_user_authorised=True)
    _wpis(uczelnia2, superuser_multisite, retry_after_user_authorised=True)
    delay = mocker.patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay")
    zalogowany.post(
        reverse("pbn_export_queue:export-queue-resend-all-waiting"),
        HTTP_HOST=site1.domain,
    )
    assert _wyslane_pk(delay) == {w1.pk}


@pytest.mark.django_db
def test_obudz_kolejke_tylko_uczelnia_z_domeny(
    zalogowany, uczelnia1, uczelnia2, superuser_multisite, site1, mocker
):
    w1 = _wpis(uczelnia1, superuser_multisite)
    _wpis(uczelnia2, superuser_multisite)
    delay = mocker.patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay")
    zalogowany.post(
        reverse("pbn_export_queue:export-queue-wake-up"), HTTP_HOST=site1.domain
    )
    assert _wyslane_pk(delay) == {w1.pk}


@pytest.mark.django_db
def test_ponow_wyfiltrowane_tylko_uczelnia_z_domeny(zalogowany, wpisy, site1, mocker):
    delay = mocker.patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay")
    zalogowany.post(
        reverse("pbn_export_queue:export-queue-resend-filtered"),
        {"zakonczono_pomyslnie": "false"},
        HTTP_HOST=site1.domain,
    )
    assert _wyslane_pk(delay) == {wpisy["u1"].pk}
