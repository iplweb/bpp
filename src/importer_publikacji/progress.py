"""Tabela stages dla tasków importera + funkcja report_progress.

Wagi w tabelach FETCH_STAGES/CREATE_STAGES sumują się do 100 i są
używane do obliczenia overall percent z (stage, sub_current, sub_total).
Najwolniejszy etap dostaje największą wagę, żeby pasek postępu
faktycznie rósł podczas najdłuższej operacji.
"""

# (stage_code, label_template, weight)
# label_template może zawierać {current}/{total} dla per-item counter.
FETCH_STAGES = [
    ("provider_fetch", "Pobieram dane z dostawcy...", 10),
    ("create_session", "Tworzę sesję importu...", 5),
    ("match_type_lang", "Dopasowuję typ publikacji i język...", 5),
    ("match_authors", "Dopasowuję autorów ({current}/{total})...", 60),
    ("prefill_zgl", "Wyszukuję zgłoszenia dla dyscyplin...", 20),
]

CREATE_STAGES = [
    ("verify", "Weryfikuję dane publikacji...", 5),
    ("create_record", "Tworzę rekord publikacji...", 10),
    ("add_authors", "Zapisuję autorów ({current}/{total})...", 50),
    ("create_abstracts", "Tworzę streszczenia...", 5),
    ("calc_score", "Uzupełniam punktację ze źródła...", 10),
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

    task_kind: "fetch" lub "create" — wpływa na fallback message.
    """
    import requests
    from django.core.exceptions import ValidationError

    if isinstance(exc, ProviderReturnedNothing):
        return (
            "Nie udało się pobrać danych z dostawcy. "
            "Sprawdź poprawność identyfikatora i spróbuj ponownie."
        )

    if isinstance(exc, requests.exceptions.Timeout):
        return (
            "Dostawca danych nie odpowiada w wyznaczonym czasie. "
            "Spróbuj ponownie za chwilę."
        )

    if isinstance(
        exc,
        (requests.exceptions.HTTPError, requests.exceptions.ConnectionError),
    ):
        return "Dostawca danych nie odpowiada. Spróbuj ponownie za chwilę."

    if isinstance(exc, ValidationError):
        messages = getattr(exc, "messages", None) or [str(exc)]
        return " ".join(messages)

    kind_text = "pobierania danych" if task_kind == "fetch" else "tworzenia rekordu"
    return f"Wystąpił błąd podczas {kind_text}. Administrator został powiadomiony."
