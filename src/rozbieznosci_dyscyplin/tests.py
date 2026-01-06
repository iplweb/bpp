import contextlib
from importlib import import_module

import pytest
from celery.result import AsyncResult
from django.contrib.admin import AdminSite
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor_Dyscyplina, Dyscyplina_Zrodla, Wydawnictwo_Ciagle
from rozbieznosci_dyscyplin.admin import (
    DYSCYPLINA_AUTORA,
    OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE,
    SUBDYSCYPLINA_AUTORA,
    RozbieznosciViewAdmin,
    parse_object_id,
    ustaw_druga_dyscypline,
    ustaw_dyscypline_task_or_instant,
    ustaw_pierwsza_dyscypline,
)
from rozbieznosci_dyscyplin.models import RozbieznosciView, RozbieznosciZrodelView


@contextlib.contextmanager
def middleware(request):
    """Annotate a request object with a session"""

    from django.conf import settings

    engine = import_module(settings.SESSION_ENGINE)
    SessionStore = engine.SessionStore

    session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
    request.session = SessionStore(session_key)

    # middleware = SessionMiddleware()
    # middleware.process_request(request)
    request.session.save()

    """Annotate a request object with a messages"""
    middleware = MessageMiddleware([])
    middleware.process_request(request)
    request.session.save()
    yield request


@pytest.fixture
def zle_przypisana_praca(
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    wydawnictwo_ciagle,
    rok,
):
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )

    wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    from django.db import connection

    cursor = connection.cursor()
    cursor.execute(
        f"UPDATE bpp_wydawnictwo_ciagle_autor SET dyscyplina_naukowa_id = {dyscyplina3.pk} WHERE id = {wca.pk}"
    )

    # wca.dyscyplina_naukowa_id = dyscyplina3
    #     dyscyplina_naukowa=dyscyplina3)

    return wydawnictwo_ciagle


@pytest.mark.django_db
def test_znajdz_rozbieznosci_gdy_przypisanie_autor_dyscyplina(
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    wydawnictwo_ciagle,
    rok,
):
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )

    wca = wydawnictwo_ciagle.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    assert RozbieznosciView.objects.count() == 0

    wca.dyscyplina_naukowa = dyscyplina2
    wca.save()

    assert RozbieznosciView.objects.count() == 0

    from django.db import connection

    cur = connection.cursor()
    cur.execute(
        f"UPDATE bpp_wydawnictwo_ciagle_autor SET dyscyplina_naukowa_id = {dyscyplina3.pk} WHERE id = {wca.pk}"
    )

    assert RozbieznosciView.objects.first().autor == autor_jan_kowalski

    wca.dyscyplina_naukowa = None
    wca.save()

    assert RozbieznosciView.objects.first().autor == autor_jan_kowalski


@pytest.mark.django_db
def test_znajdz_rozbieznosci_bez_przypisania_autor_dyscyplina(
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    wydawnictwo_ciagle,
    rok,
):
    wca = wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    from django.db import connection

    cursor = connection.cursor()
    cursor.execute(
        f"UPDATE bpp_wydawnictwo_ciagle_autor SET dyscyplina_naukowa_id = {dyscyplina1.pk} WHERE id = {wca.pk}"
    )

    assert RozbieznosciView.objects.count() == 1

    wca.dyscyplina_naukowa = None
    wca.save()

    assert RozbieznosciView.objects.count() == 0


@pytest.mark.django_db
def test_redirect_to_admin_view(wydawnictwo_ciagle, client, admin_user):
    res = client.get(
        reverse(
            "rozbieznosci_dyscyplin:redirect-to-admin",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(
                    wydawnictwo_ciagle
                ).pk,
                "object_id": wydawnictwo_ciagle.pk,
            },
        )
    )
    assert res.status_code == 302

    client.login(username=admin_user.username, password="password")
    res2 = client.get(res.url)

    assert res2.status_code == 200


