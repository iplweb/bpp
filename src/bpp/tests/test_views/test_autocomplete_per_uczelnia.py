import pytest
from django.urls import NoReverseMatch, reverse

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


def test_wydzial_autocomplete_endpointy_usuniete():
    # Faza C (#438): autocomplety Wydzialu znikają razem z modelem. „Wydział" =
    # top-level Jednostka, więc picker „wydziału" to
    # public-jednostka-toplevel-autocomplete (per-uczelnia — patrz test niżej).
    for name in ("bpp:wydzial-autocomplete", "bpp:public-wydzial-autocomplete"):
        with pytest.raises(NoReverseMatch):
            reverse(name)


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
    from bpp.views.autocomplete.units import JednostkaAutocomplete

    assert not issubclass(JednostkaAutocomplete, UczelniaScopedAutocompleteMixin)
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
def test_public_autor_autocomplete_plaska_lista_bez_optgroup(
    uczelnia1, uczelnia2, site1, jednostka_uczelnia1, autor_uczelnia1, settings
):
    """Publiczny picker autorów zwraca PŁASKĄ listę (bez optgroup).

    Grupowanie z ``AutorAutocompleteBase`` emitowało nagłówek optgroup w każdej
    stronie odpowiedzi Select2 → przy przewijaniu „✅ Autorzy z naszej uczelni"
    powielał się. Publiczny picker ma listę płaską (klucz ``children`` nie
    występuje).
    """
    settings.ALLOWED_HOSTS = ["*"]
    from model_bakery import baker

    from bpp.views.autocomplete.authors import PublicAutorAutocomplete

    baker.make("bpp.Autor", aktualna_jednostka=jednostka_uczelnia1)

    view = PublicAutorAutocomplete()
    view.request = make_request_for_site(site1)
    view.q = ""
    context = {"object_list": list(view.get_queryset())}
    results = view.get_results(context)

    assert results, "brak wyników w teście"
    assert all("children" not in r for r in results), "wciąż są optgroupy"
    assert all(r["id"] for r in results), "element bez id (nagłówek grupy)"


@pytest.mark.django_db
def test_public_autor_autocomplete_single_install_tylko_uczelnia(
    uczelnia1, site1, jednostka_uczelnia1, autor_uczelnia1, settings
):
    """Single-install: publiczny picker pokazuje TYLKO autorów z uczelni.

    Mixin scope'ujący jest no-op przy jednej uczelni (``tylko_jedna_uczelnia``),
    więc bez własnego filtra autor zewnętrzny (bez afiliacji) by przeciekł.
    """
    settings.ALLOWED_HOSTS = ["*"]
    from model_bakery import baker

    from bpp.models import Uczelnia
    from bpp.views.autocomplete.authors import PublicAutorAutocomplete

    assert Uczelnia.objects.count() == 1, "to ma być scenariusz single-install"

    zewnetrzny = baker.make("bpp.Autor", aktualna_jednostka=None)

    view = PublicAutorAutocomplete()
    view.request = make_request_for_site(site1)
    view.q = ""
    pks = set(view.get_queryset().values_list("pk", flat=True))
    assert autor_uczelnia1.pk in pks
    assert zewnetrzny.pk not in pks


