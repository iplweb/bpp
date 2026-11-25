"""Jedno polecenie: działający token PBN użytkownika w LOKALNEJ instancji.

Zwykle uruchamiane przez ``bin/pbn-zaloguj-lokalnie.py`` (ustawia połączenie
z bazą działającego ``run-site``). Opis: ``pbn_api/logowanie_lokalne.py``,
``docs/deweloper/testowanie-pbn-lokalnie.md``.
"""

from contextlib import contextmanager
from pathlib import Path

import requests
from django.core.exceptions import ImproperlyConfigured
from django.core.management import BaseCommand, CommandError, call_command
from django.utils import timezone

from bpp.fields import NieodszyfrowanaWartosc
from bpp.models import BppUser
from pbn_api import logowanie_lokalne as ll
from pbn_api.exceptions import AccessDeniedException, HttpException
from pbn_api.management.commands.pbn_ott_na_token import _znajdz_uczelnie

DOMYSLNY_PROFIL = Path.home() / ".cache" / "bpp" / "pbn-profil"


@contextmanager
def _chromium_z_profilem(profil: Path, bez_okna: bool):
    from playwright.sync_api import sync_playwright

    profil.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(profil), headless=bez_okna, no_viewport=True
        )
        try:
            yield context
        finally:
            context.close()