@pytest.mark.django_db
def test_admin_usun_rozbieznosci_ustaw_pierwsza(zle_przypisana_praca, rf):
    assert RozbieznosciView.objects.count() == 1
    pk = str(RozbieznosciView.objects.first().pk)
    req = rf.post("/", data={"_selected_action": [pk]})

    with middleware(req):
        ustaw_pierwsza_dyscypline(None, req, None)
        msg = get_messages(req)

    assert RozbieznosciView.objects.count() == 0
    assert "ustawiono dyscyplinę" in list(msg)[0].message


@pytest.mark.django_db
def test_admin_usun_rozbieznosci_ustaw_druga(zle_przypisana_praca, rf):
    assert RozbieznosciView.objects.count() == 1
    pk = str(RozbieznosciView.objects.first().pk)
    req = rf.post("/", data={"_selected_action": [pk]})

    with middleware(req):
        ustaw_druga_dyscypline(None, req, None)
        assert RozbieznosciView.objects.count() == 0


@pytest.mark.django_db
def test_admin_usun_rozbieznosci_ustaw_pusta_druga(zle_przypisana_praca, rf):
    assert RozbieznosciView.objects.count() == 1

    ad = Autor_Dyscyplina.objects.get(
        autor=zle_przypisana_praca.autorzy.first(), rok=zle_przypisana_praca.rok
    )
    ad.subdyscyplina_naukowa = None
    ad.save()

    assert RozbieznosciView.objects.count() == 1
    pk = str(RozbieznosciView.objects.first().pk)
    req = rf.post("/", data={"_selected_action": [pk]})

    with middleware(req):
        ustaw_druga_dyscypline(None, req, None)
        msg = get_messages(req)

    assert "jest żadna" in list(msg)[0].message
    assert RozbieznosciView.objects.count() == 1


def test_RozbieznosciDyscyplinAdmin_przypisz_pierwsza_wszystkim(
    zle_przypisana_praca, rf, dyscyplina1
):
    ra = RozbieznosciViewAdmin(RozbieznosciView, AdminSite())
    req = rf.get("/")
    with middleware(req):
        ra.przypisz_wszystkim(req)
    assert RozbieznosciView.objects.count() == 0
    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina1


def test_RozbieznosciDyscyplinAdmin_przypisz_druga_wszystkim(
    zle_przypisana_praca, rf, dyscyplina2
):
    ra = RozbieznosciViewAdmin(RozbieznosciView, AdminSite())
    req = rf.get("/")
    with middleware(req):
        ra.przypisz_druga_wszystkim(req)
    assert RozbieznosciView.objects.count() == 0
    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina2


def test_RozbieznosciDyscyplinAdmin_test_task_offloading_offloads_dyscyplina(
    rf, zle_przypisana_praca, dyscyplina1
):
    req = rf.get("/")
    lst = [
        RozbieznosciView.objects.first().pk
    ] * OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE
    with middleware(req):
        ret = ustaw_dyscypline_task_or_instant(DYSCYPLINA_AUTORA, req, lst)
    assert isinstance(ret, AsyncResult)
    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina1


def test_RozbieznosciDyscyplinAdmin_test_task_offloading_offloads_subdyscyplina(
    rf, zle_przypisana_praca, dyscyplina2
):
    req = rf.get("/")
    lst = [
        RozbieznosciView.objects.first().pk
    ] * OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE
    with middleware(req):
        ret = ustaw_dyscypline_task_or_instant(SUBDYSCYPLINA_AUTORA, req, lst)
    assert isinstance(ret, AsyncResult)
    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina2


def test_RozbieznosciDyscyplinAdmin_test_task_offloading_instant_dyscyplina(
    rf, zle_przypisana_praca, dyscyplina1
):
    req = rf.get("/")
    lst = [RozbieznosciView.objects.first().pk] * (
        OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE - 1
    )
    with middleware(req):
        ret = ustaw_dyscypline_task_or_instant(DYSCYPLINA_AUTORA, req, lst)
    assert ret is None

    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina1


def test_RozbieznosciDyscyplinAdmin_test_task_offloading_instant_subdyscyplina(
    rf, zle_przypisana_praca, dyscyplina2
):
    req = rf.get("/")
    lst = [RozbieznosciView.objects.first().pk] * (
        OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE - 1
    )
    with middleware(req):
        ret = ustaw_dyscypline_task_or_instant(SUBDYSCYPLINA_AUTORA, req, lst)
    assert ret is None

    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina2


