"""Symulowany „raw log" tekstowy z sesji importu PBN.

Nie mamy prawdziwego pliku logu — odtwarzamy go z wpisów ``ImportLog``. Log
zawiera te same dane co zakładka „Błędy i ostrzeżenia" (poziom error/critical/
warning): czas, klasę błędu, moduł (krok), pełną wiadomość, kontekst oraz —
gdy są — pełne tracebacki. Wpisy idą chronologicznie (najstarsze u góry), bo
plik logu czyta się od góry (UI pokazuje najnowsze pierwsze — tu odwrotnie).
"""

import json

from ..models import ImportLog

# Te same poziomy co zakładka „Błędy i ostrzeżenia".
LOG_LEVELS = ["error", "critical", "warning"]

_HEADER_RULE = "=" * 80
_ENTRY_RULE = "-" * 80
# Klucze ``details`` wypisywane jawnie — reszta trafia do bloku „details:".
_KNOWN_DETAIL_KEYS = {"exception", "context", "traceback"}


def _fmt_time(dt) -> str:
    """Sformatuj datetime do logu (lokalny czas), albo myślnik gdy brak."""
    if dt is None:
        return "-"
    from django.utils import timezone

    return timezone.localtime(dt).strftime("%Y-%m-%d %H:%M:%S")


def _render_entry(log: ImportLog) -> list[str]:
    details = log.details or {}
    exception = details.get("exception") or "-"

    lines = [
        f"[{_fmt_time(log.timestamp)}] [{log.level.upper()}] "
        f"exception={exception} step={log.step}",
        f"  message: {log.message}",
    ]

    context = details.get("context")
    if context:
        lines.append(f"  context: {context}")

    # Pozostałe (nieznane) klucze details — żeby nie zgubić „szczegółów".
    extra = {k: v for k, v in details.items() if k not in _KNOWN_DETAIL_KEYS}
    if extra:
        dumped = json.dumps(extra, ensure_ascii=False, indent=2, default=str)
        lines.append("  details:")
        lines.extend(f"    {line}" for line in dumped.splitlines())

    traceback = details.get("traceback")
    if traceback:
        lines.append("  traceback:")
        lines.extend(f"    {line}" for line in traceback.rstrip("\n").splitlines())

    lines.append(_ENTRY_RULE)
    return lines


def render_session_log_text(session) -> str:
    """Zbuduj symulowany raw log (tekst) z błędów i ostrzeżeń sesji.

    Args:
        session: instancja ``ImportSession``.

    Returns:
        Wielowierszowy tekst gotowy do wyświetlenia w ``<pre>`` lub pobrania
        jako ``.txt``. Zawsze kończy się znakiem nowej linii.
    """
    logs = list(
        ImportLog.objects.filter(session=session, level__in=LOG_LEVELS).order_by(
            "timestamp"
        )
    )

    lines = [
        _HEADER_RULE,
        f"PBN import — log sesji #{session.id}",
        f"Użytkownik: {session.user}",
        f"Status: {session.get_status_display()} ({session.status})",
        f"Rozpoczęto: {_fmt_time(session.started_at)}",
        f"Zakończono: {_fmt_time(session.completed_at)}",
        f"Wpisy (błędy + ostrzeżenia): {len(logs)}",
        _HEADER_RULE,
        "",
    ]

    if not logs:
        lines.append("(brak błędów i ostrzeżeń — import przebiegł pomyślnie)")
    else:
        for log in logs:
            lines.extend(_render_entry(log))

    return "\n".join(lines) + "\n"
