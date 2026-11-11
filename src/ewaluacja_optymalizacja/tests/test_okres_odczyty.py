"""Dwa okresy ewaluacji obok siebie: odczyty liczby N, udziałów i metryk
w module optymalizacji biorą wyłącznie wiersze okresu w zakresie (okres
runa, zadania albo wybrany w sesji) — nie mieszają okresów."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Dyscyplina_Naukowa
from ewaluacja_common.okres import KLUCZ_SESJI
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc, LiczbaNDlaUczelni
from ewaluacja_metryki.models import MetrykaAutora
from ewaluacja_optymalizacja.models import OptimizationRun


def _wybierz_okres(client, okres):
    sesja = client.session
    sesja[KLUCZ_SESJI] = okres.pk
    sesja.save()


def _metryka(autor, dyscyplina, okres, uczelnia=None, **kw):
    return baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        okres=okres,
        uczelnia=uczelnia,
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("4.0"),
        _fill_optional=False,
        **kw,
    )


@pytest.mark.django_db
def test_load_author_slot_limits_udzialy_z_okresu(uczelnia, okres_2022, okres_2026):
    from ewaluacja_optymalizacja.core.data_loader import load_author_slot_limits

    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Okresowa", kod="9.9")
    autor = baker.make(Autor)
    for okres, ogolem, mono in [
        (okres_2022, "2.00", "1.00"),
        (okres_2026, "3.00", "1.50"),
    ]:
        baker.make(
            IloscUdzialowDlaAutoraZaCalosc,
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            uczelnia=uczelnia,
            okres=okres,
            ilosc_udzialow=Decimal(ogolem),
            ilosc_udzialow_monografie=Decimal(mono),
        )

    def log(*args, **kwargs):
        return None

    limity = load_author_slot_limits([autor.pk], dyscyplina, log, okres=okres_2022)
    assert limity[autor.pk] == {"total": 2.0, "mono": 1.0}

    limity = load_author_slot_limits([autor.pk], dyscyplina, log, okres=okres_2026)
    assert limity[autor.pk] == {"total": 3.0, "mono": 1.5}


@pytest.mark.django_db
def test_index_liczba_n_wybranego_okresu(
    admin_client, uczelnia, okres_2022, okres_2026
):
    d1 = baker.make(Dyscyplina_Naukowa, nazwa="Pierwsza", kod="9.1")
    d2 = baker.make(Dyscyplina_Naukowa, nazwa="Druga", kod="9.2")
    for okres, dyscyplina, liczba_n in [
        (okres_2022, d1, 15),
        (okres_2026, d1, 20),
        (okres_2026, d2, 5),
    ]:
        baker.make(
            LiczbaNDlaUczelni,
            uczelnia=uczelnia,
            dyscyplina_naukowa=dyscyplina,
            okres=okres,
            liczba_n=Decimal(liczba_n),
        )
    url = reverse("ewaluacja_optymalizacja:index")

    res = admin_client.get(url)
    assert res.context["liczba_n_count"] == 1
    assert res.context["liczba_n_raportowane"] == 1

    _wybierz_okres(admin_client, okres_2026)
    res = admin_client.get(url)
    assert res.context["liczba_n_count"] == 2
    assert res.context["liczba_n_raportowane"] == 1


@pytest.mark.django_db
def test_get_reported_disciplines_tylko_z_okresu(uczelnia, okres_2022, okres_2026):
    from ewaluacja_optymalizacja.views.evaluation_browser import (
        _get_reported_disciplines,
    )

    d1 = baker.make(Dyscyplina_Naukowa, nazwa="Pierwsza", kod="9.1")
    d2 = baker.make(Dyscyplina_Naukowa, nazwa="Druga", kod="9.2")
    baker.make(
        LiczbaNDlaUczelni,
        uczelnia=uczelnia,
        dyscyplina_naukowa=d1,
        okres=okres_2022,
        liczba_n=Decimal(15),
    )
    baker.make(
        LiczbaNDlaUczelni,
        uczelnia=uczelnia,
        dyscyplina_naukowa=d2,
        okres=okres_2026,
        liczba_n=Decimal(15),
    )

    assert _get_reported_disciplines(uczelnia, okres_2022) == [d1.pk]
    assert _get_reported_disciplines(uczelnia, okres_2026) == [d2.pk]


@pytest.mark.django_db
def test_author_works_detail_metryka_z_okresu_runa(
    admin_client, uczelnia, okres_2022, okres_2026
):
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Okresowa", kod="9.9")
    autor = baker.make(Autor)
    metryka_2022 = _metryka(autor, dyscyplina, okres_2022, uczelnia)
    metryka_2026 = _metryka(autor, dyscyplina, okres_2026, uczelnia)

    for okres, oczekiwana in [(okres_2022, metryka_2022), (okres_2026, metryka_2026)]:
        run = baker.make(
            OptimizationRun,
            dyscyplina_naukowa=dyscyplina,
            uczelnia=uczelnia,
            okres=okres,
            status="completed",
        )
        url = reverse(
            "ewaluacja_optymalizacja:author-works-detail",
            kwargs={"run_pk": run.pk, "autor_pk": autor.pk},
        )
        res = admin_client.get(url)
        assert res.status_code == 200
        assert res.context["metryka"] == oczekiwana


@pytest.mark.django_db
def test_analyze_unpinning_kasuje_tylko_metryki_wybranego_okresu(
    admin_client, uczelnia, okres_2022, okres_2026
):
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Okresowa", kod="9.9")
    autor = baker.make(Autor)
    metryka_2022 = _metryka(autor, dyscyplina, okres_2022, uczelnia)
    metryka_2026 = _metryka(autor, dyscyplina, okres_2026, uczelnia)

    _wybierz_okres(admin_client, okres_2026)
    with patch("celery.chain") as chain:
        admin_client.get(reverse("ewaluacja_optymalizacja:analyze-unpinning"))

    assert MetrykaAutora.objects.filter(pk=metryka_2022.pk).exists()
    assert not MetrykaAutora.objects.filter(pk=metryka_2026.pk).exists()

    # Przeliczenie metryk i analiza dostają ten sam (wybrany) okres
    metryki_sig, unpinning_sig = chain.call_args.args
    assert metryki_sig.kwargs["okres_pk"] == okres_2026.pk
    assert unpinning_sig.kwargs["okres_pk"] == okres_2026.pk


@pytest.mark.django_db
def test_unpinning_analysis_metryki_tylko_z_okresu(uczelnia, okres_2022, okres_2026):
    """Analiza odpinania (zadanie z ``okres_pk``) ładuje metryki tylko z okresu
    zadania."""
    from ewaluacja_optymalizacja.tasks.unpinning.analysis import (
        _analyze_multi_author_works_impl,
    )

    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Okresowa", kod="9.9")
    _metryka(baker.make(Autor), dyscyplina, okres_2022, uczelnia)
    _metryka(baker.make(Autor), dyscyplina, okres_2026, uczelnia)
    _metryka(baker.make(Autor), dyscyplina, okres_2026, uczelnia)

    task = MagicMock()
    _analyze_multi_author_works_impl(
        task, uczelnia.pk, parallel=False, okres_pk=okres_2026.pk
    )

    zaladowane = [
        c.kwargs["meta"]["metrics_loaded"]
        for c in task.update_state.call_args_list
        if "metrics_loaded" in c.kwargs.get("meta", {})
    ]
    assert zaladowane == [2]