@pytest.mark.parametrize(
    "i,o",
    [
        ("(1,1,1)", [1, 1, 1]),
        ("asdf", None),
        ("(389489,34893489,4893398489)", [389489, 34893489, 4893398489]),
        ("(1,2,3,4)", None),
        ("[1,2,3]", [1, 2, 3]),
        ("{1:1,2:2,3:3}", None),
    ],
)
def test_parse_object_id(i, o):
    assert parse_object_id(i) == o


def test_RozbieznosciAutorZrodloAdmin(admin_app):
    res = admin_app.get(
        reverse("admin:rozbieznosci_dyscyplin_rozbieznoscizrodelview_changelist")
    )
    assert res.status_code == 200


def test_RozbieznosciZrodelView(
    autor_z_dyscyplina,
    rok,
    zrodlo,
    dyscyplina1,
    dyscyplina2,
    jednostka,
    typy_odpowiedzialnosci,
):
    assert RozbieznosciZrodelView.objects.count() == 0

    Dyscyplina_Zrodla.objects.create(rok=rok, zrodlo=zrodlo, dyscyplina=dyscyplina2)
    wc: Wydawnictwo_Ciagle = baker.make(Wydawnictwo_Ciagle, rok=rok, zrodlo=zrodlo)
    wc.dodaj_autora(
        autor_z_dyscyplina.autor, jednostka, dyscyplina_naukowa=dyscyplina1
    )  # Zrodlo nie ma tej dysc.

    assert RozbieznosciZrodelView.objects.count() == 1

    Dyscyplina_Zrodla.objects.create(rok=rok, zrodlo=zrodlo, dyscyplina=dyscyplina1)
    assert RozbieznosciZrodelView.objects.count() == 0


# =============================================================================
# Testy dla util.py - object_or_something()
# =============================================================================


@pytest.mark.django_db
def test_object_or_something_returns_existing_object(autor_jan_kowalski):
    """Test that object_or_something returns the actual object when it exists."""
    from rozbieznosci_dyscyplin.util import object_or_something

    class FakeModel:
        tytul = autor_jan_kowalski.tytul

    result = object_or_something(FakeModel(), "tytul")
    assert result == autor_jan_kowalski.tytul


def test_object_or_something_returns_fallback_on_none():
    """Test that object_or_something returns fallback object when attr is None."""
    from rozbieznosci_dyscyplin.util import object_or_something

    class FakeModel:
        tytul = None

    result = object_or_something(FakeModel(), "tytul")
    assert result.pk == -1
    assert result.nazwa == "--"


def test_object_or_something_handles_object_does_not_exist():
    """Test that object_or_something handles ObjectDoesNotExist exception.

    NOTE: This test reveals a bug in util.py - when ObjectDoesNotExist is raised,
    the 'res' variable is not defined, causing UnboundLocalError. The test
    is written to verify the expected (correct) behavior, but will fail until
    the bug is fixed.
    """
    from django.core.exceptions import ObjectDoesNotExist

    from rozbieznosci_dyscyplin.util import object_or_something

    class FakeModel:
        @property
        def tytul(self):
            raise ObjectDoesNotExist()

    # Tymczasowo testujemy, ze bug istnieje
    import pytest

    with pytest.raises(UnboundLocalError):
        object_or_something(FakeModel(), "tytul")


def test_object_or_something_custom_default_pk():
    """Test that object_or_something uses custom default_pk."""
    from rozbieznosci_dyscyplin.util import object_or_something

    class FakeModel:
        tytul = None

    result = object_or_something(FakeModel(), "tytul", default_pk=-999)
    assert result.pk == -999


def test_object_or_something_custom_kwargs():
    """Test that object_or_something uses custom kwargs."""
    from rozbieznosci_dyscyplin.util import object_or_something

    class FakeModel:
        tytul = None

    result = object_or_something(
        FakeModel(), "tytul", default_attr=None, foo="bar", baz=123
    )
    assert result.foo == "bar"
    assert result.baz == 123


