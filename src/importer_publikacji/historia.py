"""Ślad w historii zmian (admin „Historia") dla rekordów tworzonych przez
importer publikacji (FD#441).

Importer tworzy rekordy przez ``objects.create()`` poza adminem, więc bez
tego na stronie „Historia" rekordu nie było żadnego wpisu — nie było widać,
kto i skąd go dodał. Zapisujemy ``LogEntry`` z akcją ADDITION (to samo, co
zostawia „Dodaj" w adminie), z autorem = użytkownikiem prowadzącym import.

Dla modeli zarejestrowanych w django-reversion (obecnie ``Autor``)
dodatkowo zapisujemy wersję początkową z tym samym komentarzem — strona
„Historia" takich modeli pokazuje wersje, a stan z chwili utworzenia daje
punkt, do którego da się wrócić.
"""

import reversion
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry

# Rejestracja modeli w reversion (``Autor``) — jawnie, żeby nie zależeć od
# tego, czy w procesie (np. worker Celery) załadował się już moduł admina.
import bpp.wersjonowanie  # noqa: F401
from bpp.wersjonowanie import opis_uzytkownika


def _szczegoly_sesji(session):
    szczegoly = f"sesja #{session.pk}, źródło: {session.provider_name}"
    if session.zgloszenie_id:
        szczegoly += f", zgłoszenie #{session.zgloszenie_id}"
    return szczegoly


def komunikat_utworzenia(session):
    """Treść wpisu historii dla rekordu utworzonego w sesji ``session``."""
    return f"Utworzono przez importer publikacji ({_szczegoly_sesji(session)})"


def komunikat_utworzenia_z_pbn(session, wynik):
    """Jak ``komunikat_utworzenia``, z informacją, skąd nowy autor ma
    odpowiednik w PBN (FD#510)."""
    return (
        f"{komunikat_utworzenia(session)}; powiązano z osobą PBN "
        f"{wynik.scientist_id} ({wynik.zrodlo})"
    )


def komunikat_zatrudnienia(session, jednostka):
    """Treść wpisu historii, gdy importer dopisał autorowi zatrudnienie."""
    return (
        f"Dodano zatrudnienie w jednostce „{jednostka}” przez importer "
        f"publikacji ({_szczegoly_sesji(session)})"
    )


def komunikat_orcid(session, orcid):
    """Treść wpisu historii, gdy importer ustawił autorowi ORCID."""
    return (
        f"Ustawiono ORCID {orcid} przez importer publikacji "
        f"({_szczegoly_sesji(session)})"
    )


def komunikat_dyscypliny(session, record, dyscyplina, rok, user):
    """Treść wpisu historii, gdy importer przypisał autorowi dyscyplinę na
    rok pracy, bo autor nie miał żadnej (FD#620)."""
    tytul = (getattr(record, "tytul_oryginalny", "") or "").strip()
    if len(tytul) > 120:
        tytul = tytul[:119] + "…"
    return (
        f"Przypisano dyscyplinę „{dyscyplina}” na rok {rok} przez użytkownika "
        f"{opis_uzytkownika(user)} podczas importu pracy „{tytul}” "
        f"(sesja importu #{session.pk}, rekord #{record.pk})"
    )


def zapisz_utworzenie(user, obj, komunikat):
    """Zapisz ``LogEntry`` (ADDITION) dla ``obj`` w imieniu ``user``.

    Wołać wewnątrz transakcji tworzącej rekord — wycofanie importu wycofuje
    też wpis historii. Dla modeli wersjonowanych (reversion) zapisuje
    również wersję z komentarzem ``komunikat``.
    """
    _zapisz_w_historii(user, obj, komunikat, ADDITION)


def zapisz_zmiane(user, obj, komunikat):
    """Zapisz ``LogEntry`` (CHANGE) i wersję po zmianie ``obj`` w imieniu
    ``user``. Stan sprzed zmiany zapisz wcześniej przez
    ``bpp.wersjonowanie.zapewnij_wersje_poczatkowa``."""
    _zapisz_w_historii(user, obj, komunikat, CHANGE)


def _zapisz_w_historii(user, obj, komunikat, akcja):
    if not reversion.is_registered(type(obj)):
        _zapisz_log_entry(user, obj, komunikat, akcja)
        return

    # Wersję zapisujemy ze świeżo pobranego obiektu: triggery bazy (np.
    # ``aktualna_jednostka`` autora) ustawiają kolumny, których instancja
    # w pamięci nie zna. ``LogEntry`` musi powstać WEWNĄTRZ bloku
    # ``create_revision`` — reversion bierze datę wersji przy wejściu
    # w blok, a wpis starszy od najstarszej wersji strona „Historia"
    # pokazuje drugi raz jako „Wcześniejszą historię".
    swiezy = type(obj)._default_manager.get(pk=obj.pk)
    with reversion.create_revision():
        reversion.add_to_revision(swiezy)
        reversion.set_user(user)
        reversion.set_comment(komunikat)
        _zapisz_log_entry(user, swiezy, komunikat, akcja)


def _zapisz_log_entry(user, obj, komunikat, akcja):
    LogEntry.objects.log_actions(
        user.pk,
        [obj],
        akcja,
        change_message=komunikat,
        single_object=True,
    )
