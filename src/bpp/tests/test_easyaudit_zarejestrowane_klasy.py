"""Każda klasa audytowana przez easyaudit musi dać się zalogować.

easyaudit przy zapisie obiektu od razu serializuje go do JSON-a, ale
``str(obiekt)`` (pole ``CRUDEvent.object_repr``) i zapis ``CRUDEvent`` robi
dopiero w ``transaction.on_commit``. W zwykłych testach ``django_db``
transakcja testowa nigdy nie jest commitowana, więc ta część audytu NIGDY
się nie wykonuje — zepsute ``__str__`` audytowanego modelu przechodzi przez
całą suitę, a na produkcji (``DJANGO_EASY_AUDIT_PROPAGATE_EXCEPTIONS =
True``) kończy się błędem 500 po zapisie.

Test przechodzi PRAWDZIWĄ ścieżkę easyaudit dla każdej klasy z
``settings.DJANGO_EASY_AUDIT_REGISTERED_CLASSES``: ustawia bieżącego
użytkownika (jak ``EasyAuditMiddleware`` — bez niego callback BPP
``dont_log_anonymous_crud_events`` odrzuca zdarzenie), tworzy i usuwa obiekt
z wykonaniem callbacków ``on_commit`` i sprawdza, że powstały zdarzenia
CREATE i DELETE z poprawnym ``object_repr``. Nowa klasa dopisana do listy
w settings automatycznie trafia pod test.
"""

import pytest
from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django_softdelete.models import SoftDeleteModel
from easyaudit.middleware.easyaudit import clear_request, set_current_user
from easyaudit.models import CRUDEvent
from model_bakery import baker


def _model(wpis):
    # easyaudit przy starcie podmienia w tej liście napisy "app.Model" na same
    # klasy modeli (modyfikuje settings w miejscu), więc obsługujemy oba.
    return apps.get_model(wpis) if isinstance(wpis, str) else wpis


KLASY = [_model(w) for w in settings.DJANGO_EASY_AUDIT_REGISTERED_CLASSES]


@pytest.fixture
def zalogowany_uzytkownik(admin_user):
    set_current_user(admin_user)
    yield admin_user
    clear_request()


def _zdarzenia(obiekt, typ):
    return CRUDEvent.objects.filter(
        content_type=ContentType.objects.get_for_model(obiekt),
        object_id=str(obiekt.pk),
        event_type=typ,
    )


def test_lista_klas_nie_jest_pusta():
    # Strażnik: gdyby lista zniknęła z settings, parametryzacja niżej dałaby
    # zero przypadków i test „przechodziłby" niczego nie sprawdzając.
    assert KLASY


@pytest.mark.django_db
@pytest.mark.parametrize("model", KLASY, ids=lambda m: m._meta.label)
def test_klasa_audytowana_tworzy_zdarzenia(
    model, zalogowany_uzytkownik, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        obiekt = baker.make(model)
    oczekiwany_repr = str(obiekt)

    utworzenie = _zdarzenia(obiekt, CRUDEvent.CREATE).get()
    assert utworzenie.object_repr == oczekiwany_repr
    assert utworzenie.user_id == zalogowany_uzytkownik.pk

    pk = obiekt.pk
    with django_capture_on_commit_callbacks(execute=True):
        obiekt.delete()
    obiekt.pk = pk  # delete() zeruje pk; potrzebne do wyszukania zdarzenia
    if isinstance(obiekt, SoftDeleteModel):
        # Miękkie usunięcie (django_softdelete): delete() tylko oznacza rekord
        # jako usunięty i ZAPISUJE go — easyaudit loguje to jako UPDATE,
        # a wiersz zostaje w bazie (domyślny manager go ukrywa).
        typ = CRUDEvent.UPDATE
    else:
        typ = CRUDEvent.DELETE
    usuniecie = _zdarzenia(obiekt, typ).get()
    assert usuniecie.object_repr
