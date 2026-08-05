"""Harvester OAI-PMH — przechodzi rekordy repozytorium przez ``ListRecords``.

Naprawione (#9 security review): usunięto zaszyty URL HTTP i zakres kończący
się w 2020 (teraz parametry), dodano timeout + ``raise_for_status``, zamieniono
usunięte w Pythonie 3.9 ``Element.getchildren()`` na parsowanie świadome
przestrzeni nazw OAI-PMH oraz dodano bezpieczniki przed nieskończoną pętlą
(limit żądań + wykrywanie powtórzonego ``resumptionToken``).
"""

from datetime import datetime
from xml.etree import ElementTree

import requests
from django.core.management import BaseCommand, CommandError

# OAI-PMH zawsze w tej przestrzeni nazw — bez niej findall() nie znajdzie węzłów.
OAI_NS = {"oai": "http://www.openarchives.org/OAI/2.0/"}


class Command(BaseCommand):
    help = "Harvestuje (przechodzi) rekordy OAI-PMH z repozytorium przez ListRecords."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            required=True,
            help="Endpoint OAI-PMH, np. https://bpp.example.pl/bpp/oai/"
            "oai-pmh-repository.xml",
        )
        parser.add_argument(
            "--from", dest="od", default=None, help="Data od (ISO 8601, opcjonalnie)"
        )
        parser.add_argument(
            "--until", dest="do", default=None, help="Data do (ISO 8601, opcjonalnie)"
        )
        parser.add_argument("--metadata-prefix", default="oai_dc")
        parser.add_argument(
            "--timeout",
            type=float,
            default=60.0,
            help="Timeout pojedynczego żądania HTTP w sekundach (domyślnie 60)",
        )
        parser.add_argument(
            "--max-requests",
            type=int,
            default=10000,
            help="Bezpiecznik: maksymalna liczba żądań (0 = bez limitu)",
        )

    def _first_params(self, options):
        params = {"verb": "ListRecords", "metadataPrefix": options["metadata_prefix"]}
        if options["od"]:
            params["from"] = options["od"]
        if options["do"]:
            params["until"] = options["do"]
        return params

    def _parse_response(self, url, content):
        """Zwróć (rekordy, token) z odpowiedzi ListRecords; rzuć na błąd OAI."""
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as e:
            raise CommandError(f"Niepoprawny XML z {url}: {e}") from e

        error = root.find("oai:error", OAI_NS)
        if error is not None:
            raise CommandError(f"OAI-PMH error [{error.get('code')}]: {error.text}")

        list_records = root.find("oai:ListRecords", OAI_NS)
        if list_records is None:
            return [], None

        records = list_records.findall("oai:record", OAI_NS)
        token_el = list_records.find("oai:resumptionToken", OAI_NS)
        token = (
            token_el.text.strip()
            if token_el is not None and token_el.text and token_el.text.strip()
            else None
        )
        return records, token

    def handle(self, *args, **options):
        url = options["url"]
        timeout = options["timeout"]
        max_requests = options["max_requests"]

        params = self._first_params(options)
        session = requests.Session()
        seen_tokens = set()
        requests_made = 0
        records_total = 0

        while True:
            if max_requests and requests_made >= max_requests:
                raise CommandError(
                    f"Przekroczono limit {max_requests} żądań — przerywam "
                    "(możliwa pętla resumptionToken)."
                )

            start = datetime.now()
            res = session.get(url, params=params, timeout=timeout)
            res.raise_for_status()
            requests_made += 1

            records, token = self._parse_response(url, res.content)
            records_total += len(records)

            delta = datetime.now() - start
            self.stdout.write(
                f"żądanie #{requests_made}: {len(records)} rekordów, "
                f"łącznie {records_total}, czas {delta}"
                + (f", token {token[:20]}…" if token else "")
            )

            if not token:
                break

            if token in seen_tokens:
                raise CommandError(
                    f"resumptionToken powtórzył się ({token[:20]}…) — przerywam, "
                    "żeby nie kręcić się w nieskończoność."
                )
            seen_tokens.add(token)

            # Przy przewijaniu OAI-PMH wysyła się WYŁĄCZNIE verb + resumptionToken.
            params = {"verb": "ListRecords", "resumptionToken": token}

        self.stdout.write(
            self.style.SUCCESS(
                f"Zakończono: {records_total} rekordów w {requests_made} żądaniach."
            )
        )