@pytest.mark.django_db
def test_autor_aktualnie_zatrudniony_tylko_aktualna_jednostka(
    uczelnia1,
    uczelnia2,
    site1,
    jednostka_uczelnia1,
    jednostka_uczelnia2,
    autor_uczelnia1,
    autor_uczelnia2,
    settings,
):
    """``AutorAktualnieZatrudnionyNaUczelni`` zawęża po
    ``aktualna_jednostka__uczelnia`` ORAZ ``skupia_pracownikow=True`` (zakres
    ``aktualnie_zatrudnieni``).

    Aktualnie zatrudniony w U1 (realna jednostka) → jest. Aktualny w U2 →
    odpada. Bez aktualnej jednostki (niezatrudniony / tylko historia) → odpada.
    Aktualna jednostka obca/techniczna (``skupia_pracownikow=False``) → odpada.
    Lista płaska.
    """
    settings.ALLOWED_HOSTS = ["*"]
    from model_bakery import baker

    from bpp.views.autocomplete.authors import AutorAktualnieZatrudnionyNaUczelni

    # niezatrudniony aktualnie nigdzie (np. tylko historia) → poza zakresem
    autor_bez_aktualnej = baker.make("bpp.Autor", aktualna_jednostka=None)

    # aktualna jednostka obca (nie skupia pracowników) → poza zakresem
    obca = baker.make("bpp.Jednostka", uczelnia=uczelnia1, skupia_pracownikow=False)
    autor_w_obcej = baker.make("bpp.Autor", aktualna_jednostka=obca)

    view = AutorAktualnieZatrudnionyNaUczelni()
    view.request = make_request_for_site(site1)
    view.q = ""
    pks = set(view.get_queryset().values_list("pk", flat=True))

    assert autor_uczelnia1.pk in pks  # aktualnie zatrudniony w U1
    assert autor_uczelnia2.pk not in pks  # aktualny w U2 → odpada
    assert autor_bez_aktualnej.pk not in pks  # brak aktualnej jednostki → odpada
    assert autor_w_obcej.pk not in pks  # aktualna jednostka obca → odpada

    context = {"object_list": list(view.get_queryset())}
    results = view.get_results(context)
    assert all("children" not in r for r in results), "lista ma być płaska"


@pytest.mark.django_db
def test_create_from_string_honoruje_podana_uczelnie(uczelnia1, uczelnia2):
    """``AutorManager.create_from_string`` czyta ``nowy_autor_z_formularza_pokazuj``
    z PODANEJ uczelni, nie z pierwszej-z-brzegu (``Uczelnia.objects.first()``).
    """
    from bpp.models import Autor

    uczelnia1.nowy_autor_z_formularza_pokazuj = False
    uczelnia1.save()
    uczelnia2.nowy_autor_z_formularza_pokazuj = True
    uczelnia2.save()

    # uczelnia2 (wyższy pk) NIE jest first() — first() to uczelnia1 (False).
    autor = Autor.objects.create_from_string("Kowalski Jan", uczelnia=uczelnia2)
    assert autor.pokazuj is True

    autor2 = Autor.objects.create_from_string("Nowak Anna", uczelnia=uczelnia1)
    assert autor2.pokazuj is False


@pytest.mark.django_db
def test_create_from_string_bez_uczelni_wiele_uczelni_nie_zgaduje(uczelnia1, uczelnia2):
    """Bez podanej uczelni i przy >1 uczelni: get_single_uczelnia_or_none → None
    → ``pokazuj=False`` (bezpieczny default), bez zgadywania pierwszej-z-brzegu.
    """
    from bpp.models import Autor

    uczelnia1.nowy_autor_z_formularza_pokazuj = True  # first(), gdyby zgadywał
    uczelnia1.save()

    autor = Autor.objects.create_from_string("Bezuczelni Ktos")
    assert autor.pokazuj is False


@pytest.mark.django_db
def test_autor_autocomplete_create_object_uzywa_uczelni_z_requestu(
    uczelnia1, uczelnia2, site2, settings
):
    """``AutorAutocomplete.create_object`` ustala ``pokazuj`` nowego autora z
    uczelni Z REQUESTU (host), nie z pierwszej-z-brzegu.
    """
    settings.ALLOWED_HOSTS = ["*"]
    from bpp.models import Autor, BppUser
    from bpp.views.autocomplete.authors import AutorAutocomplete

    uczelnia1.nowy_autor_z_formularza_pokazuj = False  # first()
    uczelnia1.save()
    uczelnia2.nowy_autor_z_formularza_pokazuj = True
    uczelnia2.save()

    user = BppUser.objects.create_user(username="ac_creator", is_staff=True)

    view = AutorAutocomplete()
    view.request = make_request_for_site(site2, user=user)  # → uczelnia2

    obj = view.create_object("Iksinski Piotr")

    assert isinstance(obj, Autor)
    assert obj.pokazuj is True  # z uczelni2 (request), nie z first()=uczelnia1


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