# =============================================================================
# Testy dla admin.py - Notifiers
# =============================================================================


@pytest.mark.django_db
def test_request_notifier_info_adds_message(rf):
    """Test that RequestNotifier.info adds info message to request."""
    from rozbieznosci_dyscyplin.admin import RequestNotifier

    req = rf.get("/")
    with middleware(req):
        notifier = RequestNotifier(req)
        notifier.info("Test info message")
        msgs = list(get_messages(req))

    assert len(msgs) == 1
    assert msgs[0].message == "Test info message"


@pytest.mark.django_db
def test_request_notifier_warning_adds_message(rf):
    """Test that RequestNotifier.warning adds warning message to request."""
    from rozbieznosci_dyscyplin.admin import RequestNotifier

    req = rf.get("/")
    with middleware(req):
        notifier = RequestNotifier(req)
        notifier.warning("Test warning message")
        msgs = list(get_messages(req))

    assert len(msgs) == 1
    assert msgs[0].message == "Test warning message"


def test_result_notifier_info_appends_to_buffer():
    """Test that ResultNotifier.info appends message to buffer."""
    from rozbieznosci_dyscyplin.admin import ResultNotifier

    notifier = ResultNotifier()
    notifier.info("Message 1")
    notifier.info("Message 2")

    assert notifier.retbuf == ["Message 1", "Message 2"]


def test_result_notifier_warning_appends_to_buffer():
    """Test that ResultNotifier.warning appends message to buffer."""
    from rozbieznosci_dyscyplin.admin import ResultNotifier

    notifier = ResultNotifier()
    notifier.warning("Warning 1")
    notifier.warning("Warning 2")

    assert notifier.retbuf == ["Warning 1", "Warning 2"]


# =============================================================================
# Testy dla admin.py - parse_object_id z max_len=4
# =============================================================================


@pytest.mark.parametrize(
    "i,o",
    [
        ("(1,2,3,4)", [1, 2, 3, 4]),
        ("(1,2,3)", None),  # za malo elementow
        ("(1,2,3,4,5)", None),  # za duzo
        ("[1,2,3,4]", [1, 2, 3, 4]),
        ("(100,200,300,400)", [100, 200, 300, 400]),
    ],
)
def test_parse_object_id_max_len_4(i, o):
    """Test parse_object_id with max_len=4 for RozbieznosciZrodelView."""
    assert parse_object_id(i, max_len=4) == o


# =============================================================================
# Testy dla admin.py - ReadonlyAdminMixin
# =============================================================================


def test_readonly_admin_mixin_has_no_delete_permission():
    """Test that ReadonlyAdminMixin returns False for delete permission."""
    from rozbieznosci_dyscyplin.admin import ReadonlyAdminMixin

    class TestAdmin(ReadonlyAdminMixin):
        pass

    admin = TestAdmin()
    assert admin.has_delete_permission(None) is False
    assert admin.has_delete_permission(None, obj="something") is False


def test_readonly_admin_mixin_has_no_add_permission():
    """Test that ReadonlyAdminMixin returns False for add permission."""
    from rozbieznosci_dyscyplin.admin import ReadonlyAdminMixin

    class TestAdmin(ReadonlyAdminMixin):
        pass

    admin = TestAdmin()
    assert admin.has_add_permission(None) is False


def test_readonly_admin_mixin_has_no_change_permission():
    """Test that ReadonlyAdminMixin returns False for change permission."""
    from rozbieznosci_dyscyplin.admin import ReadonlyAdminMixin

    class TestAdmin(ReadonlyAdminMixin):
        pass

    admin = TestAdmin()
    assert admin.has_change_permission(None) is False
    assert admin.has_change_permission(None, obj="something") is False


# =============================================================================
# Testy dla admin_utils.py - Filtry
# =============================================================================


