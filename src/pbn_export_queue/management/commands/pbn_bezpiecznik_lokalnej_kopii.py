"""Zabezpiecza lokalną kopię bazy produkcyjnej przed wysyłką do PBN.

Wołana automatycznie przez ``run-site`` (hook ``zabezpiecz_lokalna_kopie``)
i przez ``pbn_zaloguj_lokalnie``; można ją też uruchomić ręcznie:

    uv run python src/manage.py pbn_bezpiecznik_lokalnej_kopii \\
        --tak-to-jest-lokalna-kopia

Zamyka wpisy kolejki eksportu przyniesione z produkcji. NIE wyłącza
ręcznej wysyłki rekordu — to właśnie deweloper chce testować.
"""

from django.core.management.base import BaseCommand, CommandError

from pbn_export_queue.bezpiecznik import (
    PrzelacznikNiedostepny,
    powody_nielokalnosci,
    stan_automatow,
    ustaw_odblokowanie,
    wstrzymaj_kolejke,
)

FLAGA = "--tak-to-jest-lokalna-kopia"


class Command(BaseCommand):
    help = (
        "Wstrzymuje kolejkę eksportu do PBN na lokalnej kopii bazy produkcyjnej. "
        "Odmawia działania na instancji, która nie wygląda na lokalną."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            FLAGA,
            action="store_true",
            dest="potwierdzenie",
            help="Wymagane potwierdzenie: komenda zamyka wpisy kolejki PBN.",
        )
        parser.add_argument(
            "--lokalny-host-bazy",
            action="append",
            default=[],
            metavar="HOST",
            help=(
                "Dodatkowa nazwa hosta bazy uznawana za lokalną (np. `db` w "
                "deweloperskim docker compose). Można podać kilka razy."
            ),
        )

        parser.add_argument(
            "--automaty",
            choices=("wstrzymaj", "wlacz"),
            default=None,
            help=(
                "Ustaw przełącznik automatów wysyłki do PBN: `wstrzymaj` "
                "(stan domyślny) albo `wlacz` (świadome testowanie wysyłki "
                "z kolejki). Bez tej opcji przełącznik zostaje, jak był. "
                "Kolejka z kopii bazy jest zamykana zawsze."
            ),
        )

    def handle(
        self, *args, potwierdzenie=False, lokalny_host_bazy=(), automaty=None, **kw
    ):
        powody = powody_nielokalnosci(lokalny_host_bazy)
        if powody:
            raise CommandError(
                "ODMOWA: ta instancja nie wygląda na lokalną kopię — "
                + "; ".join(powody)
                + ". Nic nie zmieniono."
            )
        if not potwierdzenie:
            raise CommandError(
                f"ODMOWA: brak flagi {FLAGA}. Komenda zamyka wszystkie "
                "niezakończone wpisy kolejki eksportu do PBN — uruchamiaj ją "
                "wyłącznie na lokalnej kopii bazy. Nic nie zmieniono."
            )

        zamkniete = wstrzymaj_kolejke()
        self.stdout.write(
            "Kolejka eksportu do PBN: zamknięto "
            f"{zamkniete['wysylka']} wpis(ów) wysyłki i "
            f"{zamkniete['wycofanie']} wpis(ów) wycofania oświadczeń "
            "(zostają w historii kolejki; wysyłkę można ponowić ręcznie)."
        )

        if automaty is not None:
            try:
                ustaw_odblokowanie(automaty == "wlacz", lokalny_host_bazy)
            except PrzelacznikNiedostepny as e:
                # Np. DJANGO_BPP_PBN_WSTRZYMAJ_AUTOMATY=0 — stan raportujemy
                # niżej, komenda nie udaje, że coś przełączyła.
                self.stdout.write(self.style.WARNING(f"UWAGA: {e}"))

        stan = stan_automatow()
        if stan.wstrzymane:
            self.stdout.write(
                "Automaty wysyłki do PBN: WSTRZYMANE — ponowienie po "
                "zalogowaniu, watchdog kolejki, łańcuch „następny z kolejki”, "
                "kosz/przywrócenie. Odblokowanie: strona kolejki eksportu PBN "
                "albo `run-site run --pbn-automaty wlacz`."
            )
        else:
            powod = (
                "odblokowane przełącznikiem"
                if stan.wstrzymywanie_wlaczone
                else "DJANGO_BPP_PBN_WSTRZYMAJ_AUTOMATY=0"
            )
            self.stdout.write(
                self.style.WARNING(
                    f"UWAGA: automaty wysyłki do PBN są WŁĄCZONE ({powod}). "
                    "Nowe wpisy kolejki będą wysyłane samoczynnie, a kosz "
                    "wycofa oświadczenia w PBN."
                )
            )
        self.stdout.write(
            "Ręczna wysyłka pojedynczego rekordu („Zapisz i wyślij do PBN”, "
            "„wyślij ponownie” w kolejce) pozostaje włączona."
        )
        return None
