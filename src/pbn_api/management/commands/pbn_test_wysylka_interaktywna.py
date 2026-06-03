"""Interaktywne narzędzie do testowania wysyłki publikacji i oświadczeń do PBN.

Narzędzie prowadzi użytkownika krok po kroku przez pełen flow wysyłki
wybranej publikacji do PBN. Dla każdego żądania HTTP pokazuje metodę,
URL, body (wysyłane dane), a dla odpowiedzi — status i treść. Między
krokami czeka na Enter.

Narzędzie NIE modyfikuje lokalnej bazy BPP — służy wyłącznie do audytu
zachowania API PBN przed docelową refaktoryzacją ``sync_publication``.

Tryb ``--dry-run`` pokazuje wszystko, ale nie wysyła niczego do PBN.

Użycie:
    uv run python src/manage.py pbn_test_wysylka_interaktywna \\
        --wydawnictwo-zwarte 123 --user-token <TOKEN> [--dry-run]

    uv run python src/manage.py pbn_test_wysylka_interaktywna \\
        --wydawnictwo-ciagle 456 [--dry-run]
"""

import json
import time
from typing import Any

from django.core.management.base import CommandError

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.const import (
    PBN_DELETE_PUBLICATION_STATEMENT,
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_POST_INSTITUTION_STATEMENTS_URL,
    PBN_POST_PUBLICATION_NO_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
)
from pbn_api.exceptions import (
    AccessDeniedException,
    DaneLokalneWymagajaAktualizacjiException,
    HttpException,
    NeedsPBNAuthorisationException,
    PraceSerwisoweException,
    ResourceLockedException,
)
from pbn_api.management.commands.util import PBNBaseCommand
from pbn_api.models import OswiadczenieInstytucji


class UserAbort(Exception):
    """Użytkownik przerwał flow (np. wpisał `q` na pytanie o Enter)."""


def _json_truncated(obj: Any, max_len: int = 800) -> str:
    """Zwraca JSON sformatowany, ewentualnie skrócony do ``max_len`` znaków."""
    text = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n... (obcięto, pełny JSON ma {len(text)} znaków)"


