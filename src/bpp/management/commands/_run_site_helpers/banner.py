"""Banner z URL-ami i statusem stack-u."""

_TEMPLATE = """\
╔════════════════════════════════════════════════════════════════╗
║  BPP run-site — stack uruchomiony                              ║
╠════════════════════════════════════════════════════════════════╣
║  Appserver:  {appserver_url:<50}║
║  Admin:      {admin_url:<50}║
║              login: {admin_user:<10} hasło: {admin_pass:<25}║
║                                                                ║
║  PostgreSQL: {pg_endpoint:<50}║
║  Redis:      {redis_endpoint:<50}║
║                                                                ║
║  Celery:     {celery_label:<50}║
║  Dump:       {dump_label:<50}║
╠════════════════════════════════════════════════════════════════╣
║  Logi z web/celery/pg pokazują się poniżej (kolory).           ║
║  Ctrl-C zakończy serwer i sprzątnie kontenery.                 ║
╚════════════════════════════════════════════════════════════════╝
"""


def _shorten_path(value: str, max_len: int) -> str:
    """Skróć string do max_len znaków zachowując prawą stronę (nazwę pliku)."""
    if len(value) <= max_len:
        return value
    return "…" + value[-(max_len - 1) :]


def format_banner(
    *,
    appserver_url: str,
    admin_url: str,
    admin_user: str,
    admin_pass: str,
    pg_host: str,
    pg_port: int,
    redis_host: str,
    redis_port: int,
    with_celery: bool,
    dump_label: str,
) -> str:
    """Sformatowany banner z parametrami stack-u (plain text + box-drawing chars)."""
    celery_label = "running (--pool=solo)" if with_celery else "disabled"
    return _TEMPLATE.format(
        appserver_url=appserver_url,
        admin_url=admin_url,
        admin_user=admin_user,
        admin_pass=admin_pass,
        pg_endpoint=f"{pg_host}:{pg_port} (bpp/password)",
        redis_endpoint=f"{redis_host}:{redis_port}",
        celery_label=celery_label,
        dump_label=_shorten_path(dump_label, 50),
    )


def format_agent_help(*, appserver_url: str, token_path: str, port_path: str) -> str:
    """Snippet copy-paste dla agenta kodującego (WebFetch / curl).

    Drukowany poniżej banera. Brak box-drawing chars (terminale czasem
    je mangą przy zaznaczaniu — fragment ma być prosto kopiowalny).

    Snippet czyta port z ``port_path`` zamiast hardcode'ować go z
    ``appserver_url`` — port się zmienia przy każdym uruchomieniu
    run_site, ale wzorzec polecenia z dotfile'a działa bez modyfikacji.
    """
    return (
        "─── Auto-login dla agenta (WebFetch / curl) "
        "──────────────────────────────\n"
        f"  Adres aktualnej sesji: {appserver_url}\n"
        f"  Token sesji admina:    {token_path}\n"
        f"  Port runservera:       {port_path}\n"
        "  (oba pliki: gitignored, kasowane na exit run_site;\n"
        "   token z chmod 600 — port nie jest sekretem)\n"
        "\n"
        "  Pobranie zalogowanej strony bez wpisywania hasła:\n"
        f'    T=$(cat "{token_path}")\n'
        f'    PORT=$(cat "{port_path}")\n'
        "    J=$(mktemp)\n"
        '    curl -sc "$J" -L '
        '"http://localhost:$PORT/__run_site_autologin__/?token=$T" '
        ">/dev/null\n"
        '    curl -sb "$J" "http://localhost:$PORT/<path>"\n'
        '    rm "$J"\n'
        "\n"
        '  Szczegóły dla agenta: patrz CLAUDE.md → "Autologin dla agentów".\n'
        "──────────────────────────────────────────────────────────────────────\n"
    )
