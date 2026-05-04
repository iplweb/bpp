"""Mapowanie powodów podobieństwa autorów na ikony Foundation i ton koloru.

Logika żyje w module Pythona zamiast w Django template-tag library, bo
auto-discovery template-tagów wykonuje się raz, przy starcie procesu —
świeżo dodany pakiet `templatetags/` nie zostaje zauważony bez restartu.
Zwykły moduł utils ładuje się przy każdym auto-reloadzie pliku.
"""

# (fragment, icon_class, tone)
# tone: match (zielony, mocna przesłanka), info (niebieski, neutralna),
#       weak (szary, słaba), warn (pomarańczowy, ostrożnie).
# Kolejność ma znaczenie — pierwszy pasujący wzorzec wygrywa, więc
# specyficzne frazy idą przed ogólnymi.
_PATTERNS: list[tuple[str, str, str]] = [
    # ORCID — najmocniejsze przesłanki tożsamości
    ("identyczny ORCID", "fi-key", "match"),
    ("różny ORCID", "fi-x-circle", "warn"),
    ("brak ORCID", "fi-key", "weak"),
    # Nazwiska
    ("identyczne nazwisko", "fi-checkbox", "match"),
    ("identyczne człony nazwiska", "fi-checkbox", "match"),
    ("podobne nazwisko", "fi-magnifying-glass", "info"),
    # Imiona
    ("zamianę imienia z nazwiskiem", "fi-loop", "warn"),
    ("wspólne imię", "fi-torsos-female-male", "match"),
    ("podobne imię", "fi-torso", "info"),
    ("pasujące inicjały", "fi-text-color", "info"),
    ("brak imion", "fi-prohibited", "weak"),
    # Tytuł naukowy
    ("identyczny tytuł naukowy", "fi-trophy", "match"),
    ("różny tytuł naukowy", "fi-trophy", "warn"),
    ("brak tytułu naukowego", "fi-trophy", "weak"),
    # Liczba publikacji
    ("mało publikacji", "fi-page", "info"),
    ("średnio publikacji", "fi-page-multiple", "info"),
    ("wiele publikacji", "fi-page-copy", "weak"),
    # Lata publikacji
    ("wspólne lata publikacji", "fi-calendar", "match"),
    ("bliskie lata publikacji", "fi-calendar", "info"),
    ("średnia odległość lat", "fi-calendar", "weak"),
    ("duża odległość lat", "fi-calendar", "warn"),
    # Fallbacki - szersze frazy
    ("ORCID", "fi-key", "info"),
    ("nazwisk", "fi-magnifying-glass", "info"),
    ("imię", "fi-torsos-female-male", "info"),
    ("imion", "fi-torsos-female-male", "info"),
    ("publikacj", "fi-page", "info"),
    ("lata", "fi-calendar", "info"),
    ("tytuł", "fi-trophy", "info"),
]


def enrich_reason(reason: str) -> dict:
    """Zwraca dict {text, icon, tone} dla pojedynczego powodu podobieństwa.

    Dla pustego/None reason zwraca neutralny chip z ikoną fi-info.
    """
    text = (reason or "").strip()
    if not text:
        return {"text": "", "icon": "fi-info", "tone": "info"}

    lowered = text.lower()
    for needle, icon, tone in _PATTERNS:
        if needle.lower() in lowered:
            return {"text": text, "icon": icon, "tone": tone}
    return {"text": text, "icon": "fi-info", "tone": "info"}


def enrich_reasons(reasons) -> list[dict]:
    """Wzbogaca listę powodów. Akceptuje None, listę stringów lub iterowalne."""
    if not reasons:
        return []
    return [enrich_reason(r) for r in reasons]