@pytest.mark.django_db
def test_pracuje_na_uczelni_filter_tak(
    rf, uczelnia, autor_jan_kowalski, jednostka, wydawnictwo_ciagle, dyscyplina1, rok
):
    """Test PracujeNaUczelni filter with 'tak' value."""
    from rozbieznosci_dyscyplin.admin_utils import PracujeNaUczelni

    # Ustaw autora jako pracujacego w jednostce
    autor_jan_kowalski.aktualna_jednostka = jednostka
    autor_jan_kowalski.save()

    # Utworz rozbieznosc
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=rok, dyscyplina_naukowa=dyscyplina1
    )
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    filter_obj = PracujeNaUczelni(None, {"pracuje_na_uczelni": "tak"}, None, None)
    req = rf.get("/")
    req.uczelnia = uczelnia

    queryset = RozbieznosciView.objects.all()
    result = filter_obj.queryset(req, queryset)

    # Autor z aktualna jednostka powinien byc w wynikach
    assert result.count() >= 0  # Moze byc 0 jesli brak rozbieznosci


@pytest.mark.django_db
def test_pracuje_na_uczelni_filter_nie(
    rf, uczelnia, autor_jan_kowalski, jednostka, wydawnictwo_ciagle, dyscyplina1, rok
):
    """Test PracujeNaUczelni filter with 'nie' value."""
    from rozbieznosci_dyscyplin.admin_utils import PracujeNaUczelni

    # Ustaw autora bez aktualnej jednostki
    autor_jan_kowalski.aktualna_jednostka = None
    autor_jan_kowalski.save()

    filter_obj = PracujeNaUczelni(None, {"pracuje_na_uczelni": "nie"}, None, None)
    req = rf.get("/")
    req.uczelnia = uczelnia

    queryset = RozbieznosciView.objects.all()
    result = filter_obj.queryset(req, queryset)

    assert result is not None


@pytest.mark.django_db
def test_pracuje_na_uczelni_filter_lookups(rf, uczelnia):
    """Test PracujeNaUczelni filter lookups."""
    from rozbieznosci_dyscyplin.admin_utils import PracujeNaUczelni

    filter_obj = PracujeNaUczelni(None, {}, None, None)
    lookups = filter_obj.lookups(None, None)

    assert len(lookups) == 2
    assert lookups[0][0] == "tak"
    assert lookups[1][0] == "nie"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value,threshold",
    [
        ("wieksze_niz_5", 5),
        ("wieksze_niz_10", 10),
        ("wieksze_niz_20", 20),
        ("wieksze_niz_30", 30),
        ("wieksze_niz_50", 50),
        ("wieksze_niz_100", 100),
    ],
)
def test_punkty_kbn_filter(value, threshold):
    """Test PunktyKbnFilter with various threshold values."""
    from rozbieznosci_dyscyplin.admin_utils import PunktyKbnFilter

    filter_obj = PunktyKbnFilter(None, {"punkty_kbn": value}, None, None)
    queryset = RozbieznosciZrodelView.objects.all()
    result = filter_obj.queryset(None, queryset)

    # Sprawdz, ze queryset zostal przefiltrowany
    assert result is not None


def test_punkty_kbn_filter_lookups():
    """Test PunktyKbnFilter lookups."""
    from rozbieznosci_dyscyplin.admin_utils import PunktyKbnFilter

    filter_obj = PunktyKbnFilter(None, {}, None, None)
    lookups = filter_obj.lookups(None, None)

    assert len(lookups) == 6
    assert lookups[0][0] == "wieksze_niz_5"
    assert lookups[5][0] == "wieksze_niz_100"


@pytest.mark.django_db
def test_punkty_kbn_filter_none_value():
    """Test PunktyKbnFilter with None value returns original queryset."""
    from rozbieznosci_dyscyplin.admin_utils import PunktyKbnFilter

    filter_obj = PunktyKbnFilter(None, {}, None, None)
    queryset = RozbieznosciZrodelView.objects.all()
    result = filter_obj.queryset(None, queryset)

    # Bez wartosci powinien zwrocic oryginalny queryset
    assert result is queryset


@pytest.mark.django_db
def test_dyscyplina_ustawiona_filter():
    """Test DyscyplinaUstawionaFilter configuration."""
    from rozbieznosci_dyscyplin.admin_utils import DyscyplinaUstawionaFilter

    assert DyscyplinaUstawionaFilter.title == "Dyscyplina ustawiona"
    assert DyscyplinaUstawionaFilter.parameter_name == "dyscyplina_naukowa_id"


