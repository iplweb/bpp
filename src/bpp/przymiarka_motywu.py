"""Przymiarka motywu: motyw z konfiguratora widoczny na całej stronie, ale
tylko w sesji osoby, która go przymierza (obsługa). Odwiedzający widzą
stronę bez zmian.

CSS leży w bazie (``MotywPrzymiarka``, pod skrótem treści), w sesji tylko
skrót. Wpisy starsze niż doba są usuwane przy kolejnej przymiarce.
"""

import hashlib
from datetime import timedelta

from django.utils.timezone import now

KLUCZ_SESJI = "bpp_przymiarka_motywu"
CZAS = timedelta(days=1)


def rozpocznij(request, css):
    from bpp.models import MotywPrzymiarka

    skrot = hashlib.sha256(css.encode("utf-8")).hexdigest()
    MotywPrzymiarka.objects.filter(utworzono__lt=now() - CZAS).delete()
    # Ta sama przymiarka ponownie — odśwież datę, żeby nie wygasła w trakcie.
    MotywPrzymiarka.objects.update_or_create(
        skrot=skrot, defaults={"css": css, "utworzono": now()}
    )
    request.session[KLUCZ_SESJI] = skrot
    return skrot


def zakoncz(request):
    request.session.pop(KLUCZ_SESJI, None)


def css(skrot):
    from bpp.models import MotywPrzymiarka

    return (
        MotywPrzymiarka.objects.filter(skrot=skrot, utworzono__gte=now() - CZAS)
        .values_list("css", flat=True)
        .first()
    )


def aktywna(request):
    """Skrót przymierzanego motywu albo None (tylko osoby z dostępem do
    konfiguratora wyglądu; po wygaśnięciu przymiarka kończy się sama)."""
    from bpp.konfigurator_dostep import moze_konfigurowac_wyglad
    from bpp.models import MotywPrzymiarka

    user = getattr(request, "user", None)
    sesja = getattr(request, "session", None)
    if not moze_konfigurowac_wyglad(user) or sesja is None:
        return None
    skrot = sesja.get(KLUCZ_SESJI)
    if not skrot:
        return None
    if not MotywPrzymiarka.objects.filter(
        skrot=skrot, utworzono__gte=now() - CZAS
    ).exists():
        zakoncz(request)
        return None
    return skrot
