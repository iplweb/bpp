"""Multiplekser logów subprocess-ów do jednego stdout z kolorowymi prefixami.

Działa jak ``docker compose up`` — każdy proces ma własną kolumnę z nazwą
i kolorem ANSI; linie są serializowane przez Lock więc się nie sklejają.

Czytamy w wątkach (po jednym na strumień), bo subprocess.Popen.stdout
to plik blokujący na ``readline()``. Wątki są daemon — gdy główny proces
schodzi po Ctrl-C, czytniki nie blokują wyjścia.

Buforowanie po stronie producenta: dla podprocesów Pythona (runserver,
celery) caller MUSI ustawić ``PYTHONUNBUFFERED=1`` w env, inaczej Python
wykrywa że stdout to pipe (nie TTY) i włącza block buffering — banner
wyświetli się dopiero po zapełnieniu 4 KB. Dla ``docker logs -f`` line
buffering jest domyślny.
"""

from __future__ import annotations

import sys
import threading
from typing import IO, TextIO

# ANSI 8-color codes — bezpieczne dla każdego terminala (xterm/iTerm/Konsole).
COLOR_CYAN = "\033[36m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_MAGENTA = "\033[35m"
COLOR_RESET = "\033[0m"


class LogMultiplexer:
    """Combines multiple subprocess byte streams into one TTY-friendly output.

    Use:
        mux = LogMultiplexer()
        mux.add_stream("web", COLOR_CYAN, runserver_proc.stdout)
        mux.add_stream("celery", COLOR_GREEN, celery_proc.stdout)
        mux.add_stream("pg", COLOR_YELLOW, pg_logs_proc.stdout)
        # streams flow to stdout while caller does its blocking work
    """

    def __init__(
        self,
        *,
        output: TextIO | None = None,
        use_color: bool | None = None,
    ):
        self._output: TextIO = output if output is not None else sys.stdout
        if use_color is None:
            use_color = bool(getattr(self._output, "isatty", lambda: False)())
        self._use_color = use_color
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []
        self._registered: list[str] = []

    @property
    def _name_width(self) -> int:
        return max((len(n) for n in self._registered), default=0)

    def add_stream(self, name: str, color: str, stream: IO[bytes]) -> None:
        """Spawn a daemon reader thread for ``stream``.

        ``color`` is an ANSI escape (e.g. ``COLOR_CYAN``); ignored when
        ``use_color`` is False. ``stream`` must yield bytes (subprocess
        ``stdout`` opened in default binary mode).
        """
        self._registered.append(name)
        t = threading.Thread(
            target=self._reader,
            args=(name, color, stream),
            daemon=True,
            name=f"logmux-{name}",
        )
        self._threads.append(t)
        t.start()

    def _reader(self, name: str, color: str, stream: IO[bytes]) -> None:
        try:
            for raw in iter(stream.readline, b""):
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                self._write(name, color, line)
        finally:
            try:
                stream.close()
            except Exception:
                # Stream już zamknięty / proces ubity — log close nie ma znaczenia.
                pass

    def _write(self, name: str, color: str, line: str) -> None:
        prefix = f"{name:<{self._name_width}} | "
        if self._use_color:
            prefix = f"{color}{prefix}{COLOR_RESET}"
        with self._lock:
            self._output.write(prefix + line + "\n")
            try:
                self._output.flush()
            except (BrokenPipeError, ValueError):
                # stdout zamknięty (np. Ctrl-C w trakcie pisania) — kończymy cicho.
                pass

    def join(self, timeout: float | None = None) -> None:
        """Wait for all reader threads (mostly for tests)."""
        for t in self._threads:
            t.join(timeout=timeout)
