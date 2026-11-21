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
from django.contrib.admin.models import ADDITION, LogEntry

# Rejestracja modeli w reversion (``Autor``) — jawnie, żeby nie zależeć od
# tego, czy w procesie (np. worker Celery) załadował się już moduł admina.
import bpp.wersjonowanie  # noqa: F401


def komunikat_utworzenia(session):
    """Treść wpisu historii dla rekordu utworzonego w sesji ``session``."""
    szczegoly = f"sesja #{session.pk}, źródło: {session.provider_name}"
    if session.zgloszenie_id:
        szczegoly += f", zgłoszenie #{session.zgloszenie_id}"
    return f"Utworzono przez importer publikacji ({szczegoly})"


def zapisz_utworzenie(user, obj, komunikat):
    """Zapisz ``LogEntry`` (ADDITION) dla ``obj`` w imieniu ``user``.

    Wołać wewnątrz transakcji tworzącej rekord — wycofanie importu wycofuje
    też wpis historii. Dla modeli wersjonowanych (reversion) zapisuje
    również wersję z komentarzem ``komunikat``.
    """
    LogEntry.objects.log_actions(
        user.pk,
        [obj],
        ADDITION,
        change_message=komunikat,
        single_object=True,
    )
    if reversion.is_registered(type(obj)):
        with reversion.create_revision():
            reversion.add_to_revision(obj)
            reversion.set_user(user)
            reversion.set_comment(komunikat)
