from pbn_api.management.commands.util import PBNBaseCommand
from pbn_integrator.utils import wyslij_informacje_o_platnosciach


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--rok", type=int)
        parser.add_argument(
            "--upload-publication",
            action="store_true",
            default=False,
            help="Upload publication if it has no PBN UID (default: skip)",
        )

    def handle(
        self,
        app_id,
        app_token,
        base_url,
        user_token,
        rok,
        upload_publication,
        *args,
        **options,
    ):
        client = self.get_client(app_id, app_token, base_url, user_token)
        wyslij_informacje_o_platnosciach(
            client, rok, upload_publication=upload_publication
        )
