"""Pobiera dane pracowników z USOS API i wypisuje je na ekran.

Komenda niczego nie zapisuje do bazy — służy do obejrzenia, jakie dane uczelnia
faktycznie trzyma w USOS-ie (w szczególności: czy ``external_ids`` z ORCID-em
i PBN UUID są wypełnione), zanim powstanie import do modelu ``Autor``.

Wymaga consumer key wydanego przez administratora USOS danej uczelni::

    uv run python src/manage.py usos_autorzy \\
        --base-url https://usosapps.umlub.pl/ \\
        --consumer-key ... --consumer-secret ... \\
        --root 1000000000 --tylko-nauczyciele --limit 20
"""

import json

from django.core.management.base import BaseCommand, CommandError

from usos_api.autorzy import pobierz_pracownikow
from usos_api.client import UsosApiError
from usos_api.conf import buduj_klienta
from usos_api.jednostki import pobierz_jednostki


class Command(BaseCommand):
    help = "Pobiera dane pracowników z USOS API (nie zapisuje do bazy)."

    def add_arguments(self, parser):
        parser.add_argument("--base-url")
        parser.add_argument("--consumer-key")
        parser.add_argument("--consumer-secret")
        parser.add_argument(
            "--jednostka",
            action="append",
            dest="jednostki",
            default=[],
            help="Kod jednostki; można podać wielokrotnie.",
        )
        parser.add_argument(
            "--root",
            help="Zamiast pojedynczych jednostek: zejdź po całym poddrzewie "
            "tej jednostki.",
        )
        parser.add_argument(
            "--tylko-nauczyciele",
            action="store_true",
            dest="tylko_nauczyciele",
            help="Ogranicz do aktywnych nauczycieli akademickich.",
        )
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument(
            "--json",
            action="store_true",
            dest="jako_json",
            help="Wypisz surowy JSON zamiast tabeli.",
        )

    def handle(self, *args, **opcje):
        klient = buduj_klienta(
            base_url=opcje.get("base_url"),
            consumer_key=opcje.get("consumer_key"),
            consumer_secret=opcje.get("consumer_secret"),
        )

        if klient.anonimowy:
            raise CommandError(
                "services/users/staff_index wymaga podpisania żądania — podaj "
                "--consumer-key i --consumer-secret (albo ustaw "
                "USOS_API_CONSUMER_KEY/SECRET). Klucz wydaje administrator USOS "
                "danej uczelni."
            )

        if not opcje["jednostki"] and not opcje["root"]:
            raise CommandError("Podaj --jednostka (można wielokrotnie) albo --root.")

        try:
            kody = self._kody_jednostek(klient, opcje)
            pracownicy = self._zbierz(klient, kody, opcje)
        except UsosApiError as błąd:
            raise CommandError(f"USOS API odmówił: {błąd}") from błąd

        if opcje["jako_json"]:
            self.stdout.write(json.dumps(pracownicy, indent=2, ensure_ascii=False))
            return

        for pracownik in pracownicy:
            self.stdout.write(self._opis(pracownik))

        self.stdout.write("")
        self.stdout.write(f"Razem osób: {len(pracownicy)}")

    def _kody_jednostek(self, klient, opcje):
        if opcje["root"]:
            return [
                jednostka["usos_id"]
                for jednostka in pobierz_jednostki(klient, opcje["root"])
            ]
        return opcje["jednostki"]

    def _zbierz(self, klient, kody, opcje):
        """Zbiera pracowników jednostka po jednostce, bez powtórzeń.

        Ta sama osoba bywa zatrudniona w kilku jednostkach, a ``staff_index``
        nie schodzi rekurencyjnie — pytamy więc o każdą jednostkę osobno
        i deduplikujemy po identyfikatorze USOS.
        """
        limit = opcje["limit"]
        znalezieni = {}

        for kod in kody:
            for pracownik in pobierz_pracownikow(
                klient, kod, tylko_nauczyciele=opcje["tylko_nauczyciele"]
            ):
                znalezieni.setdefault(pracownik["usos_id"], pracownik)
                if limit is not None and len(znalezieni) >= limit:
                    return list(znalezieni.values())

        return list(znalezieni.values())

    def _opis(self, pracownik):
        nazwa = " ".join(
            część
            for część in (
                pracownik["tytul_przed"],
                pracownik["imie"],
                pracownik["nazwisko"],
            )
            if część
        )
        części = [f"{pracownik['usos_id']:>10}  {nazwa}"]
        części.append(f"ORCID: {pracownik['orcid'] or '—'}")
        części.append(f"PBN: {pracownik['pbn_id'] or '—'}")
        if pracownik["nauczyciel_akademicki"]:
            części.append("nauczyciel akademicki")
        for stanowisko in pracownik["stanowiska"]:
            części.append(f"{stanowisko['jednostka']}: {stanowisko['stanowisko']}")
        return " | ".join(części)
