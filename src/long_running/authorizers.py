"""Autoryzator subskrypcji kanałów WWW dla operacji ``long_running``.

``channels_broadcast`` wymaga, by każdy kanał żądany przez przeglądarkę
w ``?extraChannels=`` przeszedł przez konfigurowalny autoryzator
(``CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER``). Domyślny autoryzator
biblioteki odrzuca WSZYSTKO — bez własnego autoryzatora żaden pasek
postępu operacji ``long_running`` nie dostaje aktualizacji na żywo.

Widoki ``long_running`` (``LongRunningSingleObjectChannelSubscriberMixin``,
``LongRunningResultsView``) subskrybują kanał-stronę operacji przez
``extraChannels=[operation.pk]``, a ``ASGINotificationMixin.send_progress``
publikuje do grupy ``str(pk)``. Ten autoryzator wpina się w to: przepuszcza
subskrypcję kanału-strony wyłącznie WŁAŚCICIELOWI operacji o danym pk.

Podpiąć w settings::

    CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER = (
        "long_running.authorizers.authorize_operation_channel"
    )
"""

import uuid

from long_running.models import Operation


def _iter_operation_models():
    """Iteruj po konkretnych (nieabstrakcyjnych) podklasach ``Operation``.

    ``Operation`` jest abstrakcyjny — każda aplikacja importująca (POLON,
    absencje, itd.) definiuje własną konkretną tabelę. Kanał-strona niesie
    goły UUID (``str(pk)``), więc nie wiemy z góry, do której tabeli należy;
    przeglądamy wszystkie i pytamy o pk.
    """
    from django.apps import apps

    for model in apps.get_models():
        if issubclass(model, Operation):
            yield model


def authorize_operation_channel(user, channel_name) -> bool:
    """Zwróć ``True``, gdy ``user`` jest właścicielem operacji o pk
    == ``channel_name``.

    Kanał-strona operacji to goły UUID. Autoryzujemy subskrypcję tylko gdy:

    * ``user`` jest zalogowany, oraz
    * ``channel_name`` jest poprawnym UUID-em, oraz
    * istnieje konkretna operacja ``long_running`` o tym pk należąca do
      ``user`` (właściciel).

    Wszystko inne (anonim, cudza operacja, nieistniejąca, nazwa kanału
    niebędąca UUID-em — np. kanał audience) → ``False``, bez wyjątku.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False

    try:
        uuid.UUID(str(channel_name))
    except (ValueError, TypeError, AttributeError):
        # Nazwa kanału nie jest UUID-em → to nie kanał-strona operacji.
        return False

    return any(
        model.objects.filter(pk=channel_name, owner=user).exists()
        for model in _iter_operation_models()
    )
