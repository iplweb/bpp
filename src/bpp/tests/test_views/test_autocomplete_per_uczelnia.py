import pytest

from bpp.models import Jednostka
from fixtures.conftest_multisite import make_request_for_site


@pytest.mark.django_db
def test_jednostka_autocomplete_zawezony_do_uczelni(
    uczelnia1, uczelnia2, site1, jednostka_uczelnia1, jednostka_uczelnia2, settings
):
    settings.ALLOWED_HOSTS = ["*"]
    from bpp.views.autocomplete.units import WidocznaJednostkaAutocomplete

    # WidocznaJednostkaAutocomplete.qset = Jednostka.objects.widoczne(), tj.
    # filter(widoczna=True). Pole `widoczna` ma default=True, ale ustawiamy je
    # jawnie na obu jednostkach, by test mierzył filtr per-uczelnia, a nie
    # widoczność.
    Jednostka.objects.filter(
        pk__in=[jednostka_uczelnia1.pk, jednostka_uczelnia2.pk]
    ).update(widoczna=True)

    view = WidocznaJednostkaAutocomplete()
    view.request = make_request_for_site(site1)
    view.q = ""
    pks = set(view.get_queryset().values_list("pk", flat=True))
    assert jednostka_uczelnia1.pk in pks
    assert jednostka_uczelnia2.pk not in pks
