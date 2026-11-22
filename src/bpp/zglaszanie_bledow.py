"""Zgłaszanie błędów do zewnętrznych usług monitoringu — Rollbar i/lub Sentry.

Jedno miejsce, przez które kod BPP wysyła wyjątki i komunikaty „do monitoringu".
Obsługiwane są dwa backendy, każdy aktywny TYLKO wtedy, gdy jest skonfigurowany:

* **Rollbar** — gdy ``rollbar.init()`` dostał token dostępu
  (``ROLLBAR_ACCESS_TOKEN``; inicjalizacja w :mod:`bpp.rollbar_config`),
* **Sentry / GlitchTip** — gdy ``sentry_sdk.init()`` dostał DSN
  (``SENTRY_DSN``; inicjalizacja w :mod:`bpp.sentry_config`).

Oba mogą działać równolegle (okres przejściowy Rollbar → GlitchTip). Wyłączenie
Rollbara = usunięcie ``ROLLBAR_ACCESS_TOKEN`` z konfiguracji; kod wołający się
nie zmienia. Bez żadnej konfiguracji funkcje nic nie wysyłają.

Sygnatury są celowo zbliżone do ``rollbar.report_exc_info`` /
``rollbar.report_message`` (``extra_data`` → ``extra``), żeby przepięcie
istniejących wywołań było mechaniczne.

Moduł jest liściem (importuje tylko ``rollbar`` i ``sentry_sdk``), więc można go
bezpiecznie importować z dowolnego miejsca, także na etapie startu aplikacji.

Zgłaszanie NIGDY nie przerywa kodu wołającego: błąd wysyłki do jednego backendu
jest logowany (``logger.exception``), a drugi backend i tak dostaje zgłoszenie.
"""

import logging
import sys

import rollbar
import sentry_sdk

logger = logging.getLogger(__name__)

#: Poziomy Rollbara → poziomy Sentry (Sentry nie zna „critical", ma „fatal").
POZIOMY_SENTRY = {
    "critical": "fatal",
    "error": "error",
    "warning": "warning",
    "info": "info",
    "debug": "debug",
}


def rollbar_skonfigurowany():
    """Czy Rollbar ma token dostępu (czyli czy zgłoszenie w ogóle wyjdzie).

    Bez tokenu pyrollbar i tak nic nie wysyła, tylko loguje ostrzeżenie
    „No access_token provided" — pomijamy go, żeby nie śmiecić logów.
    """
    return bool(rollbar.SETTINGS.get("access_token"))


def sentry_skonfigurowany():
    """Czy ``sentry_sdk.init()`` został wywołany z niepustym DSN."""
    return sentry_sdk.get_client().is_active()


def _poziom_sentry(level):
    if level is None:
        return None
    return POZIOMY_SENTRY.get(str(level).lower(), str(level).lower())


def _extra_dla_rollbara(extra, tags):
    # Rollbar nie ma tagów — trafiają do sekcji `custom` obok `extra`.
    # Bez tagów przekazujemy `extra` bez zmian (także None), jak dotąd.
    if not tags:
        return extra
    dane = dict(extra or {})
    dane["tags"] = dict(tags)
    return dane


def _ustaw_scope(scope, *, level, extra, tags):
    poziom = _poziom_sentry(level)
    if poziom is not None:
        scope.set_level(poziom)
    for klucz, wartosc in (extra or {}).items():
        scope.set_extra(klucz, wartosc)
    for klucz, wartosc in (tags or {}).items():
        scope.set_tag(klucz, wartosc)


def capture_exception(
    exc_info=None,
    *,
    level=None,
    extra=None,
    tags=None,
    request=None,
    pomin_sentry=False,
):
    """Zgłoś wyjątek do każdego skonfigurowanego backendu.

    :param exc_info: krotka z ``sys.exc_info()``; domyślnie obsługiwany właśnie
        wyjątek (funkcję woła się wtedy z bloku ``except``).
    :param level: poziom w nomenklaturze Rollbara (``"critical"``, ``"error"``,
        ``"warning"``, ``"info"``, ``"debug"``); ``None`` = domyślny backendu.
    :param extra: słownik dodatkowych danych (Rollbar: ``custom``,
        Sentry: ``extra``).
    :param tags: słownik tagów (Sentry: tagi; Rollbar: ``custom["tags"]``).
    :param request: obiekt requestu Django — przekazywany do Rollbara. Sentry
        dostaje dane requestu sam, z integracji Django.
    :param pomin_sentry: nie wysyłaj do Sentry — dla ścieżek, które Sentry
        raportuje już własną integracją (np. błędy zadań Celery), żeby nie
        dublować zdarzeń.
    """
    if exc_info is None:
        exc_info = sys.exc_info()

    if rollbar_skonfigurowany():
        try:
            rollbar.report_exc_info(
                exc_info,
                request=request,
                extra_data=_extra_dla_rollbara(extra, tags),
                level=level,
            )
        except Exception:
            logger.exception("Nie udało się zgłosić wyjątku do Rollbara")

    if not pomin_sentry and sentry_skonfigurowany():
        try:
            with sentry_sdk.new_scope() as scope:
                _ustaw_scope(scope, level=level, extra=extra, tags=tags)
                sentry_sdk.capture_exception(exc_info)
        except Exception:
            logger.exception("Nie udało się zgłosić wyjątku do Sentry")


def capture_message(message, level="info", *, extra=None, tags=None, request=None):
    """Zgłoś komunikat (bez wyjątku) do każdego skonfigurowanego backendu.

    Parametry jak w :func:`capture_exception`. UWAGA: domyślny poziom to
    ``"info"`` (jak w Sentry), a NIE ``"error"`` jak w
    ``rollbar.report_message`` — przy przepinaniu starych wywołań bez
    jawnego poziomu trzeba podać ``level="error"``.
    """
    if rollbar_skonfigurowany():
        try:
            rollbar.report_message(
                message,
                level=level,
                request=request,
                extra_data=_extra_dla_rollbara(extra, tags),
            )
        except Exception:
            logger.exception("Nie udało się zgłosić komunikatu do Rollbara")

    if sentry_skonfigurowany():
        try:
            with sentry_sdk.new_scope() as scope:
                _ustaw_scope(scope, level=level, extra=extra, tags=tags)
                sentry_sdk.capture_message(message)
        except Exception:
            logger.exception("Nie udało się zgłosić komunikatu do Sentry")
