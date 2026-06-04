import pytest

from bpp.models import Jednostka, Wydzial
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


@pytest.mark.django_db
def test_wydzial_autocomplete_zawezony_do_uczelni(
    uczelnia1, uczelnia2, site1, wydzial_uczelnia1, wydzial_uczelnia2, settings
):
    settings.ALLOWED_HOSTS = ["*"]
    from bpp.views.autocomplete.simple import PublicWydzialAutocomplete

    # PublicWydzialAutocomplete.qset = Wydzial.objects.filter(widoczny=True).
    # Pole `widoczny` ma default=True, ale ustawiamy je jawnie na obu
    # wydziałach, by test mierzył filtr per-uczelnia, a nie widoczność.
    Wydzial.objects.filter(pk__in=[wydzial_uczelnia1.pk, wydzial_uczelnia2.pk]).update(
        widoczny=True
    )

    view = PublicWydzialAutocomplete()
    view.request = make_request_for_site(site1)
    view.q = ""
    pks = set(view.get_queryset().values_list("pk", flat=True))
    assert wydzial_uczelnia1.pk in pks
    assert wydzial_uczelnia2.pk not in pks


@pytest.mark.django_db
def test_autor_autocomplete_kiedykolwiek_zwiazany(
    uczelnia1,
    uczelnia2,
    site1,
    jednostka_uczelnia1,
    jednostka_uczelnia2,
    autor_uczelnia1,
    autor_uczelnia2,
    settings,
):
    settings.ALLOWED_HOSTS = ["*"]
    from model_bakery import baker

    from bpp.views.autocomplete.authors import PublicAutorAutocomplete

    # autor historyczny: aktualna jednostka w U2, ale wpis Autor_Jednostka w U1
    autor_hist = baker.make("bpp.Autor", aktualna_jednostka=jednostka_uczelnia2)
    baker.make("bpp.Autor_Jednostka", autor=autor_hist, jednostka=jednostka_uczelnia1)

    view = PublicAutorAutocomplete()
    view.request = make_request_for_site(site1)
    view.q = ""
    pks = set(view.get_queryset().values_list("pk", flat=True))
    assert autor_uczelnia1.pk in pks  # obecny pracownik U1
    assert autor_hist.pk in pks  # historycznie związany z U1
    assert autor_uczelnia2.pk not in pks  # tylko U2 → zewnętrzny dla U1


@pytest.mark.django_db
def test_autor_autocomplete_dedup_wielokrotna_historia(
    uczelnia1, uczelnia2, site1, jednostka_uczelnia1, settings
):
    """Autor z wieloma wpisami Autor_Jednostka w U1 pojawia się DOKŁADNIE raz
    (kontrakt .distinct() — join po historii mnoży wiersze)."""
    settings.ALLOWED_HOSTS = ["*"]
    from model_bakery import baker

    from bpp.views.autocomplete.authors import PublicAutorAutocomplete

    # druga jednostka tej samej uczelni U1, by autor miał 2 wpisy historii w U1
    jedn_u1_b = baker.make("bpp.Jednostka", uczelnia=uczelnia1)
    autor = baker.make("bpp.Autor", aktualna_jednostka=jednostka_uczelnia1)
    baker.make("bpp.Autor_Jednostka", autor=autor, jednostka=jednostka_uczelnia1)
    baker.make("bpp.Autor_Jednostka", autor=autor, jednostka=jedn_u1_b)

    view = PublicAutorAutocomplete()
    view.request = make_request_for_site(site1)
    view.q = ""
    pk_list = list(view.get_queryset().values_list("pk", flat=True))
    assert pk_list.count(autor.pk) == 1  # nie zduplikowany mimo 2 wpisów historii


def test_admin_autocomplety_nie_sa_zawezone():
    """Admin/edytor autocomplety NIE dziedziczą scopingu — pełny dostęp do
    wszystkich uczelni (multi-hosted: tylko publiczne pickery są zawężone)."""
    from bpp.views.autocomplete.authors import AutorAutocomplete
    from bpp.views.autocomplete.mixins import UczelniaScopedAutocompleteMixin
    from bpp.views.autocomplete.simple import WydzialAutocomplete
    from bpp.views.autocomplete.units import JednostkaAutocomplete

    assert not issubclass(JednostkaAutocomplete, UczelniaScopedAutocompleteMixin)
    assert not issubclass(WydzialAutocomplete, UczelniaScopedAutocompleteMixin)
    assert not issubclass(AutorAutocomplete, UczelniaScopedAutocompleteMixin)


@pytest.mark.django_db
def test_public_jednostka_autocomplete_zawezony_do_uczelni(
    uczelnia1, uczelnia2, site1, jednostka_uczelnia1, jednostka_uczelnia2, settings
):
    settings.ALLOWED_HOSTS = ["*"]
    from bpp.views.autocomplete.units import PublicJednostkaAutocomplete

    # PublicJednostkaAutocomplete używa Jednostka.objects.publiczne(), tj.
    # widoczne().filter(aktualna=True) → filter(widoczna=True, aktualna=True).
    # `aktualna` ma default=False, więc fixtury (Jednostka.objects.create bez
    # tego pola) NIE są publiczne. Ustawiamy widoczna=True ORAZ aktualna=True na
    # obu jednostkach, by test mierzył filtr per-uczelnia, a nie publiczność.
    Jednostka.objects.filter(
        pk__in=[jednostka_uczelnia1.pk, jednostka_uczelnia2.pk]
    ).update(widoczna=True, aktualna=True)

    view = PublicJednostkaAutocomplete()
    view.request = make_request_for_site(site1)
    view.q = ""
    pks = set(view.get_queryset().values_list("pk", flat=True))
    assert jednostka_uczelnia1.pk in pks
    assert jednostka_uczelnia2.pk not in pks


@pytest.mark.django_db
def test_autocomplete_get_queryset_bez_requestu_nie_wywala(uczelnia1, uczelnia2):
    """Mixin toleruje brak self.request (no-op) — kontrakt defensywny bazy.

    Niektóre testy/ścieżki instancjonują widok bez requestu i wołają
    get_queryset() bezpośrednio; mixin nie może na tym wywalić AttributeError.
    """
    from bpp.views.autocomplete.units import WidocznaJednostkaAutocomplete

    view = WidocznaJednostkaAutocomplete()  # brak view.request
    view.q = ""
    # nie powinno rzucić AttributeError — po prostu nie zawęża
    list(view.get_queryset())
