"""SSH pipe: dump_pbn_token (zdalny) → load_pbn_token (lokalny).

Użyte przez `run_site --get-pbn-token-from USERNAME@SSH-HOST`. SSH host
to alias z ~/.ssh/config (z wpisanym użytkownikiem ssh — nie mylić z
USERNAME, który jest nazwą użytkownika Django, taką samą po obu stronach).

Na zdalnym hoście BPP jest zarządzane przez bpp-deploy (docker compose),
więc komenda `dump_pbn_token` jest odpalana przez `docker compose exec`
z katalogu z plikami compose.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass

from .processes import _python_executable, _src_dir


@dataclass(frozen=True)
class PbnTokenSource:
    """Sparsowany argument `--get-pbn-token-from`."""

    django_username: str
    ssh_host: str

    @classmethod
    def parse(cls, raw: str) -> PbnTokenSource:
        if "@" not in raw:
            raise ValueError(
                f"--get-pbn-token-from {raw!r}: brak '@'. "
                "Oczekiwany format USERNAME@SSH-HOST."
            )
        username, _, host = raw.rpartition("@")
        if not username or not host:
            raise ValueError(f"--get-pbn-token-from {raw!r}: pusty username albo host.")
        return cls(django_username=username, ssh_host=host)


def fetch_pbn_token_via_ssh(
    source: PbnTokenSource,
    *,
    remote_deploy_path: str,
    remote_compose_service: str,
    local_env: dict[str, str],
    log,
) -> bool:
    """Pobierz token PBN ze zdalnego hosta i wgraj do lokalnej bazy.

    Zwraca True jeśli operacja się powiodła. Błędy są łapane i
    raportowane przez ``log`` — caller decyduje czy traktować to jako
    fatal. Domyślnie w run_site to tylko warning, bo server nadal
    działa bez aktualnego tokenu.
    """
    remote_cmd = (
        f"cd {shlex.quote(remote_deploy_path)} && "
        f"docker compose exec -T {shlex.quote(remote_compose_service)} "
        f"python src/manage.py dump_pbn_token "
        f"--user={shlex.quote(source.django_username)}"
    )
    ssh_cmd = ["ssh", source.ssh_host, remote_cmd]

    log(
        f"[run_site] PBN token: ssh {source.ssh_host} → "
        f"docker compose exec {remote_compose_service} "
        f"dump_pbn_token --user={source.django_username}"
    )
    dump = subprocess.run(
        ssh_cmd,
        capture_output=True,
        text=True,
    )
    if dump.returncode != 0:
        log(
            f"[run_site] PBN token: ssh dump nieudane (rc={dump.returncode}). "
            f"stderr: {dump.stderr.strip() or '(puste)'}"
        )
        return False
    if not dump.stdout.strip():
        log("[run_site] PBN token: zdalny dump zwrócił pusty wynik.")
        return False

    load_cmd = [
        _python_executable(),
        str(_src_dir() / "manage.py"),
        "load_pbn_token",
        f"--user={source.django_username}",
    ]
    load = subprocess.run(
        load_cmd,
        input=dump.stdout,
        capture_output=True,
        text=True,
        env=local_env,
        cwd=str(_src_dir()),
    )
    if load.returncode != 0:
        log(
            f"[run_site] PBN token: lokalny load nieudany "
            f"(rc={load.returncode}). stderr: "
            f"{load.stderr.strip() or '(puste)'}"
        )
        return False

    log(
        f"[run_site] PBN token: ustawiony dla {source.django_username} "
        f"(źródło: {source.ssh_host})."
    )
    return True
