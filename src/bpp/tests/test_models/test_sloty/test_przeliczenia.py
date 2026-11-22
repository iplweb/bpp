"""Automatyczne przeliczenie punktacji dyscyplin po aktualizacji (FD#618)."""

from decimal import Decimal
from unittest import mock

import pytest
from denorm import denorms
from denorm.models import DirtyInstance
from django.contrib.contenttypes.models import ContentType

from bpp import przeliczenia
from bpp.models import Wersja_Przeliczenia, Wydawnictwo_Ciagle
from bpp.models.sloty.core import IPunktacjaCacher
from bpp.przeliczenia import (
    PRZELICZENIA,
    Przeliczenie,
    oznacz_punktacje_dyscyplin,
    zlec_przeliczenie,
    zlec_zalegle_przeliczenia,
)


def _znaczniki_punktacji(rekord):
    return DirtyInstance.objects.filter(
        content_type=ContentType.objects.get_for_model(rekord),
        object_id=rekord.pk,
        func_name="cached_punkty_dyscyplin",
    )


def _artykul_70_pkt_k1_m2(ciagle, rok):
    """Artykuł z 2022 r., 70 pkt, dwóch autorów z różnych dyscyplin:
    √(1/2) = 0,7071, czyli 49,4970 pkt (stary kod: 49,4975)."""
    ciagle.rok = 2022
    ciagle.punkty_kbn = 70
    ciagle.save()
    for wca in ciagle.autorzy_set.all():
        ad = wca.autor.autor_dyscyplina_set.get(rok=rok)
        ad.pk = None
        ad.rok = 2022
        ad.save()
    return ciagle


def test_rejestr_przeliczen_ma_unikalne_nazwy_i_dodatnie_wersje():
    nazwy = [p.nazwa for p in PRZELICZENIA]
    assert len(nazwy) == len(set(nazwy))
    assert all(p.wersja > 0 for p in PRZELICZENIA)
    assert "punktacja_dyscyplin" in nazwy


@pytest.mark.django_db
def test_oznacza_tylko_rekordy_z_dyscyplina(
    ciagle_z_dyscyplinami, make_ciagle, autor_jan_nowak, jednostka
):
    bez_dyscypliny = make_ciagle(autor_jan_nowak, jednostka)
    assert not bez_dyscypliny.autorzy_set.exclude(dyscyplina_naukowa=None).exists()
    DirtyInstance.objects.all().delete()

    oznacz_punktacje_dyscyplin()

    assert _znaczniki_punktacji(ciagle_z_dyscyplinami).count() == 1
    assert not _znaczniki_punktacji(bez_dyscypliny).exists()


@pytest.mark.django_db
def test_zlecenie_raz_na_wersje(ciagle_z_dyscyplinami):
    DirtyInstance.objects.all().delete()

    wynik = zlec_zalegle_przeliczenia()

    assert wynik == {"punktacja_dyscyplin": 1}
    stan = Wersja_Przeliczenia.objects.get(nazwa="punktacja_dyscyplin")
    assert stan.wersja == PRZELICZENIA[0].wersja
    assert stan.oznaczono_rekordow == 1
    assert stan.zlecono is not None
    assert _znaczniki_punktacji(ciagle_z_dyscyplinami).count() == 1

    # Kolejny start workera: wersja aktualna, nic nie oznaczamy.
    DirtyInstance.objects.all().delete()
    assert zlec_zalegle_przeliczenia() == {}
    assert not _znaczniki_punktacji(ciagle_z_dyscyplinami).exists()


@pytest.mark.django_db
def test_podbicie_wersji_zleca_ponownie():
    oznacz = mock.Mock(return_value=5)
    v1 = Przeliczenie(nazwa="testowe", wersja=1, oznacz=oznacz)
    v2 = Przeliczenie(nazwa="testowe", wersja=2, oznacz=oznacz)

    assert zlec_przeliczenie(v1) == 5
    assert zlec_przeliczenie(v1) is None
    assert zlec_przeliczenie(v2) == 5
    assert oznacz.call_count == 2
    assert Wersja_Przeliczenia.objects.get(nazwa="testowe").wersja == 2

    # Starszy kod (np. stary worker w trakcie wdrożenia) nie cofa wersji.
    assert zlec_przeliczenie(v1) is None
    assert Wersja_Przeliczenia.objects.get(nazwa="testowe").wersja == 2


