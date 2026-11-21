"""Konta demo (tylko z ``--konta-demo``): hasło = login.

- ``admin`` — superużytkownik,
- ``redaktor`` — redaktor (dostęp do panelu, „wprowadzanie danych",
  „zgłoszenia publikacji", „indeks autorów"; „generowanie raportów"
  dochodzi automatycznie),
- ``raporty`` — tylko „generowanie raportów",
- ``user`` — zwykłe konto bez uprawnień, powiązane z autorem demo.

Istniejącego konta NIE zmieniamy (ani hasła, ani uprawnień) — tylko
zgłaszamy, że jest. Hasła są jawne, więc to opcja wyłącznie dla
instancji demonstracyjnych; dlatego nie jest domyślna (np. bpp-wsl jej nie
podaje — tam pierwsze konto zakłada kreator).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from bpp.const import (
    GR_RAPORTY_WYSWIETLANIE,
    GR_WPROWADZANIE_DANYCH,
    GR_ZGLOSZENIA_PUBLIKACJI,
)
from bpp.demo_data.manifest import Manifest
from bpp.models import Autor


@dataclass(frozen=True)
class KontoDemo:
    login: str
    opis: str
    superuser: bool = False
    staff: bool = False
    grupy: tuple[str, ...] = ()
    z_autorem: bool = False


KONTA_DEMO = (
    KontoDemo("admin", "superużytkownik", superuser=True, staff=True),
    KontoDemo(
        "redaktor",
        "redaktor (wprowadzanie danych, zgłoszenia publikacji)",
        staff=True,
        grupy=(GR_WPROWADZANIE_DANYCH, GR_ZGLOSZENIA_PUBLIKACJI, "indeks autorów"),
    ),
    KontoDemo("raporty", "generowanie raportów", grupy=(GR_RAPORTY_WYSWIETLANIE,)),
    KontoDemo("user", "zwykły użytkownik powiązany z autorem", z_autorem=True),
)


def create_konta(*, autorzy: Iterable[Autor], manifest: Manifest, stdout) -> list:
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    User = get_user_model()
    autorzy = list(autorzy)
    utworzone = []
    for konto in KONTA_DEMO:
        if User.objects.filter(username=konto.login).exists():
            stdout.write(
                f"[--] Konto '{konto.login}' już istnieje — nie zmieniam go.\n"
            )
            continue
        user = User(
            username=konto.login,
            is_superuser=konto.superuser,
            is_staff=konto.staff,
            first_name="Demo",
            last_name=konto.login.capitalize(),
            email=f"{konto.login}@example.org",
        )
        user.set_password(konto.login)
        if konto.z_autorem:
            wolny = next(
                (a for a in autorzy if not User.objects.filter(autor=a).exists()),
                None,
            )
            user.autor = wolny
        user.save()
        grupy = list(Group.objects.filter(name__in=konto.grupy))
        brak = set(konto.grupy) - {g.name for g in grupy}
        if brak:
            stdout.write(
                f"[--] Brak grup {sorted(brak)} — uruchom `manage.py odtworz_grupy`.\n"
            )
        user.groups.add(*grupy)
        _bez_wymuszonej_zmiany_hasla(user)
        utworzone.append(user)
        manifest.append("bpp.BppUser", [user.pk])
        stdout.write(
            f"[OK] Konto '{konto.login}' / hasło '{konto.login}' — {konto.opis}"
            + (f" ({user.autor})" if user.autor_id else "")
            + ".\n"
        )
    manifest.save()
    return utworzone


def _bez_wymuszonej_zmiany_hasla(user) -> None:
    """Jak hook run-site: wpis w historii haseł (wiek hasła liczy się od
    niego) i brak flagi „wymagana zmiana hasła"."""
    from password_policies.models import PasswordChangeRequired, PasswordHistory

    PasswordChangeRequired.objects.filter(user=user).delete()
    if not PasswordHistory.objects.filter(user=user).exists():
        PasswordHistory.objects.create(user=user, password=user.password)