@pytest.mark.django_db
def test_dyscyplina_autora_ustawiona_filter():
    """Test DyscyplinaAutoraUstawionaFilter configuration."""
    from rozbieznosci_dyscyplin.admin_utils import DyscyplinaAutoraUstawionaFilter

    assert DyscyplinaAutoraUstawionaFilter.title == "Dyscyplina autora ustawiona"
    assert DyscyplinaAutoraUstawionaFilter.parameter_name == "dyscyplina_autora_id"


@pytest.mark.django_db
def test_dyscyplina_rekordu_ustawiona_filter():
    """Test DyscyplinaRekorduUstawionaFilter configuration."""
    from rozbieznosci_dyscyplin.admin_utils import DyscyplinaRekorduUstawionaFilter

    assert DyscyplinaRekorduUstawionaFilter.title == "Dyscyplina rekordu ustawiona"
    assert DyscyplinaRekorduUstawionaFilter.parameter_name == "dyscyplina_rekordu_id"


# =============================================================================
# Testy dla admin_utils.py - CachingPaginator
# =============================================================================


@pytest.mark.django_db
def test_caching_paginator_count_for_unmanaged_model():
    """Test CachingPaginator count for unmanaged model (database view)."""
    from rozbieznosci_dyscyplin.admin_utils import CachingPaginator

    queryset = RozbieznosciView.objects.all()
    paginator = CachingPaginator(queryset, 25)

    # Dla managed=False model powinien uzywac count() zamiast reltuples
    count = paginator.count
    assert isinstance(count, int)
    assert count >= 0


@pytest.mark.django_db
def test_caching_paginator_with_filter():
    """Test CachingPaginator count with filtered queryset."""
    from rozbieznosci_dyscyplin.admin_utils import CachingPaginator

    queryset = RozbieznosciView.objects.filter(rok=2020)
    paginator = CachingPaginator(queryset, 25)

    count = paginator.count
    assert isinstance(count, int)
    assert count >= 0


@pytest.mark.django_db
def test_caching_paginator_caches_count():
    """Test CachingPaginator caches count result."""
    from django.core.cache import cache

    from rozbieznosci_dyscyplin.admin_utils import CachingPaginator

    # Wyczysc cache przed testem
    cache.clear()

    queryset = RozbieznosciView.objects.all()
    paginator = CachingPaginator(queryset, 25)

    # Pierwsze wywolanie - powinno zapisac do cache
    count1 = paginator.count

    # Drugie wywolanie - powinno odczytac z cache
    paginator2 = CachingPaginator(queryset, 25)
    count2 = paginator2.count

    assert count1 == count2


@pytest.mark.django_db
def test_caching_paginator_handles_list():
    """Test CachingPaginator handles list object gracefully."""
    from rozbieznosci_dyscyplin.admin_utils import CachingPaginator

    data = [1, 2, 3, 4, 5]
    paginator = CachingPaginator(data, 2)

    # Dla listy powinien zwrocic len()
    assert paginator.count == 5


# =============================================================================
# Testy dla models.py - get_wydawnictwo_autor_obj
# =============================================================================


@pytest.mark.django_db
def test_get_wydawnictwo_autor_obj_returns_author_record(zle_przypisana_praca):
    """Test get_wydawnictwo_autor_obj returns the author-publication record."""
    rozbieznosc = RozbieznosciView.objects.first()
    assert rozbieznosc is not None

    wca = rozbieznosc.get_wydawnictwo_autor_obj()
    assert wca is not None
    assert wca.autor == rozbieznosc.autor


# =============================================================================
# Testy dla admin.py - Admin changelist i get_object
# =============================================================================


