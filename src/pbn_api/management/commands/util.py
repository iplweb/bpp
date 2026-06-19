import warnings

from django.core.management import BaseCommand, CommandError

from bpp.models import BppUser, Uczelnia
from pbn_api.client import BppPBNClient, RequestsTransport
from pbn_client.conf import settings


class PBNBaseCommand(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--uczelnia-id",
            type=int,
            default=None,
            help=(
                "ID uczelni. Wymagane gdy w systemie jest więcej niż jedna "
                "uczelnia; przy dokładnie jednej uczelni jest ona używana "
                "automatycznie."
            ),
        )
        # Domyślne wartości celowo None — credentiale rozwiązujemy dopiero
        # w execute() (po sparsowaniu --uczelnia-id), a nie na etapie
        # budowania parsera. Dzięki temu --uczelnia-id realnie wpływa na
        # wybór konfiguracji PBN (wcześniej flaga była martwa).
        parser.add_argument("--app-id", default=None)
        parser.add_argument("--app-token", default=None)
        parser.add_argument("--base-url", default=None)
        parser.add_argument("--user-token", default=None)

    def execute(self, *args, **options):
        # Uczelnię i credentiale PBN rozwiązujemy LENIWIE — dopiero w
        # get_client() (gdy komenda realnie buduje klienta PBN), a nie tutaj,
        # dla każdego uruchomienia. Dzięki temu komendy dziedziczące
        # PBNBaseCommand, które PBN-a w ogóle nie używają (np. ustawianie
        # punktów po imporcie czy przypisywanie rekordów do jednostek), NIE
        # wymagają --uczelnia-id i nie wywalają się przy >1 uczelni. Komendy
        # PBN-owe nadal dostają twardy CommandError — ale w get_client().
        self._pbn_uczelnia_id = options.get("uczelnia_id")
        # Inwariant: atrybut istnieje już po execute() (komendy czytają go
        # wprost, np. WydawnictwoPBNAdapter(uczelnia=self._resolved_uczelnia)).
        # Leniwe get_client() nadpisze go realną uczelnią, gdy zbuduje klienta.
        self._resolved_uczelnia = None
        return super().execute(*args, **options)

    def _resolve_uczelnia(self, uczelnia_id):
        """Uczelnia dla komendy CLI.

        - ``--uczelnia-id`` zawsze honorowane (i walidowane),
        - przy dokładnie jednej uczelni używamy jej (get_default() jest OK
          TYLKO w tym jednym przypadku),
        - przy wielu uczelniach brak ``--uczelnia-id`` to ``CommandError`` —
          bez cichego wyboru pierwszej-z-brzegu.
        """
        if uczelnia_id is not None:
            try:
                return Uczelnia.objects.get(pk=uczelnia_id)
            except Uczelnia.DoesNotExist as e:
                raise CommandError(f"Brak uczelni o id={uczelnia_id}.") from e

        count = Uczelnia.objects.count()
        if count == 0:
            return None
        if count == 1:
            return Uczelnia.objects.get()
        raise CommandError(
            "W systemie jest więcej niż jedna uczelnia — podaj --uczelnia-id, "
            "żeby wskazać której konfiguracji PBN użyć."
        )

    def _fill_pbn_credentials(self, options):
        """Uzupełnij app_id/app_token/base_url/user_token w ``options``.

        Wartości jawnie podane na CLI mają priorytet; resztę bierzemy z
        konfiguracji wskazanej uczelni, a w ostateczności z ``settings``.
        """
        uczelnia = self._resolve_uczelnia(options.get("uczelnia_id"))
        # Zapamiętujemy rozwiązaną uczelnię, żeby get_client zbudował
        # BppPBNClient świadomy uczelni (orchestracja czyta z niej flagi).
        self._resolved_uczelnia = uczelnia

        if options.get("app_id") is None:
            options["app_id"] = (
                uczelnia.pbn_app_name
                if uczelnia and uczelnia.pbn_app_name
                else settings.PBN_CLIENT_APP_ID
            )
        if options.get("app_token") is None:
            options["app_token"] = (
                uczelnia.pbn_app_token
                if uczelnia and uczelnia.pbn_app_token
                else settings.PBN_CLIENT_APP_TOKEN
            )
        if options.get("base_url") is None:
            options["base_url"] = (
                uczelnia.pbn_api_root
                if uczelnia and uczelnia.pbn_api_root
                else settings.PBN_CLIENT_BASE_URL
            )
        if options.get("user_token") is None:
            if uczelnia is not None and uczelnia.pbn_api_user_id is not None:
                options["user_token"] = uczelnia.pbn_api_user.pbn_token
            else:
                user = BppUser.objects.first()
                options["user_token"] = user.pbn_token if user is not None else None

    def get_client(
        self, app_id=None, app_token=None, base_url=None, user_token=None, verbose=False
    ):
        # Tu rozwiązujemy uczelnię i uzupełniamy credentiale (leniwie). To
        # jedyne miejsce, w którym PBN jest faktycznie potrzebny — i jedyne,
        # w którym może paść CommandError o >1 uczelni bez --uczelnia-id.
        # Wartości jawnie podane na CLI (app_id itd.) mają priorytet; resztę
        # bierzemy z wybranej uczelni, a w ostateczności z settings.
        options = {
            "uczelnia_id": getattr(self, "_pbn_uczelnia_id", None),
            "app_id": app_id,
            "app_token": app_token,
            "base_url": base_url,
            "user_token": user_token,
        }
        self._fill_pbn_credentials(options)
        app_id = options["app_id"]
        app_token = options["app_token"]
        base_url = options["base_url"]
        user_token = options["user_token"]

        if user_token is None:
            warnings.warn(
                "user_token not set, expect authorisation problems", stacklevel=2
            )

        transport = RequestsTransport(app_id, app_token, base_url, user_token)
        if verbose:
            print("App ID\t\t", app_id)
            print("App token\t", app_token)
            print("Base URL\t", base_url)
            print("User token\t", user_token)
        return BppPBNClient(
            transport, uczelnia=getattr(self, "_resolved_uczelnia", None)
        )
