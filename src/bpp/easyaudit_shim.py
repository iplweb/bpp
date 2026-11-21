"""Poprawka do ``django-easy-audit``: nie zakładaj, że ``objects`` widzi
wszystkie wiersze.

PROBLEM
-------
``easyaudit.signals.model_signals.pre_save`` pobiera poprzednią wersję
zapisywanego wiersza przez DOMYŚLNEGO menedżera::

    old_model = sender.objects.get(pk=instance.pk)

Dla modeli soft-delete ``objects`` filtruje ``deleted_at IS NULL``, a przy
``restore()`` wiersz w bazie jest w tym momencie WCIĄŻ skasowany — więc
lookup rzuca ``DoesNotExist``. Ponieważ BPP ma
``DJANGO_EASY_AUDIT_PROPAGATE_EXCEPTIONS = True``, wyjątek wychodzi na
zewnątrz i wywraca cały ``restore()``.

Poprawne jest ``_base_manager``: Django dokumentuje go jako menedżera, który
MUSI zwracać wszystkie obiekty, i sam tworzy dla niego zwykły, nieodfiltrowany
``Manager``, gdy model nie ustawia ``Meta.base_manager_name``. Sprawdzone na
naszych modelach — ``_base_manager`` widzi rekordy z kosza, ``objects`` nie.

ZAKRES BŁĘDU — SZERSZY NIŻ FAZA 02
----------------------------------
To NIE jest problem wprowadzony przez soft-delete publikacji.
``Zgloszenie_Publikacji`` jest ``SoftDeleteModel`` od dawna i figuruje
w ``DJANGO_EASY_AUDIT_REGISTERED_CLASSES``, więc na ``dev`` **nie da się dziś
przywrócić skasowanego zgłoszenia**. Faza 02 rozszerza zasięg z jednego
modelu na sześć. Ten shim naprawia oba przypadki naraz.

Through-modele ``*_Autor`` (faza 01) nie były dotknięte, bo nie ma ich
w ``REGISTERED_CLASSES``.

DLACZEGO SHIM, A NIE FORK
-------------------------
Wadliwe wywołanie jest w całym pakiecie DOKŁADNIE JEDNO, a sygnały są
podpinane z ``dispatch_uid`` — można więc czysto podmienić sam handler,
bez forka i bez monkeypatchowania wnętrzności modułu.

Upstream (``soynatan/django-easy-audit``) zna ten błąd jako issue #175,
otwarte od 2021-02. Cztery próby naprawy (PR #168, #176, #318, #342) w sześć
lat, żadna nie scalona — mimo że projekt jest aktywnie wydawany. Z wątku
przy #168 wynika, dlaczego: maintainer odsyła do obejścia przez
``DJANGO_EASY_AUDIT_CRUD_DIFFERENCE_CALLBACKS``, które NIE DZIAŁA, bo
wyjątek leci zanim callbacki zostaną w ogóle sprawdzone.

Gdy poprawka wejdzie upstream — skasować ten moduł i wywołanie
``zainstaluj()`` w ``BppConfig.ready()``. Pilnuje tego
``test_easyaudit_shim.py``, który pada, gdy upstream się zmieni.
"""

import json
from functools import partial

from django.conf import settings
from django.core import serializers
from django.db import transaction
from django.db.models import signals

#: ``dispatch_uid``, którym easyaudit podpina swój handler
#: (``model_signals.py``, na dole modułu). Używamy TEGO SAMEGO klucza, więc
#: podmiana jest czysta w obie strony — patrz ``zainstaluj()``.
DISPATCH_UID = "easy_audit_signals_pre_save"

#: Wersja pakietu, na której kopiowano ciało handlera. Nie jest sprawdzana
#: w runtime — pilnuje jej test, żeby aktualizacja pakietu była GŁOŚNA.
WERSJA_UPSTREAM = "1.3.9"


def pre_save(sender, instance, raw, using, update_fields, **kwargs):
    """Kopia ``easyaudit.signals.model_signals.pre_save`` (1.3.9) z JEDNĄ
    zmianą: ``sender.objects`` -> ``sender._base_manager``.

    Cała reszta — łącznie z obsługą wyjątków, kolejnością callbacków
    i ``transaction.on_commit`` — jest importowana z upstreamu, a nie
    przepisana. Powielamy wyłącznie strukturę funkcji, bo jedyny sposób
    na podmianę jednej linii w cudzym ciele to podmiana całej funkcji.
    """
    # Import lokalny: moduł easyaudit ma być ładowany dopiero wtedy, gdy
    # aplikacja jest faktycznie zainstalowana (w BPP wchodzi tylko
    # w local.py/production.py).
    from easyaudit.signals.crud_flows import pre_save_crud_flow
    from easyaudit.signals.model_signals import (
        call_callbacks,
        handle_signal_exception,
        should_audit,
    )
    from easyaudit.utils import model_delta

    if raw:
        # Return if loading Fixtures
        return None

    try:
        if not should_audit(instance):
            return False

        with transaction.atomic(using=using):
            try:
                object_json_repr = serializers.serialize("json", [instance])
            except Exception:
                # We need a better way for this to work. ManyToMany will fail on
                # pre_save on create
                return None

            # Determine if the instance is a create
            created = instance.pk is None or instance._state.adding

            # created or updated?
            delta = {}
            if not created:
                # ↓↓↓ JEDYNA ZMIANA WOBEC UPSTREAMU ↓↓↓
                # Upstream: sender.objects.get(pk=instance.pk)
                old_model = sender._base_manager.get(pk=instance.pk)
                delta = model_delta(old_model, instance)

                if not delta and getattr(
                    settings,
                    "DJANGO_EASY_AUDIT_CRUD_EVENT_NO_CHANGED_FIELDS_SKIP",
                    False,
                ):
                    return False

            # callbacks
            create_crud_event = call_callbacks(
                instance, object_json_repr, created, raw, using, update_fields, **kwargs
            )

            # Create crud event only if all callbacks returned True
            if create_crud_event and not created:
                crud_flow = partial(
                    pre_save_crud_flow,
                    instance=instance,
                    object_json_repr=object_json_repr,
                    changed_fields=json.dumps(delta),
                )

                if getattr(settings, "TEST", False):
                    crud_flow()
                else:
                    transaction.on_commit(crud_flow, using=using)
    except Exception:
        handle_signal_exception("pre_save")


def zainstaluj():
    """Podmienia handler ``pre_save`` easyauditu na nasz.

    Działa NIEZALEŻNIE od kolejności ``ready()`` aplikacji, bo używamy tego
    samego ``dispatch_uid`` co upstream:

    - gdy nasz ``ready()`` biegnie PIERWSZY (tak jest dziś: ``bpp`` stoi
      w ``INSTALLED_APPS`` przed ``easyaudit``, który jest doklejany na
      końcu w ``local.py``/``production.py``) — ``disconnect`` jest no-opem,
      a nasz ``connect`` zajmuje klucz. Późniejszy ``connect`` easyauditu
      jest wtedy pomijany, bo ``Signal.connect`` ignoruje duplikat
      ``dispatch_uid``;
    - gdy kolejność się kiedyś odwróci — ``disconnect`` zdejmuje ich
      handler, a ``connect`` wstawia nasz.

    Idempotentne: powtórne wywołanie nie dokłada drugiego odbiorcy.
    """
    signals.pre_save.disconnect(dispatch_uid=DISPATCH_UID)
    signals.pre_save.connect(pre_save, dispatch_uid=DISPATCH_UID)
