"""BPP-specific hooks dla `run-site` CLI.

Dwa callable wskazane w `runsite.toml`:

- :func:`clear_password_policy` — odpalany jako `[[hooks.post_superuser]]`.
  Po utworzeniu/nadpisaniu admina kasuje wymog zmiany hasla z
  `password_policies` i dodaje swiezy wpis PasswordHistory, zeby middleware
  nie wymuszalo zmiany przy pierwszym logowaniu. Dawniej zaszyte w
  `runsite_setup_admin._clear_password_change_required` /
  `_refresh_password_history`.

- :func:`fetch_pbn_token` — odpalany jako `[[hooks.post_migrate]]` z
  dynamicznym CLI flagiem `--get-pbn-token-from`. Pipe `dump_pbn_token`
  (zdalnie przez SSH + docker compose exec) → `load_pbn_token` (lokalnie).
  Gdy flag nie jest podany, no-op. Dawniej w
  `_run_site_helpers/pbn_token.py`.

Hooki run-site sa wywolywane przez `manage.py shell -c`, wiec Django jest
juz zaladowany — mozemy bez ceregieli importowac modele i wolac
`call_command`. Sygnatura: `def hook(ctx: dict) -> None`. Ctx zawiera
m.in. ``ctx["opts"]`` (dynamic CLI args), ``ctx["superuser"]`` (gdy
post_superuser), ``ctx["postgres"]`` itd.
"""

from __future__ import annotations

import json
import logging
import shlex
import subprocess
import sys

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


def fetch_pbn_token(ctx: dict) -> None:
    """Pull token PBN z hosta SSH przez dump_pbn_token | load_pbn_token.

    No-op gdy uzytkownik nie podal `--get-pbn-token-from`. Bledy SSH /
    dump-a sa logowane (nie raise), bo serwer dziala bez aktualnego tokenu
    — przyklad: deweloper nie jest na VPN-ie, ale chce uruchomic stack.
    """
    opts = ctx.get("opts") or {}
    raw_source = opts.get("pbn_ssh_source")
    if not raw_source:
        return  # flag nie podany — nic do roboty

    try:
        source = _parse_pbn_source(raw_source)
    except ValueError as exc:
        logger.warning("[runsite-hook] PBN: %s", exc)
        return

    remote_deploy_path = opts.get("pbn_remote_deploy_path") or "~/bpp-deploy"
    remote_compose_service = opts.get("pbn_remote_compose_service") or "appserver"

    payload_json = _dump_pbn_via_ssh(
        source,
        remote_deploy_path=remote_deploy_path,
        remote_compose_service=remote_compose_service,
    )
    if payload_json is None:
        return

    if _apply_pbn_to_local_db(payload_json, source):
        logger.info(
            "[runsite-hook] PBN token: ustawiony dla %s (zrodlo: %s)",
            source["django_username"],
            source["ssh_host"],
        )


def _parse_pbn_source(raw: str) -> dict:
    if "@" not in raw:
        raise ValueError(
            f"--get-pbn-token-from {raw!r}: brak '@'. "
            "Oczekiwany format USERNAME@SSH-HOST."
        )
    username, _, host = raw.rpartition("@")
    if not username or not host:
        raise ValueError(f"--get-pbn-token-from {raw!r}: pusty username albo host.")
    return {"django_username": username, "ssh_host": host}


def _quote_remote_path(path: str) -> str:
    # shlex.quote("~/foo") → "'~/foo'", a bash nie rozwija `~` wewnatrz
    # cudzyslowow. Zostawiamy wiodace ~/ poza quotem, reszte quotujemy.
    if path == "~" or path.startswith("~/"):
        head, _, tail = path.partition("/")
        if not tail:
            return head
        return f"{head}/{shlex.quote(tail)}"
    return shlex.quote(path)


def _dump_pbn_via_ssh(
    source: dict, *, remote_deploy_path: str, remote_compose_service: str
) -> str | None:
    remote_cmd = (
        f"cd {_quote_remote_path(remote_deploy_path)} && "
        f"docker compose exec -T {shlex.quote(remote_compose_service)} "
        f"python src/manage.py dump_pbn_token "
        f"--user={shlex.quote(source['django_username'])}"
    )
    ssh_cmd = ["ssh", source["ssh_host"], remote_cmd]
    logger.info(
        "[runsite-hook] PBN: ssh %s → docker compose exec %s dump_pbn_token --user=%s",
        source["ssh_host"],
        remote_compose_service,
        source["django_username"],
    )
    dump = subprocess.run(ssh_cmd, capture_output=True, text=True)
    if dump.returncode != 0:
        logger.warning(
            "[runsite-hook] PBN: ssh dump nieudane (rc=%d). stderr: %s",
            dump.returncode,
            dump.stderr.strip() or "(puste)",
        )
        return None
    if not dump.stdout.strip():
        logger.warning("[runsite-hook] PBN: zdalny dump zwrocil pusty wynik")
        return None
    # Sanity check: musi byc wlasciwy JSON
    try:
        json.loads(dump.stdout)
    except json.JSONDecodeError as exc:
        logger.warning("[runsite-hook] PBN: niewlasciwy JSON z ssh: %s", exc)
        return None
    return dump.stdout


def _apply_pbn_to_local_db(payload_json: str, source: dict) -> bool:
    """Wgraj JSON do lokalnej bazy przez `manage.py load_pbn_token`.

    Hook biegnie wewnatrz Django shella (przez `manage.py shell -c`), wiec
    `call_command("load_pbn_token", ...)` byloby naturalne — ALE `load_pbn_token`
    czyta JSON ze stdin, a `call_command` nie ma latwego sposobu na zywe
    podmienienie sys.stdin. Dlatego odpalamy podproces python z manage.py
    i przekazujemy JSON jako stdin pipe.
    """
    from pathlib import Path

    # Lokalizacja src/manage.py: hook biegnie z `manage.py shell -c` ktorego
    # cwd to src/, ale konfiguracja dla pewnosci.
    manage_py = Path(sys.argv[0]).resolve()
    if manage_py.name != "manage.py":
        # Edge case: hook moze byc odpalony nie przez manage.py shell -c.
        # Szukamy manage.py wzgledem __file__.
        manage_py = (Path(__file__).resolve().parent.parent / "manage.py").resolve()

    cmd = [
        sys.executable,
        str(manage_py),
        "load_pbn_token",
        f"--user={source['django_username']}",
    ]
    load = subprocess.run(
        cmd,
        input=payload_json,
        capture_output=True,
        text=True,
        cwd=str(manage_py.parent),
    )
    if load.returncode != 0:
        logger.warning(
            "[runsite-hook] PBN: lokalny load nieudany (rc=%d). stderr: %s",
            load.returncode,
            load.stderr.strip() or "(puste)",
        )
        return False
    return True
