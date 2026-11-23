"""Pobiera konfigurację aplikacji PBN (i opcjonalnie token użytkownika)
z serwera po SSH i zapisuje ją lokalnie, szyfrując lokalnym kluczem.

    uv run python src/manage.py pbn_konfiguracja_z_serwera LOGIN@HOST

HOST to alias SSH serwera z ``bpp-deploy``; LOGIN to użytkownik BPP, którego
token PBN też przenieść (samo ``HOST`` = tylko konfiguracja aplikacji).
Szczegóły: ``pbn_api/konfiguracja_z_serwera.py``,
``docs/deweloper/testowanie-pbn-lokalnie.md``.
"""

import sys

from django.core.management import BaseCommand, CommandError, call_command

from pbn_api import konfiguracja_z_serwera as kzs


class Command(BaseCommand):
    help = (
        "Przenosi konfigurację aplikacji PBN (adres API, nazwa i token "
        "aplikacji, opcjonalnie token użytkownika) z serwera na lokalną "
        "kopię bazy. Sekretów nie wypisuje."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "zrodlo",
            nargs="?",
            help="LOGIN@HOST albo HOST (alias SSH). LOGIN = użytkownik BPP.",
        )
        parser.add_argument(
            "--stdin",
            action="store_true",
            help=(
                "Zamiast łączyć się po SSH, wczytaj wyjście zdalnego polecenia "
                "ze stdin (patrz --wypisz-zdalne-polecenie)."
            ),
        )
        parser.add_argument(
            "--wypisz-zdalne-polecenie",
            action="store_true",
            help=(
                "Wypisz polecenie do uruchomienia na serwerze (bez sekretów) "
                "i zakończ. Jego wyjście podaj potokiem do --stdin."
            ),
        )
        parser.add_argument(
            "--user", default=None, help="Login użytkownika BPP (przy --stdin)."
        )
        parser.add_argument(
            "--user-lokalny",
            default=None,
            help="Lokalny login, któremu zapisać token (domyślnie taki sam).",
        )
        parser.add_argument(
            "--uczelnia", default=None, help="Skrót lokalnej uczelni (gdy kilka)."
        )
        parser.add_argument(
            "--uczelnia-zdalna",
            default=None,
            help="Skrót uczelni na serwerze (gdy kilka).",
        )
        parser.add_argument("--remote-deploy-path", default="~/bpp-deploy")
        parser.add_argument("--remote-compose-service", default="appserver")
        parser.add_argument(
            "--bez-bezpiecznika",
            action="store_true",
            help=(
                "Nie uruchamiaj wcześniej pbn_bezpiecznik_lokalnej_kopii "
                "(domyślnie: najpierw bezpiecznik, a gdy odmówi — nic nie "
                "jest pobierane)."
            ),
        )

    def handle(self, *args, zrodlo=None, **o):
        login, host = o["user"], None
        if zrodlo:
            try:
                login_ze_zrodla, host = kzs.rozbierz_zrodlo(zrodlo)
            except kzs.BladPrzenoszenia as e:
                raise CommandError(str(e)) from e
            login = login_ze_zrodla or login

        if o["wypisz_zdalne_polecenie"]:
            self.stdout.write(
                kzs.zdalne_polecenie(
                    login,
                    o["uczelnia_zdalna"],
                    o["remote_deploy_path"],
                    o["remote_compose_service"],
                )
            )
            return

        if not o["stdin"] and not host:
            raise CommandError("Podaj LOGIN@HOST (albo HOST), albo użyj --stdin.")

        if not o["bez_bezpiecznika"]:
            # Najpierw bezpiecznik: prawdziwy token nie może trafić do bazy,
            # w której czeka kolejka eksportu z produkcji. Na instancji
            # nielokalnej bezpiecznik odmawia i na tym kończymy.
            call_command(
                "pbn_bezpiecznik_lokalnej_kopii",
                potwierdzenie=True,
                stdout=self.stdout,
            )

        try:
            if o["stdin"]:
                dane = kzs.rozbierz_odpowiedz(sys.stdin.read())
            else:
                self.stdout.write(f"Pobieram konfigurację PBN z {host} (ssh)…")
                dane = kzs.pobierz_z_serwera(
                    host,
                    login=login,
                    skrot=o["uczelnia_zdalna"],
                    remote_deploy_path=o["remote_deploy_path"],
                    remote_compose_service=o["remote_compose_service"],
                )
            raport = kzs.zastosuj(
                dane, skrot_lokalny=o["uczelnia"], login_lokalny=o["user_lokalny"]
            )
        except kzs.BladPrzenoszenia as e:
            raise CommandError(str(e)) from e

        for linia in raport:
            styl = self.style.WARNING if linia.startswith("UWAGA") else str
            self.stdout.write(styl(linia))