class Command(PBNBaseCommand):
    help = (
        "Interaktywny REPL testujący wysyłkę publikacji i oświadczeń do PBN "
        "krok po kroku. Nie modyfikuje lokalnej bazy BPP."
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--wydawnictwo-zwarte",
            type=int,
            help="PK rekordu Wydawnictwo_Zwarte do przetestowania",
        )
        parser.add_argument(
            "--wydawnictwo-ciagle",
            type=int,
            help="PK rekordu Wydawnictwo_Ciagle do przetestowania",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Pokazuj co byłoby wysyłane, ale nie wysyłaj niczego do PBN",
        )
        parser.add_argument(
            "--yes-all",
            action="store_true",
            help=(
                "Automatycznie akceptuj wszystkie pytania Enter "
                "(bez interakcji — do testów automatycznych)."
            ),
        )

    def handle(self, app_id, app_token, base_url, user_token, *args, **options):
        self.dry_run = options["dry_run"]
        self.yes_all = options["yes_all"]
        self.stats: list[tuple[str, str]] = []

        if self.dry_run:
            self._warn("TRYB DRY-RUN — żadne żądania nie będą wysłane do PBN.")

        publication = self._get_publication(options)

        try:
            pbn_client = self.get_client(app_id, app_token, base_url, user_token)
        except Exception as e:
            raise CommandError(f"Nie mogę utworzyć klienta PBN: {e}") from e

        try:
            self._run_flow(pbn_client, publication)
        except UserAbort:
            self._warn("Przerwano przez użytkownika.")
        finally:
            self._print_summary()

    # ------------------------- wybór publikacji -------------------------

    def _get_publication(self, options):
        pk_zwarte = options.get("wydawnictwo_zwarte")
        pk_ciagle = options.get("wydawnictwo_ciagle")

        if bool(pk_zwarte) == bool(pk_ciagle):
            raise CommandError(
                "Podaj dokładnie jedno z: --wydawnictwo-zwarte <PK> "
                "lub --wydawnictwo-ciagle <PK>."
            )

        if pk_zwarte:
            try:
                return Wydawnictwo_Zwarte.objects.get(pk=pk_zwarte)
            except Wydawnictwo_Zwarte.DoesNotExist as e:
                raise CommandError(
                    f"Nie znaleziono Wydawnictwo_Zwarte o pk={pk_zwarte}"
                ) from e

        try:
            return Wydawnictwo_Ciagle.objects.get(pk=pk_ciagle)
        except Wydawnictwo_Ciagle.DoesNotExist as e:
            raise CommandError(
                f"Nie znaleziono Wydawnictwo_Ciagle o pk={pk_ciagle}"
            ) from e

    # ------------------------- główny flow -------------------------

    def _run_flow(self, pbn_client, publication):
        self._step_show_publication(publication)
        js, bez_oswiadczen = self._step_generate_json(publication)
        endpoint_choice = self._step_choose_endpoint(bez_oswiadczen)
        object_id = self._step_post_publication(
            pbn_client, publication, js, endpoint_choice
        )
        if not object_id:
            self._warn("Brak objectId z PBN — kończę flow. Sprawdź odpowiedź serwera.")
            return

        pbn_statements = self._step_get_pbn_statements(pbn_client, object_id)
        identyczne = self._step_compare_statements(publication, pbn_statements)

        # Zawsze pytamy osobno o DELETE i POST — nawet gdy identyczne.
        # Default zależy od wyniku porównania (False dla identycznych,
        # True dla różnic), ale user ma ostatnie słowo. Pozwala to
        # wymusić operację (np. żeby empirycznie sprawdzić jak PBN
        # reaguje na „zbędny" DELETE+POST).
        ctx = "identyczne — zwykle nie trzeba" if identyczne else "są różnice"
        default_act = not identyczne

        if self._prompt_yes_no(
            f"Czy skasować oświadczenia w PBN? ({ctx})", default=default_act
        ):
            self._step_delete_statements(pbn_client, object_id)
        else:
            self._info("Pominięto DELETE oświadczeń (decyzja użytkownika).")
            self.stats.append(("DELETE oświadczeń", "pominięty"))

        if self._prompt_yes_no(
            f"Czy wysłać (POST) oświadczenia do PBN? ({ctx})",
            default=default_act,
        ):
            self._step_post_statements(pbn_client, publication)
        else:
            self._info("Pominięto POST oświadczeń (decyzja użytkownika).")
            self.stats.append(("POST oświadczeń", "pominięty"))

    # ------------------------- kroki -------------------------

    def _step_show_publication(self, publication):
        self._header("KROK 1/8 — Wybrana publikacja")

        # Cache ostatniej synchronizacji z PBN (może być nieaktualny).
        cache = (
            OswiadczenieInstytucji.objects.filter(
                publicationId_id=publication.pbn_uid_id
            ).count()
            if publication.pbn_uid_id
            else 0
        )
        # Intencja BPP — live count tego co by adapter wysłał teraz.
        try:
            intended_count = len(
                WydawnictwoPBNAdapter(
                    publication, uczelnia=self._resolved_uczelnia
                ).pbn_get_json_statements()
            )
            intended_label = str(intended_count)
        except Exception as e:  # noqa: BLE001
            intended_label = f"?? (błąd adaptera: {e})"

        self._info(f"Typ:          {type(publication).__name__}")
        self._info(f"PK:           {publication.pk}")
        self._info(f"Tytuł:        {publication.tytul_oryginalny[:100]}")
        self._info(f"Rok:          {publication.rok}")
        self._info(f"PBN UID:      {publication.pbn_uid_id or '(brak)'}")
        self._info(f"Oświadczenia w cache (OswiadczenieInstytucji): {cache}")
        self._info(f"Oświadczenia intencji BPP (live, adapter):     {intended_label}")
        self._prompt_enter()

    def _step_generate_json(self, publication):
        self._header("KROK 2/8 — Generowanie JSON publikacji")
        adapter = WydawnictwoPBNAdapter(publication, uczelnia=self._resolved_uczelnia)
        js = adapter.pbn_get_json()
        bez_oswiadczen = "statements" not in js
        n_statements = len(js.get("statements", [])) if not bez_oswiadczen else 0
        self._info(f"Adapter:      WydawnictwoPBNAdapter({publication!r})")
        self._info(
            f"JSON:         {'BEZ oświadczeń' if bez_oswiadczen else 'Z oświadczeniami'}"
            f" (klucz 'statements' {'NIE' if bez_oswiadczen else 'JEST'} w JSON)"
        )
        if not bez_oswiadczen:
            self._info(f"Oświadczeń w JSON: {n_statements}")
        self._info("Preview JSON:")
        self.stdout.write(_json_truncated(js, max_len=600))
        if self._prompt_yes_no("Pokazać pełny JSON?", default=False):
            self.stdout.write(json.dumps(js, indent=2, ensure_ascii=False, default=str))
        self._prompt_enter()
        return js, bez_oswiadczen

    def _step_choose_endpoint(self, bez_oswiadczen):
        self._header("KROK 3/8 — Wybór endpointa wysyłki publikacji")
        self._info(
            f"Opcja [1]: POST {PBN_POST_PUBLICATIONS_URL} (all-in-one, JSON bez zmian)"
        )
        self._info(
            f"Opcja [2]: POST {PBN_POST_PUBLICATION_NO_STATEMENTS_URL} "
            f"(wymusza JSON bez oświadczeń — convert_json_with_statements_to_no_statements)"
        )
        prod_endpoint = (
            "[2] /v1/repositorium/publications"
            if bez_oswiadczen
            else "[1] /v1/publications"
        )
        self._info(f"Produkcja wybrałaby: {prod_endpoint}")
        if not bez_oswiadczen:
            self._warn(
                "UWAGA: JSON zawiera klucz 'statements'. Opcja [2] wyrzuci go "
                "z JSON przez convert_json_with_statements_to_no_statements. "
                "PBN w obu przypadkach zaakceptuje dokument zgodny ze spec."
            )
        while True:
            choice = self._prompt("Wybór [1/2] (q=wyjście): ")
            if choice == "1":
                return "publications"
            if choice == "2":
                return "repositorium"
            if choice.lower() in ("q", "quit", "exit"):
                raise UserAbort()
            self._err("Nieprawidłowa opcja. Wpisz 1, 2 lub q.")

    def _step_post_publication(self, pbn_client, publication, js, endpoint_choice):
        self._header("KROK 4/8 — POST publikacji do PBN")

        if endpoint_choice == "publications":
            url = PBN_POST_PUBLICATIONS_URL
            body = js
            label = "post_publication (all-in-one)"
        else:
            url = PBN_POST_PUBLICATION_NO_STATEMENTS_URL
            # `convert_json_with_statements_to_no_statements` usuwa klucz
            # `statements` (endpoint repo go nie przyjmuje) oraz konwertuje
            # pola (givenNames→firstName, abstracts do roota itd.). `dict(js)`
            # — bo `js` jest współdzielone z gałęzią `publications`, mutowanie
            # in-place złamałoby pozostałe kroki flow.
            body_js = pbn_client.convert_json_with_statements_to_no_statements(dict(js))
            body = [body_js]
            label = "post_publication_no_statements (repozytorium)"

        self._print_http_request("POST", url, body, label=label)

        if self.dry_run:
            self._info("[dry-run] Pomijam wysyłkę. Zwracam sztuczny objectId='DRY'.")
            self.stats.append(("POST publikacji", "dry-run (pominięty)"))
            self._prompt_enter()
            return "DRY"

        if not self._prompt_yes_no("Wyślij teraz?", default=True):
            self._info("Pominięto POST publikacji (decyzja użytkownika).")
            self.stats.append(("POST publikacji", "pominięty"))
            return None

        try:
            response = pbn_client.transport.post(url, body=body)
        except HttpException as e:
            self._print_http_error(e)
            self.stats.append(("POST publikacji", f"BŁĄD HTTP {e.status_code}"))
            if self._prompt_yes_no(
                "Wysyłka nie powiodła się. Kontynuować flow?", default=False
            ):
                return None
            raise UserAbort() from e
        except (
            AccessDeniedException,
            NeedsPBNAuthorisationException,
            ResourceLockedException,
            PraceSerwisoweException,
        ) as e:
            self._err(f"{type(e).__name__}: {e}")
            self.stats.append(("POST publikacji", f"BŁĄD {type(e).__name__}"))
            raise UserAbort() from e

        self._print_http_response(response)

        object_id = self._extract_object_id(response, endpoint_choice)
        self._info(f"Wyciągnięty objectId = {object_id!r}")
        self.stats.append(("POST publikacji", f"OK, objectId={object_id}"))
        self._prompt_enter()
        return object_id

    def _step_get_pbn_statements(self, pbn_client, object_id):
        self._header("KROK 5/8 — Pobranie aktualnych oświadczeń z PBN")
        object_id_str = str(object_id)
        url = PBN_GET_INSTITUTION_STATEMENTS + f"?publicationId={object_id_str}"
        self._print_http_request(
            "GET", url, body=None, label="get_institution_statements"
        )

        if self.dry_run or object_id == "DRY":
            self._info("[dry-run] Pomijam GET. Zwracam pustą listę.")
            self.stats.append(("GET oświadczeń PBN", "dry-run"))
            self._prompt_enter()
            return []

        try:
            result = list(
                pbn_client.get_institution_statements_of_single_publication(
                    object_id_str, page_size=5120
                )
            )
        except HttpException as e:
            self._print_http_error(e)
            self.stats.append(("GET oświadczeń PBN", f"BŁĄD HTTP {e.status_code}"))
            raise UserAbort() from e

        self._info(f"PBN zwrócił oświadczeń: {len(result)}")
        self.stdout.write(_json_truncated(result, max_len=600))
        self.stats.append(("GET oświadczeń PBN", f"OK, {len(result)} oświadczeń"))
        self._prompt_enter()
        return result

    def _step_compare_statements(self, publication, pbn_statements):
        self._header("KROK 6/8 — Porównanie: intencja BPP (live) vs PBN")

        # Intencja BPP: co wygenerowałby adapter GDYBY teraz wysłać — czyli
        # aktualny stan autorów/dyscyplin w rekordzie. NIE używamy cache'a
        # ``OswiadczenieInstytucji`` (to snapshot *PBN* z poprzedniego
        # pobrania, nie BPP); po edycji w rekordzie — skasowaniu autora,
        # dyscypliny, wypięciu — cache pozostałby nieaktualny.
        #
        # Używamy ``pbn_get_json_statements()`` (surowa lista dict-ów
        # przed konwersją w ``pbn_get_api_statements``, która usuwa
        # ``disciplineId`` gdy jest ``disciplineUuid``). Surowy format
        # zachowuje ``disciplineId`` (numerek MNiSW) i ``personObjectId``
        # — oba nam potrzebne do porównania z PBN GET response, gdzie są
        # ``area`` i ``personId``.
        try:
            intended = WydawnictwoPBNAdapter(
                publication, uczelnia=self._resolved_uczelnia
            ).pbn_get_json_statements()
        except Exception as e:  # noqa: BLE001
            self._warn(f"Nie mogę wygenerować intencji BPP (adapter): {e}")
            self._info("Zwracam 'różnice' — user zdecyduje co robić.")
            self.stats.append(("Porównanie", "nieznane (błąd adaptera)"))
            self._prompt_enter()
            return False  # traktujemy jak "różne"

        def _key(stmt):
            """Klucz porównania: (person-mongoId, disciplineNumer).

            Mapowanie między formatami:
            - PBN GET response (``/page/statements``): ``personId`` (mongoId),
              ``area`` (string, numerek dyscypliny MNiSW np. "301").
            - Adapter ``pbn_get_json_statements()`` (przed konwersją):
              ``personObjectId`` (mongoId), ``disciplineId`` (int, numerek
              dyscypliny MNiSW).
            Oba oznaczają to samo.
            """
            if not isinstance(stmt, dict):
                return (None, None)
            person = stmt.get("personId") or stmt.get("personObjectId")
            discipline = stmt.get("area")
            if discipline is None:
                discipline = stmt.get("disciplineId")
            return (
                str(person) if person else None,
                str(discipline) if discipline is not None else "",
            )

        intended_keys = {_key(x) for x in intended}
        pbn_keys = {_key(x) for x in pbn_statements}

        only_intended = intended_keys - pbn_keys
        only_pbn = pbn_keys - intended_keys
        common = intended_keys & pbn_keys

        self._info(f"Intencja BPP (live):          {len(intended_keys)}")
        self._info(f"Aktualnie w PBN:              {len(pbn_keys)}")
        self._info(f"Identycznych:                 {len(common)}")
        self._info(f"Tylko w intencji (do dodania): {len(only_intended)}")
        self._info(f"Tylko w PBN (do usunięcia):    {len(only_pbn)}")

        if only_intended:
            self._info(f"  → intencja bez PBN: {list(only_intended)[:5]}")
        if only_pbn:
            self._info(f"  → w PBN bez intencji: {list(only_pbn)[:5]}")

        identyczne = not only_intended and not only_pbn
        self.stats.append(
            (
                "Porównanie",
                "identyczne" if identyczne else "różnice",
            )
        )
        self._prompt_enter()
        return identyczne

    def _step_delete_statements(self, pbn_client, object_id):
        self._header("KROK 7/8 — DELETE oświadczeń w PBN")
        url = PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=object_id)
        body = {"all": True, "statementsOfPersons": []}
        self._print_http_request(
            "DELETE", url, body, label="delete_all_publication_statements"
        )

        if self.dry_run or object_id == "DRY":
            self._info("[dry-run] Pomijam DELETE.")
            self.stats.append(("DELETE oświadczeń", "dry-run"))
            self._prompt_enter()
            return

        # Uwaga: zewnętrzny _prompt_yes_no w _run_flow już zapytał czy
        # w ogóle robić DELETE — jeśli tu jesteśmy, user się zgodził.
        # Nie dodajemy drugiego pytania "Wyślij DELETE?" dla prostoty.

        try:
            response = pbn_client.delete_all_publication_statements(object_id)
        except HttpException as e:
            self._print_http_error(e)
            self.stats.append(("DELETE oświadczeń", f"BŁĄD HTTP {e.status_code}"))
            raise UserAbort() from e
        except ResourceLockedException as e:
            self._err(f"ResourceLocked: {e}")
            self.stats.append(("DELETE oświadczeń", "Locked"))
            raise UserAbort() from e

        self._print_http_response(response)
        self.stats.append(("DELETE oświadczeń", "OK"))
        self._prompt_enter()

    def _step_post_statements(self, pbn_client, publication):
        self._header("KROK 8/8 — POST nowych oświadczeń")
        try:
            payload = WydawnictwoPBNAdapter(
                publication, uczelnia=self._resolved_uczelnia
            ).pbn_get_api_statements()
        except DaneLokalneWymagajaAktualizacjiException as e:
            self._err(
                f"Nie mogę przygotować payloadu oświadczeń: {e}. "
                "Prawdopodobnie brak lokalnie PublikacjaInstytucji_V2 dla tego PBN UID."
            )
            self.stats.append(("POST oświadczeń", f"błąd adaptera: {e}"))
            return

        body = {"data": [payload]}
        self._print_http_request(
            "POST",
            PBN_POST_INSTITUTION_STATEMENTS_URL,
            body,
            label="post_discipline_statements",
        )

        if self.dry_run:
            self._info("[dry-run] Pomijam POST oświadczeń.")
            self.stats.append(("POST oświadczeń", "dry-run"))
            self._prompt_enter()
            return

        # Zewnętrzny _prompt_yes_no w _run_flow już zapytał czy w ogóle
        # robić POST — jeśli tu jesteśmy, user się zgodził. Pomijamy
        # drugie pytanie "Wyślij POST?" dla prostoty.

        max_tries = 3
        attempt = 0
        while True:
            attempt += 1
            try:
                response = pbn_client.post_discipline_statements(body)
                break
            except HttpException as e:
                self._print_http_error(e)
                if e.status_code in (500, 423) and attempt < max_tries:
                    wait = 2**attempt
                    self._warn(f"Retry za {wait}s (próba {attempt}/{max_tries})...")
                    time.sleep(wait)
                    continue
                self.stats.append(
                    ("POST oświadczeń", f"BŁĄD HTTP {e.status_code} (prób: {attempt})")
                )
                raise UserAbort() from e

        self._print_http_response(response)
        self.stats.append(("POST oświadczeń", f"OK (prób: {attempt})"))
        self._prompt_enter()

    # ------------------------- helpers -------------------------

    def _extract_object_id(self, response, endpoint_choice):
        if endpoint_choice == "publications":
            if isinstance(response, dict):
                return response.get("objectId")
            return None
        if isinstance(response, list) and len(response) == 1:
            item = response[0]
            if isinstance(item, dict):
                return item.get("id") or item.get("objectId")
        return None

    def _print_http_request(self, method, url, body, label=""):
        self._info(f"Wywołanie: {label}" if label else "Żądanie HTTP:")
        self.stdout.write(self.style.HTTP_INFO(f"  {method} {url}"))
        if body is not None:
            self.stdout.write("  body:")
            self.stdout.write(_json_truncated(body, max_len=800))

    def _print_http_response(self, response):
        self.stdout.write(self.style.SUCCESS("  Odpowiedź:"))
        self.stdout.write(_json_truncated(response, max_len=800))

    def _print_http_error(self, exc: HttpException):
        self._err(f"HTTP {exc.status_code} przy {exc.url}")
        self.stdout.write(f"  content: {(exc.content or '')[:500]}")

    def _header(self, text):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"=== {text} ==="))

    def _info(self, text):
        self.stdout.write(text)

    def _warn(self, text):
        self.stdout.write(self.style.WARNING(text))

    def _err(self, text):
        self.stdout.write(self.style.ERROR(text))

    def _prompt(self, msg):
        # Ogólny prompt (np. wybór 1/2/q) — nigdy nie uwzględnia yes_all.
        # yes_all wpływa tylko na proste pytania "[Enter] kontynuuj" oraz
        # yes/no z wartością domyślną (patrz: _prompt_enter, _prompt_yes_no).
        return input(msg)

    def _prompt_enter(self):
        if self.yes_all:
            return
        ans = input("[Enter] kontynuuj / [q] wyjście: ")
        if ans.strip().lower() in ("q", "quit", "exit"):
            raise UserAbort()

    def _prompt_yes_no(self, msg, default=True):
        if self.yes_all:
            return default
        hint = "[T/n]" if default else "[t/N]"
        ans = input(f"{msg} {hint}: ").strip().lower()
        if not ans:
            return default
        if ans in ("q", "quit", "exit"):
            raise UserAbort()
        return ans in ("t", "tak", "y", "yes")

    def _print_summary(self):
        self._header("PODSUMOWANIE")
        if not self.stats:
            self._info("Brak wykonanych operacji.")
            return
        for name, status in self.stats:
            self.stdout.write(f"  {name:30s} → {status}")
