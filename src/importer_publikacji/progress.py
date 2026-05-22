"""Tabela stages dla tasków importera + funkcja report_progress.

Wagi w tabelach FETCH_STAGES/CREATE_STAGES sumują się do 100 i są
używane do obliczenia overall percent z (stage, sub_current, sub_total).
Najwolniejszy etap dostaje największą wagę, żeby pasek postępu
faktycznie rósł podczas najdłuższej operacji.
"""

# (stage_code, label_template, weight)
# label_template może zawierać {current}/{total} dla per-item counter.
FETCH_STAGES = [
    ("provider_fetch", "Pobieram dane od dostawcy...", 10),
    ("create_session", "Tworzę sesję importu...", 5),
    ("match_type_lang", "Dopasowuję typ publikacji i język...", 5),
    ("match_authors", "Dopasowuję autorów ({current}/{total})...", 60),
    ("prefill_zgl", "Wyszukuję zgłoszenia dla dyscyplin...", 20),
]

CREATE_STAGES = [
    ("prepare", "Przygotowuję dane do zapisu...", 5),
    (
        "create_record",
        "Tworzę rekord publikacji (autorzy, źródło, streszczenia)...",
        75,
    ),
    ("link_pbn", "Powiązanie z PBN...", 20),
]


def report_progress(task, stage_code, sub_current=0, sub_total=1, *, stages):
    """Raportuj postęp do Celery z mapowania (stage, sub_current/sub_total)
    na overall percent (0-100).

    Wywołuje task.update_state(state="PROGRESS", meta={...}). Meta zawiera:
        - stage_code: identyfikator etapu (str)
        - label: tekst do wyświetlenia (z interpolowanym {current}/{total})
        - current, total: sub_current/sub_total (0/0 gdy etap bez counter)
        - counter_display: "M/N" lub "" gdy total <= 1
        - progress: overall percent (0-100, int)
    """
    completed_weight = 0
    found = None
    for code, label_template, weight in stages:
        if code == stage_code:
            found = (code, label_template, weight)
            break
        completed_weight += weight

    if found is None:
        raise ValueError(f"Unknown stage: {stage_code}")

    _, label_template, weight = found

    if sub_total > 1:
        stage_fraction = sub_current / sub_total
        counter_display = f"{sub_current}/{sub_total}"
        label = label_template.format(current=sub_current, total=sub_total)
    else:
        stage_fraction = 0
        counter_display = ""
        label = label_template.replace(" ({current}/{total})", "")

    progress = int(completed_weight + weight * stage_fraction)

    task.update_state(
        state="PROGRESS",
        meta={
            "stage_code": stage_code,
            "label": label,
            "current": sub_current,
            "total": sub_total if sub_total > 1 else 0,
            "counter_display": counter_display,
            "progress": progress,
        },
    )


class ProviderReturnedNothing(Exception):
    """Provider zwrócił None - identyfikator nie został rozpoznany
    lub nie ma takiej publikacji w bazie dostawcy.
    """


def user_safe_message(exc, *, task_kind):
    """Zamapuj wyjątek na user-friendly komunikat (po polsku).

    Każda wiadomość ma prefix mówiący CZYJ to problem — żeby user widział
    czy to my, dostawca czy jego dane. Prefiksy:
      - "Problem dostawcy" — błąd po stronie serwera zewnętrznego
        (HTTP 5xx, timeout, brak publikacji w bazie dostawcy).
      - "Problem danych wejściowych" — błąd walidacji (user podał coś
        niepoprawnego, np. niespełniający wymogi rekord).
      - "Problem aplikacji" — bug po naszej stronie. Admin powiadomiony
        przez Rollbar (globalny @task_failure.connect).

    task_kind: "fetch" lub "create" — wpływa na fallback message.
    """
    import requests
    from django.core.exceptions import ValidationError

    if isinstance(exc, ProviderReturnedNothing):
        return (
            "Problem dostawcy: nie udało się pobrać danych. "
            "Sprawdź poprawność identyfikatora i spróbuj ponownie."
        )

    if isinstance(exc, requests.exceptions.Timeout):
        return (
            "Problem dostawcy: serwer nie odpowiada w wyznaczonym czasie. "
            "Spróbuj ponownie za chwilę."
        )

    if isinstance(exc, requests.exceptions.HTTPError):
        status = _http_status_from_exc(exc)
        if status:
            return (
                f"Problem dostawcy: serwer zwrócił błąd HTTP {status}. "
                f"To problem po stronie dostawcy, nie aplikacji. "
                f"Spróbuj ponownie później."
            )
        return "Problem dostawcy: serwer zwrócił błąd. Spróbuj ponownie za chwilę."

    if isinstance(exc, requests.exceptions.ConnectionError):
        return (
            "Problem dostawcy: nie można połączyć się z serwerem. "
            "Spróbuj ponownie za chwilę."
        )

    if isinstance(exc, ValidationError):
        messages = getattr(exc, "messages", None) or [str(exc)]
        return "Problem danych wejściowych: " + " ".join(messages)

    kind_text = "pobierania danych" if task_kind == "fetch" else "tworzenia rekordu"
    return (
        f"Problem aplikacji: wystąpił błąd podczas {kind_text}. "
        f"Administrator został powiadomiony."
    )


def _http_status_from_exc(exc):
    """Wyciągnij status code z requests.HTTPError jeśli jest dostępny.

    raise_for_status() zachowuje response na exception; ręczny raise z
    inną sygnaturą może nie mieć. Bezpieczna ekstrakcja zwraca None gdy
    nie ma response albo nie ma status_code.
    """
    response = getattr(exc, "response", None)
    if response is None:
        return None
    return getattr(response, "status_code", None)
