"""Testy dwukolumnowego układu paneli na stronie przemapowania.

Lewy panel „Źródło źródłowe" (statyczny, renderowany server-side) i prawy panel
„Źródło docelowe" (wypełniany JS-em po zmianie comboboxa). Testujemy tylko część
renderowaną po stronie serwera — samo zachowanie JS jest sprawdzane manualnie /
w Playwright.
"""

import pytest
from django.urls import reverse
from model_bakery import baker


@pytest.mark.django_db
def test_source_panel_shows_bppid(client_with_group):
    """Panel źródłowy pokazuje BPP ID (pk) — wcześniej go brakowało."""
    zrodlo = baker.make("bpp.Zrodlo", nazwa="X")
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo)

    url = reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo.slug])
    content = client_with_group.get(url).content.decode()

    assert "BPP ID" in content
    assert 'id="src-bppid"' in content
    assert f">{zrodlo.pk}</span>" in content


@pytest.mark.django_db
def test_target_panel_container_present(client_with_group):
    """Prawy panel „Źródło docelowe" istnieje w DOM (kontener dla JS)."""
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo)

    url = reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo.slug])
    content = client_with_group.get(url).content.decode()

    assert 'id="dst-panel"' in content
    assert "Źródło docelowe" in content


@pytest.mark.django_db
def test_info_url_available_for_js(client_with_group):
    """Szablon udostępnia bazowy URL endpointu info, żeby JS mógł go złożyć."""
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo)

    url = reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo.slug])
    content = client_with_group.get(url).content.decode()

    info_base = reverse("przemapuj_zrodlo:info", args=[0]).rsplit("0/", 1)[0]
    assert info_base in content


@pytest.mark.django_db
def test_context_has_src_mnisw_effective(client_with_group):
    """Kontekst niesie efektywne MNiSW ID źródła (dla reguły blokady w JS)."""
    from pbn_api.models import Journal

    journal = baker.make(Journal, mniswId=555, status="CURRENT", title="J")
    zrodlo = baker.make("bpp.Zrodlo", pbn_uid=journal)
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo)

    url = reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo.slug])
    resp = client_with_group.get(url)

    assert resp.context["src_mnisw_effective"] == 555


@pytest.mark.django_db
def test_context_src_mnisw_effective_none_when_not_ministerial(client_with_group):
    """Źródło bez MNiSW ID → src_mnisw_effective is None."""
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo)

    url = reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo.slug])
    resp = client_with_group.get(url)

    assert resp.context["src_mnisw_effective"] is None
