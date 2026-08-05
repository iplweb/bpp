"""Multi-hosted: przeglądanie jednostek (`/bpp/jednostki/`) zawężone do uczelni.

`JednostkiView` musi pokazywać wyłącznie jednostki bieżącej uczelni (rozwiązanej
z hosta przez `Uczelnia.objects.get_for_request`). Dotyczy to ZARÓWNO listy
paginowanej (`get_queryset`), JAK I paska liter A–Z (`available_letters` w
`get_context_data`) — inaczej pasek reklamowałby litery istniejące tylko dla
jednostek innej uczelni.

Wzorzec: `bpp/tests/test_views/test_autocomplete_per_uczelnia.py`.
"""

import pytest

from bpp.models import Jednostka
from fixtures.conftest_multisite import make_request_for_site


def _jednostki_view_dla_site(site):
    from bpp.views.browse import JednostkiView

    view = JednostkiView()
    view.request = make_request_for_site(site)
    view.kwargs = {}
    return view


@pytest.mark.django_db
def test_jednostki_view_zawezone_do_uczelni(
    uczelnia1, uczelnia2, site1, jednostka_uczelnia1, jednostka_uczelnia2, settings
):
    """Multi-hosted: lista jednostek pokazuje tylko jednostki uczelni z hosta."""
    settings.ALLOWED_HOSTS = ["*"]

    view = _jednostki_view_dla_site(site1)
    pks = set(view.get_queryset().values_list("pk", flat=True))

    assert jednostka_uczelnia1.pk in pks
    assert jednostka_uczelnia2.pk not in pks


@pytest.mark.django_db
def test_jednostki_view_pasek_liter_zawezony_do_uczelni(
    uczelnia1, uczelnia2, site1, wydzial_uczelnia1, wydzial_uczelnia2, settings
):
    """Pasek liter A–Z odzwierciedla tylko jednostki uczelni oglądającego.

    U1 ma jednostkę na 'A', U2 na 'B'. Oglądając U1 widzimy 'a', nie 'b'.
    """
    settings.ALLOWED_HOSTS = ["*"]

    Jednostka.objects.create(
        uczelnia=uczelnia1,
        parent=wydzial_uczelnia1,
        skrot="ALFA-U1",
        nazwa="Alfa Jednostka U1",
    )
    Jednostka.objects.create(
        uczelnia=uczelnia2,
        parent=wydzial_uczelnia2,
        skrot="BETA-U2",
        nazwa="Beta Jednostka U2",
    )

    view = _jednostki_view_dla_site(site1)
    view.object_list = view.get_queryset()
    available = view.get_context_data()["available_letters"]

    assert "A" in available
    assert "B" not in available


@pytest.mark.django_db
def test_jednostki_view_single_install_pokazuje_wszystkie(
    uczelnia1, site1, wydzial_uczelnia1, settings
):
    """Single-install: guard `tylko_jedna_uczelnia` czyni filtr no-opem.

    Jednostka bez powiązania z żadną drugą uczelnią pozostaje widoczna —
    przy jednej uczelni nie ma czego zawężać.
    """
    settings.ALLOWED_HOSTS = ["*"]
    from bpp.models import Uczelnia

    assert Uczelnia.objects.count() == 1, "to ma być scenariusz single-install"

    jedn = Jednostka.objects.create(
        uczelnia=uczelnia1,
        parent=wydzial_uczelnia1,
        skrot="J-SINGLE",
        nazwa="Jednostka Single",
    )

    view = _jednostki_view_dla_site(site1)
    pks = set(view.get_queryset().values_list("pk", flat=True))
    assert jedn.pk in pks


@pytest.mark.django_db
def test_scope_jednostki_do_uczelni_helper(
    uczelnia1, uczelnia2, jednostka_uczelnia1, jednostka_uczelnia2
):
    """Sam helper: przy ≥2 uczelniach filtruje po FK `uczelnia`."""
    from bpp.util.uczelnia_scope import scope_jednostki_do_uczelni

    qs = scope_jednostki_do_uczelni(Jednostka.objects.all(), uczelnia1)
    pks = set(qs.values_list("pk", flat=True))

    assert jednostka_uczelnia1.pk in pks
    assert jednostka_uczelnia2.pk not in pks


@pytest.mark.django_db
def test_scope_jednostki_do_uczelni_brak_uczelni_to_noop(
    uczelnia1, uczelnia2, jednostka_uczelnia1, jednostka_uczelnia2
):
    """Helper no-op gdy uczelnia=None (nierozwiązany host) — bezpieczny fallback."""
    from bpp.util.uczelnia_scope import scope_jednostki_do_uczelni

    qs = scope_jednostki_do_uczelni(Jednostka.objects.all(), None)
    pks = set(qs.values_list("pk", flat=True))

    assert jednostka_uczelnia1.pk in pks
    assert jednostka_uczelnia2.pk in pks