@pytest.mark.django_db
def test_blad_wycofuje_zlecenie_i_nie_podbija_wersji(ciagle_z_dyscyplinami):
    DirtyInstance.objects.all().delete()

    def oznacz_i_wybuchnij():
        oznacz_punktacje_dyscyplin()
        raise RuntimeError("awaria")

    p = Przeliczenie(nazwa="punktacja_dyscyplin", wersja=1, oznacz=oznacz_i_wybuchnij)
    with pytest.raises(RuntimeError):
        zlec_przeliczenie(p)

    # Znaczniki i wersja wycofane razem — następny start workera ponowi.
    assert not _znaczniki_punktacji(ciagle_z_dyscyplinami).exists()
    assert not Wersja_Przeliczenia.objects.filter(
        nazwa="punktacja_dyscyplin", wersja__gte=1
    ).exists()


@pytest.mark.django_db
def test_fd618_kolejka_denorm_przelicza_stara_punktacje(ciagle_z_dyscyplinami, rok):
    """Od zlecenia do poprawionych wartości: wartości policzone starym kodem
    (bez zaokrąglenia √(k/m)) zostają przeliczone przez kolejkę denorm."""
    rekord = _artykul_70_pkt_k1_m2(ciagle_z_dyscyplinami, rok)
    denorms.flush()
    cacher = IPunktacjaCacher(rekord)
    # Stan bazy sprzed FD#618 (bez znaczników denorm — nic go nie poprawi).
    cacher.cache_punktacja_dyscypliny.update(pkd=Decimal("49.4975"))
    cacher.cache_punktacja_autora.update(pkdaut=Decimal("49.4975"))
    Wydawnictwo_Ciagle.objects.filter(pk=rekord.pk).update(
        cached_punkty_dyscyplin={"stary": "cache"}
    )
    # Znaczniki od samej symulacji (triggery) usuwamy: w produkcji ten stan
    # był już dawno „przetrawiony” przez kolejkę denorm.
    DirtyInstance.objects.all().delete()
    assert {c.pkd for c in cacher.cache_punktacja_dyscypliny} == {Decimal("49.4975")}
    ostatnio_zmieniony = Wydawnictwo_Ciagle.objects.get(pk=rekord.pk).ostatnio_zmieniony

    zlec_zalegle_przeliczenia()
    denorms.flush()

    assert {c.pkd for c in cacher.cache_punktacja_dyscypliny} == {Decimal("49.4970")}
    assert {c.pkdaut for c in cacher.cache_punktacja_autora} == {Decimal("49.4970")}
    rekord = Wydawnictwo_Ciagle.objects.get(pk=rekord.pk)
    assert "49.4970" in str(rekord.cached_punkty_dyscyplin)
    # Przeliczenie nie udaje edycji rekordu przez użytkownika.
    assert rekord.ostatnio_zmieniony == ostatnio_zmieniony


def test_start_workera_tylko_zleca_zadanie():
    """Sygnał ``worker_ready`` nie liczy niczego sam — tylko ``delay()``."""
    from django_bpp.celery_tasks import zlec_przeliczenia_po_aktualizacji

    with mock.patch("bpp.tasks.zlec_zalegle_przeliczenia.delay") as delay:
        zlec_przeliczenia_po_aktualizacji(sender=None)
    delay.assert_called_once_with()


@pytest.mark.django_db
def test_zadanie_celery_wola_zlecenie():
    from bpp.tasks import zlec_zalegle_przeliczenia as zadanie

    with mock.patch.object(przeliczenia, "zlec_zalegle_przeliczenia") as zlec:
        zadanie.apply()
    zlec.assert_called_once_with()


@pytest.mark.django_db
def test_admin_pokazuje_wersje_przeliczen(admin_client):
    Wersja_Przeliczenia.objects.create(
        nazwa="punktacja_dyscyplin", wersja=1, oznaczono_rekordow=123
    )
    res = admin_client.get("/admin/bpp/wersja_przeliczenia/")
    assert res.status_code == 200
    assert "punktacja_dyscyplin" in res.content.decode()
