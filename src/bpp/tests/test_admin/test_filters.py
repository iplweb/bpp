import pytest
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from bpp.admin.filters import (
    JednostkaFilter,
    OstatnioZmienionePrzezFilter,
    UtworzonePrzezFilter,
)
from bpp.models import Autor, BppUser, Wydawnictwo_Zwarte


@pytest.mark.django_db
def test_OstatnioZmienionePrzezFilter(wydawnictwo_zwarte, admin_user):

    LogEntry.objects.create(
        action_flag=CHANGE,
        object_id=wydawnictwo_zwarte.pk,
        content_type_id=ContentType.objects.get_for_model(wydawnictwo_zwarte).pk,
        user=admin_user,
    )

    f = OstatnioZmienionePrzezFilter(None, {}, Wydawnictwo_Zwarte, None)

    f.value = lambda *args, **kw: admin_user.pk

    assert wydawnictwo_zwarte in f.queryset(None, Wydawnictwo_Zwarte.objects.all())

    assert admin_user.pk in [x[0] for x in f.lookups(None, None)]


@pytest.mark.django_db
def test_UtworzonePrzeZFilter(wydawnictwo_zwarte, admin_user, normal_django_user):
    drugie_wydawnictwo_zwarte = baker.make(Wydawnictwo_Zwarte)
    content_type_id = ContentType.objects.get_for_model(wydawnictwo_zwarte).pk

    LogEntry.objects.create(
        action_flag=ADDITION,
        object_id=wydawnictwo_zwarte.pk,
        user=admin_user,
        content_type_id=content_type_id,
    )

    LogEntry.objects.create(
        action_flag=ADDITION,
        object_id=drugie_wydawnictwo_zwarte.pk,
        user=normal_django_user,
        content_type_id=content_type_id,
    )

    f = UtworzonePrzezFilter(None, {}, Wydawnictwo_Zwarte, None)

    f.value = lambda *args, **kw: admin_user.pk

    assert wydawnictwo_zwarte in f.queryset(None, Wydawnictwo_Zwarte.objects.all())
    assert drugie_wydawnictwo_zwarte not in f.queryset(
        None, Wydawnictwo_Zwarte.objects.all()
    )

    user_ids = [x[0] for x in f.lookups(None, None)]
    assert admin_user.pk in user_ids


@pytest.mark.django_db
def test_JednostkaFilter_lookups_jednym_zapytaniem(uczelnia, django_assert_num_queries):
    """Opcje filtra „Jednostka" powstają JEDNYM zapytaniem.

    Regresja: ``lookups()`` woła ``str(x)`` na każdej jednostce, a
    ``Jednostka.__str__`` czyta DWA FK — ``self.uczelnia`` (bramka
    ``uzywaj_wydzialow``) i ``self.wydzial`` (skrót w nawiasie).
    ``select_related`` pokrywał tylko ``wydzial``, więc każda opcja listy
    kosztowała osobny SELECT po uczelnię: na bazie produkcyjnej 504 jednostki
    = 504 zapytania na KAŻDE wejście na changelistę autorów.
    """
    from bpp.tests.util import any_jednostka

    for numer in range(4):
        any_jednostka(nazwa=f"Jednostka Filtrowa {numer}", uczelnia=uczelnia)

    filtr = JednostkaFilter(None, {}, Autor, None)

    with django_assert_num_queries(1):
        etykiety = [etykieta for _pk, etykieta in filtr.lookups(None, None)]

    assert len([e for e in etykiety if "Jednostka Filtrowa" in e]) == 4


@pytest.mark.django_db
def test_UtworzonePrzezFilter_lookups_jednym_zapytaniem(
    wydawnictwo_zwarte, django_assert_num_queries
):
    """Opcje filtra „Utworzone przez" powstają JEDNYM zapytaniem.

    Regresja: ``lookups()`` zawężał queryset przez ``.only("pk", "username")``,
    ale ``BppUser.__str__`` czyta też ``last_name`` i ``first_name``. Każde
    pole odroczone to osobny ``refresh_from_db()`` per użytkownik, czyli DWA
    dodatkowe SELECT-y na wiersz — „optymalizacja", która kosztowała zamiast
    oszczędzać (na produkcji 156 zapytań na wejście na changelistę wydawnictw
    ciągłych). Test pilnuje, żeby ``only()`` nadążało za ``__str__``.
    """
    content_type_id = ContentType.objects.get_for_model(wydawnictwo_zwarte).pk

    for numer in range(3):
        LogEntry.objects.create(
            action_flag=ADDITION,
            object_id=wydawnictwo_zwarte.pk,
            user=baker.make(
                BppUser, first_name=f"Imie{numer}", last_name=f"Nazwisko{numer}"
            ),
            content_type_id=content_type_id,
        )

    filtr = UtworzonePrzezFilter(None, {}, Wydawnictwo_Zwarte, None)

    with django_assert_num_queries(1):
        etykiety = [etykieta for _pk, etykieta in filtr.lookups(None, None)]

    assert len(etykiety) == 3
    # Nazwisko i imię MUSZĄ się pojawić — inaczej ``only()`` znów je pominęło,
    # a ``__str__`` po cichu degradowałby do samego ``username``.
    assert all("Nazwisko" in etykieta for etykieta in etykiety), etykiety
    assert all("Imie" in etykieta for etykieta in etykiety), etykiety