class Command(BaseCommand):
    help = (
        "Loguje użytkownika lokalnej instancji BPP do PBN: otwiera przeglądarkę, "
        "czeka na zalogowanie w PBN, przechwytuje powrót kierowany na serwer "
        "klienta i kończy autoryzację lokalnie. Tokenu nie wypisuje."
    )

    #: Podmieniane w testach (kontekst przeglądarki z pytest-playwright).
    otworz_przegladarke = staticmethod(_chromium_z_profilem)

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            required=False,
            help="Adres lokalnej instancji BPP, np. http://localhost:8000.",
        )
        parser.add_argument("--user", default="admin", help="Login w lokalnym BPP.")
        parser.add_argument("--uczelnia", default=None, help="ID lub skrót uczelni.")
        parser.add_argument(
            "--ott",
            default=None,
            help="Tryb awaryjny bez przeglądarki: wymień podany kod OTT na token.",
        )
        parser.add_argument(
            "--konfiguracja-z",
            default=None,
            metavar="[LOGIN@]HOST",
            help=(
                "Najpierw pobierz po SSH konfigurację aplikacji PBN i token "
                "użytkownika z serwera (pbn_konfiguracja_z_serwera). Gdy "
                "przeniesiony token działa, logowanie w PBN jest pomijane."
            ),
        )
        parser.add_argument(
            "--wymus",
            action="store_true",
            help="Loguj w PBN nawet wtedy, gdy zapisany token już działa.",
        )
        parser.add_argument(
            "--tylko-sprawdz",
            action="store_true",
            help="Nie loguj — sprawdź tylko, czy zapisany token działa.",
        )
        parser.add_argument(
            "--profil",
            default=str(DOMYSLNY_PROFIL),
            help=f"Katalog trwałego profilu przeglądarki (domyślnie {DOMYSLNY_PROFIL}).",
        )
        parser.add_argument(
            "--bez-okna",
            action="store_true",
            help="Przeglądarka bez okna — ma sens tylko, gdy sesja PBN w profilu żyje.",
        )
        parser.add_argument("--limit-czasu", type=int, default=570, metavar="SEKUNDY")

    def handle(self, *args, **o):
        try:
            user = BppUser.objects.get(username=o["user"])
        except BppUser.DoesNotExist as e:
            raise CommandError(
                f"W lokalnej bazie nie ma użytkownika {o['user']!r}."
            ) from e
        uczelnia = _znajdz_uczelnie(o["uczelnia"])

        if o["tylko_sprawdz"]:
            self._podsumuj(user, uczelnia, zapisano_teraz=False)
            return

        # Bezpiecznik PRZED zapisaniem tokenu (zapis rusza ponowienie kolejki).
        # Na instancji nielokalnej odmawia — i na tym kończymy.
        call_command(
            "pbn_bezpiecznik_lokalnej_kopii", potwierdzenie=True, stdout=self.stdout
        )
        if o["konfiguracja_z"]:
            zrodlo = o["konfiguracja_z"]
            if "@" not in zrodlo:
                zrodlo = f"{user.username}@{zrodlo}"
            call_command(
                "pbn_konfiguracja_z_serwera",
                zrodlo,
                user_lokalny=user.username,
                uczelnia=uczelnia.skrot,
                bez_bezpiecznika=True,
                stdout=self.stdout,
            )
            uczelnia.refresh_from_db()
            user.refresh_from_db()
        self._sprawdz_konfiguracje_aplikacji(uczelnia)

        if not o["ott"] and not o["wymus"] and user.pbn_token:
            try:
                self._podsumuj(user, uczelnia, zapisano_teraz=False)
            except CommandError as e:
                self.stdout.write(f"{e} Przechodzę do logowania w PBN.")
            else:
                return

        start = timezone.now()
        if o["ott"]:
            self._wymien_ott(o["ott"], user, uczelnia)
        else:
            self._zaloguj_w_przegladarce(user, uczelnia, o)

        user.refresh_from_db()
        if not user.pbn_token or (user.pbn_token_updated or start) < start:
            raise CommandError(
                "Token PBN NIE został zapisany — lokalny BPP odrzucił "
                "autoryzację. Zajrzyj do logu run-site (komunikat widoku "
                "/pbn_api/callback)."
            )
        self._podsumuj(user, uczelnia, zapisano_teraz=True)

    def _sprawdz_konfiguracje_aplikacji(self, uczelnia):
        if not uczelnia.pbn_app_name:
            raise CommandError(
                f"Uczelnia {uczelnia.skrot} nie ma nazwy aplikacji PBN. "
                + self._jak_pobrac_konfiguracje()
            )
        token = uczelnia.pbn_app_token
        if isinstance(token, NieodszyfrowanaWartosc):
            raise CommandError(
                "Token aplikacji PBN jest w bazie zaszyfrowany INNYM kluczem "
                "(kopia bazy z serwera, lokalny DJANGO_BPP_FIELD_ENCRYPTION_KEY "
                "jest inny), więc nie da się go odczytać. "
                + self._jak_pobrac_konfiguracje()
            )
        if not token:
            raise CommandError(
                f"Uczelnia {uczelnia.skrot} nie ma tokenu aplikacji PBN. "
                + self._jak_pobrac_konfiguracje()
            )

    @staticmethod
    def _jak_pobrac_konfiguracje():
        return (
            "Pobierz konfigurację z serwera: "
            "`uv run bin/pbn-zaloguj-lokalnie.py --konfiguracja-z HOST` "
            "(albo `manage.py pbn_konfiguracja_z_serwera HOST`)."
        )

    def _wymien_ott(self, ott, user, uczelnia):
        call_command(
            "pbn_ott_na_token",
            ott,
            user=user.username,
            uczelnia=str(uczelnia.pk),
            stdout=self.stdout,
        )

    def _zaloguj_w_przegladarce(self, user, uczelnia, o):
        base_url = (o["url"] or "").rstrip("/")
        if not base_url:
            raise CommandError("Podaj --url lokalnej instancji BPP.")
        if not ll.adres_jest_lokalny(base_url):
            raise CommandError(
                f"ODMOWA: {base_url} nie jest adresem lokalnym "
                "(localhost / 127.0.0.1). To narzędzie obsługuje wyłącznie "
                "lokalną instancję."
            )

        ciasteczko = ll.utworz_sesje(user)
        with self.otworz_przegladarke(Path(o["profil"]), o["bez_okna"]) as context:
            wynik = ll.autoryzuj_w_przegladarce(
                context,
                base_url,
                ciasteczko,
                pbn_api_root=uczelnia.pbn_api_root,
                limit_czasu=o["limit_czasu"],
                komunikat=self.stdout.write,
            )
        # Od tego miejsca przeglądarka jest zamknięta — wolno używać ORM.

        if wynik.zatrzymane:
            self.stdout.write(
                "Zatrzymano przed wyjściem z przeglądarki: "
                + ", ".join(f"{m} {u}" for m, u in wynik.zatrzymane)
            )
        if wynik.status == "callback":
            return
        if wynik.status == "ott":
            # PBN wrócił inną drogą niż GET na /pbn_api/callback — kod mamy,
            # wymieniamy go tą samą ścieżką co tryb --ott.
            self.stdout.write(
                "PBN wrócił nietypowo (nie przez /pbn_api/callback) — "
                "wymieniam przechwycony kod OTT bezpośrednio."
            )
            self._wymien_ott(wynik.ott, user, uczelnia)
            return
        komunikaty = {
            "callback_bez_ott": (
                "PBN wrócił na adres callbacku BEZ kodu OTT w adresie ani "
                "w treści żądania — nie umiem go przechwycić. Skorzystaj "
                "z wariantu awaryjnego (--ott <kod>, patrz "
                "docs/deweloper/testowanie-pbn-lokalnie.md)."
            ),
            "niezalogowany": (
                "Lokalny BPP nie przyjął sesji użytkownika "
                f"{user.username} (strona: {wynik.szczegoly}). Sprawdź, czy "
                "--url wskazuje instancję korzystającą z TEJ bazy i czy konto "
                "nie wymaga zmiany hasła."
            ),
            "zamknieto": "Okno przeglądarki zostało zamknięte przed zalogowaniem.",
            "timeout": (
                f"Upłynął limit czasu ({o['limit_czasu']} s) — nie doczekałem "
                "się powrotu z PBN."
            ),
        }
        raise CommandError(komunikaty[wynik.status])

    def _podsumuj(self, user, uczelnia, zapisano_teraz):
        if not user.pbn_token:
            powod = (
                "zaszyfrowany innym kluczem (kopia bazy z serwera)"
                if isinstance(user.pbn_token, NieodszyfrowanaWartosc)
                else "brak"
            )
            raise CommandError(f"Token PBN użytkownika {user.username}: {powod}.")
        try:
            ile = ll.sprawdz_token(uczelnia, user.pbn_token)
        except ImproperlyConfigured as e:
            raise CommandError(f"{e}. {self._jak_pobrac_konfiguracje()}") from e
        except (AccessDeniedException, HttpException) as e:
            kod = getattr(e, "status_code", 403)
            raise CommandError(
                f"Token PBN użytkownika {user.username} jest zapisany, ale PBN "
                f"go ODRZUCA (HTTP {kod} z {uczelnia.pbn_api_root}) — zaloguj "
                "się ponownie."
            ) from e
        except requests.RequestException as e:
            raise CommandError(
                f"Token PBN użytkownika {user.username} jest zapisany, ale nie "
                f"udało się połączyć z PBN ({uczelnia.pbn_api_root}): "
                f"{type(e).__name__}."
            ) from e
        self.stdout.write(
            self.style.SUCCESS(
                f"OK: token PBN użytkownika {user.username} "
                f"{'zapisany i ' if zapisano_teraz else ''}działa — "
                f"{uczelnia.pbn_api_root} odpowiada (liczba publikacji "
                f"w profilu instytucji: {ile})."
            )
        )
