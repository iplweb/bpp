from decimal import Decimal
from unittest.mock import patch

import pytest
from model_bakery import baker

from ewaluacja_metryki.models import MetrykaAutora, StatusGenerowania


def _make_metryka(autor, dyscyplina, uczelnia, **kw):
    defaults = dict(
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("2.0"),
        punkty_nazbierane=Decimal("100.0"),
        slot_wszystkie=Decimal("3.0"),
        punkty_wszystkie=Decimal("150.0"),
    )
    defaults.update(kw)
    return MetrykaAutora.objects.create(
        autor=autor, dyscyplina_naukowa=dyscyplina, uczelnia=uczelnia, **defaults
    )


@pytest.mark.django_db
def test_metryka_ma_uczelnia(autor_jan_kowalski, dyscyplina1):
    u = baker.make("bpp.Uczelnia")
    m = _make_metryka(autor_jan_kowalski, dyscyplina1, u)
    assert m.uczelnia_id == u.pk


@pytest.mark.django_db
def test_metryka_unique_together_z_uczelnia(autor_jan_kowalski, dyscyplina1):
    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    # ta sama (autor, dyscyplina), różne uczelnie → OK (rozłączne metryki)
    _make_metryka(autor_jan_kowalski, dyscyplina1, u1)
    _make_metryka(autor_jan_kowalski, dyscyplina1, u2)
    assert MetrykaAutora.objects.count() == 2


@pytest.mark.django_db
def test_status_generowania_per_uczelnia():
    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    s1 = StatusGenerowania.get_or_create(uczelnia=u1)
    s2 = StatusGenerowania.get_or_create(uczelnia=u2)
    assert s1.pk != s2.pk
    assert s1.uczelnia_id == u1.pk
    assert s2.uczelnia_id == u2.pk


@pytest.mark.django_db
def test_oblicz_metryki_dla_autora_nie_sumuje_slotow_z_innej_uczelni(
    autor_jan_kowalski, dyscyplina1
):
    """Regresja R2: slot_maksymalny nie może sumować udziałów wszystkich uczelni."""
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
    from ewaluacja_metryki.utils import oblicz_metryki_dla_autora

    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    IloscUdzialowDlaAutoraZaCalosc.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=None,
        ilosc_udzialow=Decimal("4.0"),
        ilosc_udzialow_monografie=Decimal("0"),
        uczelnia=u1,
    )
    IloscUdzialowDlaAutoraZaCalosc.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=None,
        ilosc_udzialow=Decimal("9.0"),
        ilosc_udzialow_monografie=Decimal("0"),
        uczelnia=u2,
    )
    metryka, _ = oblicz_metryki_dla_autora(
        autor=autor_jan_kowalski, dyscyplina=dyscyplina1, uczelnia=u1
    )
    # slot_maksymalny = 4.0 (tylko u1), NIE 13.0 (suma u1+u2)
    assert metryka.slot_maksymalny == Decimal("4.0")
    assert metryka.uczelnia_id == u1.pk


@pytest.mark.django_db
def test_command_oblicz_metryki_scope_uczelnia(
    autor_jan_kowalski, dyscyplina1, rodzaj_autora_n
):
    """Komenda oblicz_metryki z --uczelnia-id scope'uje delete i źródłowy QS.

    Asercja pozytywna: komenda musi wygenerować metrykę dla u1.
    Asercja negatywna: istniejąca metryka u2 (sprzed uruchomienia) musi
    przeżyć (scoped --nadpisz nie wyciera obcej uczelni).
    """
    from django.core.management import call_command

    from bpp.models import Autor_Dyscyplina
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    _make_metryka(autor_jan_kowalski, dyscyplina1, u2)  # must survive

    # IloscUdzialowDlaAutoraZaCalosc dla u1 — źródło slot_maksymalny
    IloscUdzialowDlaAutoraZaCalosc.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=None,
        ilosc_udzialow=Decimal("4.0"),
        ilosc_udzialow_monografie=Decimal("0"),
        uczelnia=u1,
    )

    # Autor_Dyscyplina wymagany przez _should_skip_author (rok w 2022-2025,
    # rodzaj_autora.skrot == "N" pasujący do --rodzaje-autora N)
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=2022,
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=Decimal("1.0"),
        procent_dyscypliny=Decimal("100.0"),
        rodzaj_autora=rodzaj_autora_n,
    )

    # Mockujemy _calculate_metrics_data — zbieraj_sloty potrzebuje cache
    # który jest pusty w tym teście; interesuje nas tu tylko logika scope'owania.
    with patch("ewaluacja_metryki.utils._calculate_metrics_data") as mock_calc:
        mock_calc.return_value = {
            "punkty_nazbierane": Decimal("100.0"),
            "prace_nazbierane_ids": [],
            "slot_nazbierany": Decimal("2.0"),
            "punkty_wszystkie": Decimal("100.0"),
            "prace_wszystkie_ids": [],
            "slot_wszystkie": Decimal("2.0"),
        }
        call_command(
            "oblicz_metryki",
            "--bez-liczby-n",
            "--nadpisz",
            "--uczelnia-id",
            str(u1.pk),
            "--rodzaje-autora",
            "N",
        )

    assert MetrykaAutora.objects.filter(uczelnia=u1).exists()  # u1 wygenerowana
    assert MetrykaAutora.objects.filter(uczelnia=u2).exists()  # u2 nietknięta


