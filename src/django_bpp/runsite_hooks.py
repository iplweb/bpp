"""BPP-specific hooks dla `run-site` CLI.

Callable wskazane w `runsite.toml`:

- :func:`clear_password_policy` — odpalany jako `[[hooks.post_superuser]]`.
  Po utworzeniu/nadpisaniu admina kasuje wymog zmiany hasla z
  `password_policies` i dodaje swiezy wpis PasswordHistory, zeby middleware
  nie wymuszalo zmiany przy pierwszym logowaniu. Dawniej zaszyte w
  `runsite_setup_admin._clear_password_change_required` /
  `_refresh_password_history`.

- :func:`zabezpiecz_lokalna_kopie` — `[[hooks.post_migrate]]`, zawsze:
  zamyka kolejke eksportu do PBN przyniesiona z kopia bazy
  (`pbn_bezpiecznik_lokalnej_kopii`).

- :func:`fetch_pbn_token` — odpalany jako `[[hooks.post_superuser]]` z
  dynamicznym CLI flagiem `--get-pbn-token-from`. Pobiera po SSH
  konfiguracje aplikacji PBN i token uzytkownika
  (`pbn_konfiguracja_z_serwera`). Gdy flag nie jest podany, no-op.

Hooki run-site sa wywolywane przez `manage.py shell -c`, wiec Django jest
juz zaladowany — mozemy bez ceregieli importowac modele i wolac
`call_command`. Sygnatura: `def hook(ctx: dict) -> None`. Ctx zawiera
m.in. ``ctx["opts"]`` (dynamic CLI args), ``ctx["superuser"]`` (gdy
post_superuser), ``ctx["postgres"]`` itd.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def clear_password_policy(ctx: dict) -> None:
    """Skasuj wymog zmiany hasla i dodaj swiezy PasswordHistory dla admina.

    Idempotent. No-op gdy `password_policies` nie ma w INSTALLED_APPS.
    """
    superuser = ctx.get("superuser") or {}
    username = superuser.get("username", "admin")

    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        # Hook biegnie po `run-site` `[superuser]` block, wiec uzytkownik
        # powinien istniec. Gdy nie istnieje — pewnie superuser jest wylaczony
        # i nic nie ma do roboty.
        logger.info("[runsite-hook] clear_password_policy: brak %s, pomijam", username)
        return

    _clear_password_change_required(user)
    _refresh_password_history(user)


def _clear_password_change_required(user) -> None:
    try:
        from password_policies.models import PasswordChangeRequired
    except ImportError:
        return  # password_policies nieobecne — nic do roboty

    deleted, _ = PasswordChangeRequired.objects.filter(user=user).delete()
    if deleted:
        logger.info(
            "[runsite-hook] Usunieto %d wpisow PasswordChangeRequired dla %s",
            deleted,
            user,
        )


def _refresh_password_history(user) -> None:
    """Dodaj swiezy wpis PasswordHistory zeby middleware nie wymuszal zmiany.

    `password_policies.middleware.PasswordChangeMiddleware` sprawdza wiek
    ostatniego ``PasswordHistory`` (lub ``date_joined`` jako fallback)
    wzgledem ``PASSWORD_DURATION_SECONDS``. Po restore dumpa wpisy admina
    sa stare → haslo przeterminowane. Swiezy wpis (auto_now_add) sprawia,
    ze ``get_newest(user)`` zwraca aktualny timestamp.
    """
    try:
        from password_policies.models import PasswordHistory
    except ImportError:
        return

    PasswordHistory.objects.create(user=user, password=user.password)
    logger.info("[runsite-hook] Dodano swiezy PasswordHistory dla %s", user)


def zabezpiecz_lokalna_kopie(ctx: dict) -> None:
    """Zamknij kolejke eksportu do PBN przyniesiona z kopia bazy.

    Biegnie przy KAZDYM starcie run-site (idempotentne; na swiezej bazie
    z baseline nie ma czego zamykac). Po `--from-dump` z bazy klienta
    w kolejce leza wpisy z produkcji — bez tego pierwszy zapisany token PBN
    albo watchdog wyslalby je z maszyny dewelopera do prawdziwego PBN.

    Odmowa bezpiecznika (instancja nie wyglada na lokalna) jest logowana,
    nie zatrzymuje stacku.
    """
    from django.core.management import CommandError, call_command

    wyjscie = io.StringIO()
    try:
        call_command(
            "pbn_bezpiecznik_lokalnej_kopii", potwierdzenie=True, stdout=wyjscie
        )
    except CommandError as exc:
        logger.warning("[runsite-hook] PBN bezpiecznik: %s", exc)
    _zaloguj_wyjscie("PBN bezpiecznik", wyjscie)


def fetch_pbn_token(ctx: dict) -> None:
    """Pobierz z serwera (SSH) konfiguracje aplikacji PBN i token uzytkownika.

    No-op gdy uzytkownik nie podal `--get-pbn-token-from LOGIN@HOST`.
    Przenosi adres API, nazwe i token aplikacji PBN oraz token uzytkownika
    LOGIN — jawne wartosci odczytuje ORM serwera, lokalny zapis szyfruje je
    lokalnym kluczem (kopia bazy z serwera ma te pola zaszyfrowane kluczem,
    ktorego lokalnie nie ma). Cala logika: `pbn_api/konfiguracja_z_serwera.py`.

    Bledy SSH sa logowane (nie raise), bo serwer dziala bez aktualnego tokenu
    — przyklad: deweloper nie jest na VPN-ie, ale chce uruchomic stack.
    """
    from django.core.management import CommandError, call_command

    opts = ctx.get("opts") or {}
    raw_source = opts.get("pbn_ssh_source")
    if not raw_source:
        return  # flag nie podany — nic do roboty

    wyjscie = io.StringIO()
    try:
        call_command(
            "pbn_konfiguracja_z_serwera",
            raw_source,
            stdout=wyjscie,
            remote_deploy_path=opts.get("pbn_remote_deploy_path") or "~/bpp-deploy",
            remote_compose_service=(
                opts.get("pbn_remote_compose_service") or "appserver"
            ),
        )
    except CommandError as exc:
        logger.warning("[runsite-hook] PBN: %s", exc)
    _zaloguj_wyjscie("PBN", wyjscie)


def _zaloguj_wyjscie(prefiks: str, wyjscie: io.StringIO) -> None:
    # Komendy nie wypisuja sekretow (tokeny ida tylko do bazy), wiec ich
    # raport mozna bezpiecznie przepisac do logu run-site.
    for linia in wyjscie.getvalue().splitlines():
        if linia.strip():
            logger.info("[runsite-hook] %s: %s", prefiks, linia)
