"""SSH pipe: dump_pbn_token (zdalny) → load_pbn_token (lokalny).

Użyte przez `run_site --get-pbn-token-from USERNAME@SSH-HOST`. SSH host
to alias z ~/.ssh/config (z wpisanym użytkownikiem ssh — nie mylić z
USERNAME, który jest nazwą użytkownika Django, taką samą po obu stronach).

Na zdalnym hoście BPP jest zarządzane przez bpp-deploy (docker compose),
więc komenda `dump_pbn_token` jest odpalana przez `docker compose exec`
z katalogu z plikami compose.

Wynik dumpa (JSON) jest opcjonalnie cache'owany w pliku (`cache_path`),
żeby kolejne uruchomienia run_site nie musiały odpalać SSH — przydatne
gdy zdalny host bywa niedostępny. Gdy cache jest dla innego użytkownika
niż żądany, jest pomijany. Aby wymusić odświeżenie tokenu, usuń plik
cache ręcznie.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

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
    cache_path: Path | None = None,
) -> bool:
    """Pobierz token PBN (z cache albo zdalnie) i wgraj do lokalnej bazy.

    Zwraca True jeśli operacja się powiodła. Błędy są łapane i
    raportowane przez ``log`` — caller decyduje czy traktować to jako
    fatal. Domyślnie w run_site to tylko warning, bo server nadal
    działa bez aktualnego tokenu.

    Gdy ``cache_path`` jest podane i plik istnieje, JSON jest czytany
    stamtąd zamiast z SSH. Po pomyślnym dumpie SSH wynik jest
    zapisywany do ``cache_path`` (chmod 600).
    """
    payload_json = _read_cache(cache_path, source, log)

    if payload_json is None:
        payload_json = _dump_via_ssh(
            source,
            remote_deploy_path=remote_deploy_path,
            remote_compose_service=remote_compose_service,
            log=log,
        )
        if payload_json is None:
            return False
        _write_cache(cache_path, payload_json, log)

    return _apply_to_local_db(payload_json, source, local_env, log)


def _read_cache(cache_path: Path | None, source: PbnTokenSource, log) -> str | None:
    """Zwróć zawartość cache (JSON) gdy jest aktualna dla żądanego usera.

    Pomija cache i zwraca None gdy: ścieżka nie podana, plik nie
    istnieje, nieczytelny, niepoprawny JSON, albo trzyma token dla
    innego użytkownika. Nie kasuje pliku — to gestia usera.
    """
    if cache_path is None or not cache_path.is_file():
        return None
    try:
        raw = cache_path.read_text()
    except OSError as exc:
        log(f"[run_site] PBN token: nie mogę odczytać {cache_path}: {exc}")
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        log(
            f"[run_site] PBN token: cache {cache_path} ma nieprawidłowy "
            f"JSON ({exc}); pomijam."
        )
        return None
    cached_user = payload.get("username") if isinstance(payload, dict) else None
    if cached_user != source.django_username:
        log(
            f"[run_site] PBN token: cache {cache_path} jest dla użytkownika "
            f"{cached_user!r}, a zażądano {source.django_username!r}; "
            "pomijam cache."
        )
        return None
    log(f"[run_site] PBN token: wczytuję z cache {cache_path}")
    return raw


def _write_cache(cache_path: Path | None, payload_json: str, log) -> None:
    """Zapisz JSON do cache i ustaw chmod 600. Błąd I/O loguje, nie rzuca."""
    if cache_path is None:
        return
    try:
        cache_path.write_text(payload_json)
    except OSError as exc:
        log(f"[run_site] PBN token: nie udało się zapisać cache {cache_path}: {exc}")
        return
    try:
        cache_path.chmod(0o600)
    except OSError as exc:
        # Niektóre FS (np. zamontowany SMB) nie wspierają chmod —
        # zawartość już zapisana, więc tylko ostrzegamy.
        log(
            f"[run_site] PBN token: zapisano {cache_path}, ale chmod 600 "
            f"się nie udał ({exc})."
        )
        return
    log(f"[run_site] PBN token: zapisany do cache {cache_path}")


def _dump_via_ssh(
    source: PbnTokenSource,
    *,
    remote_deploy_path: str,
    remote_compose_service: str,
    log,
) -> str | None:
    """Odpal SSH dump_pbn_token i zwróć stdout (JSON) lub None przy błędzie."""
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
        return None
    if not dump.stdout.strip():
        log("[run_site] PBN token: zdalny dump zwrócił pusty wynik.")
        return None
    return dump.stdout


def _apply_to_local_db(
    payload_json: str,
    source: PbnTokenSource,
    local_env: dict[str, str],
    log,
) -> bool:
    """Wgraj JSON do lokalnej bazy przez load_pbn_token."""
    load_cmd = [
        _python_executable(),
        str(_src_dir() / "manage.py"),
        "load_pbn_token",
        f"--user={source.django_username}",
    ]
    load = subprocess.run(
        load_cmd,
        input=payload_json,
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