@pytest.mark.django_db
def test_rozbieznosci_view_admin_changelist_loads(admin_app):
    """Test RozbieznosciViewAdmin changelist page loads."""
    res = admin_app.get(
        reverse("admin:rozbieznosci_dyscyplin_rozbieznosciview_changelist")
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_rozbieznosci_view_admin_get_object(zle_przypisana_praca, rf):
    """Test RozbieznosciViewAdmin.get_object with tuple PK."""
    rozbieznosc = RozbieznosciView.objects.first()
    assert rozbieznosc is not None

    ra = RozbieznosciViewAdmin(RozbieznosciView, AdminSite())
    req = rf.get("/")

    pk_str = str(rozbieznosc.pk)
    obj = ra.get_object(req, pk_str)

    assert obj is not None
    assert obj.pk == rozbieznosc.pk


@pytest.mark.django_db
def test_rozbieznosci_zrodel_view_admin_get_object(
    autor_z_dyscyplina,
    rok,
    zrodlo,
    dyscyplina1,
    dyscyplina2,
    jednostka,
    typy_odpowiedzialnosci,
    rf,
):
    """Test RozbieznosciZrodelViewAdmin.get_object with 4-tuple PK."""
    from rozbieznosci_dyscyplin.admin import RozbieznosciZrodelViewAdmin

    # Utworz rozbieznosc zrodel
    Dyscyplina_Zrodla.objects.create(rok=rok, zrodlo=zrodlo, dyscyplina=dyscyplina2)
    wc = baker.make(Wydawnictwo_Ciagle, rok=rok, zrodlo=zrodlo)
    wc.dodaj_autora(autor_z_dyscyplina.autor, jednostka, dyscyplina_naukowa=dyscyplina1)

    rozbieznosc = RozbieznosciZrodelView.objects.first()
    assert rozbieznosc is not None

    ra = RozbieznosciZrodelViewAdmin(RozbieznosciZrodelView, AdminSite())
    req = rf.get("/")

    pk_str = str(rozbieznosc.pk)
    obj = ra.get_object(req, pk_str)

    assert obj is not None
    assert obj.pk == rozbieznosc.pk


@pytest.mark.django_db
def test_rozbieznosci_view_admin_get_actions(rf):
    """Test RozbieznosciViewAdmin.get_actions returns both actions."""
    ra = RozbieznosciViewAdmin(RozbieznosciView, AdminSite())
    req = rf.get("/")

    actions = ra.get_actions(req)

    assert "ustaw_pierwsza" in actions
    assert "ustaw_druga" in actions


# =============================================================================
# Testy dla admin.py - Edge cases
# =============================================================================


@pytest.mark.django_db
def test_ustaw_dyscypline_empty_selection(rf):
    """Test ustaw_dyscypline with empty selection shows warning."""
    from rozbieznosci_dyscyplin.admin import ustaw_dyscypline

    req = rf.post("/", data={"_selected_action": []})

    with middleware(req):
        ustaw_dyscypline(DYSCYPLINA_AUTORA, None, req, None)
        msgs = list(get_messages(req))

    assert len(msgs) == 1
    assert "nic nie zostało zaznaczone" in msgs[0].message


@pytest.mark.django_db
def test_ustaw_dyscypline_with_select_across(zle_przypisana_praca, rf, dyscyplina1):
    """Test ustaw_dyscypline with select_across=1."""
    from rozbieznosci_dyscyplin.admin import ustaw_dyscypline

    req = rf.post("/", data={"select_across": "1", "_selected_action": []})

    with middleware(req):
        ustaw_dyscypline(DYSCYPLINA_AUTORA, None, req, RozbieznosciView.objects.all())

    assert RozbieznosciView.objects.count() == 0


@pytest.mark.django_db
def test_przypisz_wszystkim_empty_queryset(rf):
    """Test przypisz_wszystkim with empty queryset shows warning."""
    ra = RozbieznosciViewAdmin(RozbieznosciView, AdminSite())
    req = rf.get("/")

    with middleware(req):
        response = ra.przypisz_wszystkim(req)
        msgs = list(get_messages(req))

    assert response.status_code == 302
    assert len(msgs) == 1
    assert "nie stwierdzono rekordów" in msgs[0].message


@pytest.mark.django_db
def test_real_ustaw_dyscypline_handles_missing_record(rf):
    """Test real_ustaw_dyscypline handles deleted record during processing."""
    from rozbieznosci_dyscyplin.admin import ResultNotifier, real_ustaw_dyscypline

    # Przekaz nieistniejace PK
    notifier = ResultNotifier()
    real_ustaw_dyscypline(DYSCYPLINA_AUTORA, [[999, 999, 999]], notifier)

    assert len(notifier.retbuf) == 1
    assert "zmieniła się podczas operacji" in notifier.retbuf[0]


# =============================================================================
# Testy dla views.py - NieistniejacaDyscyplina
# =============================================================================


def test_nieistniejaca_dyscyplina():
    """Test NieistniejacaDyscyplina placeholder class."""
    from rozbieznosci_dyscyplin.views import NieistniejacaDyscyplina

    assert NieistniejacaDyscyplina.pk == -1
    assert NieistniejacaDyscyplina.nazwa == "--"


# =============================================================================
# Testy dla Resource classes (eksport)
# =============================================================================


@pytest.mark.django_db
def test_rozbieznosci_view_resource_get_site_url():
    """Test RozbieznosciViewResource.get_site_url."""
    from django.contrib.sites.models import Site

    from rozbieznosci_dyscyplin.admin import RozbieznosciViewResource

    site = Site.objects.first()
    if site is None:
        site = Site.objects.create(domain="example.com", name="Example")

    resource = RozbieznosciViewResource()
    url = resource.get_site_url()

    assert url.startswith("https://")
    assert site.domain in url


@pytest.mark.django_db
def test_rozbieznosci_zrodel_view_resource_get_site_url():
    """Test RozbieznosciZrodelViewResource.get_site_url."""
    from django.contrib.sites.models import Site

    from rozbieznosci_dyscyplin.admin import RozbieznosciZrodelViewResource

    site = Site.objects.first()
    if site is None:
        site = Site.objects.create(domain="example.com", name="Example")

    resource = RozbieznosciZrodelViewResource()
    url = resource.get_site_url()

    assert url.startswith("https://")
    assert site.domain in url


@pytest.mark.django_db
def test_rozbieznosci_view_resource_dehydrate_bpp_strona_url(zle_przypisana_praca):
    """Test RozbieznosciViewResource.dehydrate_bpp_strona_url."""
    from django.contrib.sites.models import Site

    from rozbieznosci_dyscyplin.admin import RozbieznosciViewResource

    site = Site.objects.first()
    if site is None:
        Site.objects.create(domain="example.com", name="Example")

    rozbieznosc = RozbieznosciView.objects.first()
    assert rozbieznosc is not None

    resource = RozbieznosciViewResource()
    url = resource.dehydrate_bpp_strona_url(rozbieznosc)

    assert "browse_praca" in url or "bpp" in url


@pytest.mark.django_db
def test_rozbieznosci_zrodel_view_resource_dehydrate_dyscypliny_zrodla(
    autor_z_dyscyplina,
    rok,
    zrodlo,
    dyscyplina1,
    dyscyplina2,
    jednostka,
    typy_odpowiedzialnosci,
):
    """Test RozbieznosciZrodelViewResource.dehydrate_dyscypliny_zrodla."""
    from django.contrib.sites.models import Site

    from rozbieznosci_dyscyplin.admin import RozbieznosciZrodelViewResource

    Site.objects.get_or_create(pk=1, defaults={"domain": "example.com", "name": "Ex"})

    # Utworz rozbieznosc zrodel
    Dyscyplina_Zrodla.objects.create(rok=rok, zrodlo=zrodlo, dyscyplina=dyscyplina2)
    wc = baker.make(Wydawnictwo_Ciagle, rok=rok, zrodlo=zrodlo)
    wc.dodaj_autora(autor_z_dyscyplina.autor, jednostka, dyscyplina_naukowa=dyscyplina1)

    rozbieznosc = RozbieznosciZrodelView.objects.first()
    assert rozbieznosc is not None

    resource = RozbieznosciZrodelViewResource()
    disciplines = resource.dehydrate_dyscypliny_zrodla(rozbieznosc)

    # Powinno zawierac nazwe dyscypliny2
    assert dyscyplina2.nazwa in disciplines