@pytest.mark.django_db
def test_generuj_metryki_task_scope_per_uczelnia(autor_jan_kowalski, dyscyplina1):
    """Task generuje metryki tylko dla swojej uczelni, nie wyciera innej."""
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
    from ewaluacja_metryki.tasks import generuj_metryki_task

    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    # istniejąca metryka u2 — nie wolno jej skasować
    _make_metryka(autor_jan_kowalski, dyscyplina1, u2)
    IloscUdzialowDlaAutoraZaCalosc.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=None,
        ilosc_udzialow=Decimal("4.0"),
        ilosc_udzialow_monografie=Decimal("0"),
        uczelnia=u1,
    )
    generuj_metryki_task(
        uczelnia_id=u1.pk, przelicz_liczbe_n=False, rodzaje_autora=[" "]
    )
    # metryka u2 nadal istnieje (scoped delete nie wyciera obcej uczelni)
    assert MetrykaAutora.objects.filter(uczelnia=u2).exists()


@pytest.mark.django_db
def test_scope_metryki_single_install_noop(autor_jan_kowalski, dyscyplina1):
    from ewaluacja_metryki.uczelnia_scope import scope_metryki

    u = baker.make("bpp.Uczelnia")  # dokładnie 1 uczelnia
    _make_metryka(autor_jan_kowalski, dyscyplina1, u)
    qs = scope_metryki(MetrykaAutora.objects.all(), u)
    assert qs.count() == 1  # no-op, nie filtruje


@pytest.mark.django_db
def test_scope_metryki_multi_filtruje(autor_jan_kowalski, dyscyplina1):
    from ewaluacja_metryki.uczelnia_scope import scope_metryki

    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    autor2 = baker.make("bpp.Autor")
    _make_metryka(autor_jan_kowalski, dyscyplina1, u1)
    _make_metryka(autor2, dyscyplina1, u2)
    qs = scope_metryki(MetrykaAutora.objects.all(), u1)
    assert list(qs.values_list("uczelnia_id", flat=True)) == [u1.pk]


@pytest.mark.django_db
def test_lista_metryk_filtruje_po_uczelni(
    client, settings, django_user_model, dyscyplina1, uczelnia1, uczelnia2, site1
):
    from django.urls import reverse

    settings.ALLOWED_HOSTS = ["*"]
    autor1 = baker.make("bpp.Autor")
    autor2 = baker.make("bpp.Autor")
    _make_metryka(autor1, dyscyplina1, uczelnia1)
    _make_metryka(autor2, dyscyplina1, uczelnia2)

    su = django_user_model.objects.create_superuser("su_d7", "su_d7@x.pl", "x")
    client.force_login(su)
    resp = client.get(reverse("ewaluacja_metryki:lista"), HTTP_HOST=site1.domain)
    assert resp.status_code == 200
    uczelnie = {m.uczelnia_id for m in resp.context["metryki"]}
    assert uczelnie == {uczelnia1.pk}  # tylko uczelnia z site1, nie uczelnia2


@pytest.mark.django_db
def test_autor_discipline_count_scoped_per_uczelnia(
    client,
    settings,
    django_user_model,
    dyscyplina1,
    dyscyplina2,
    uczelnia1,
    uczelnia2,
    site1,
):
    """Regresja D/Fix-1: autor_discipline_count zlicza dyscypliny TYLKO z uczelni oglądanej.

    Autor ma 1 dyscyplinę w u1 i 1 dyscyplinę w u2.
    Gdy patrzymy przez site1 (→ uczelnia1), annotacja powinna wynosić 1, nie 2.
    """
    from django.urls import reverse

    settings.ALLOWED_HOSTS = ["*"]
    autor = baker.make("bpp.Autor")
    _make_metryka(autor, dyscyplina1, uczelnia1)
    _make_metryka(autor, dyscyplina2, uczelnia2)

    su = django_user_model.objects.create_superuser("su_disc", "su_disc@x.pl", "x")
    client.force_login(su)
    resp = client.get(reverse("ewaluacja_metryki:lista"), HTTP_HOST=site1.domain)
    assert resp.status_code == 200

    metryki = list(resp.context["metryki"])
    # Site1 → uczelnia1: only the u1 metryka should be visible
    assert len(metryki) == 1
    assert metryki[0].uczelnia_id == uczelnia1.pk
    # discipline_count must reflect only u1 disciplines (1), not u1+u2 total (2)
    assert metryki[0].autor_discipline_count == 1
