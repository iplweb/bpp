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
        parser.add_argument(
            "--ignore-wydawnictwa-ciagle",
            action="store_true",
            default=False,
            help="Skip Wydawnictwo_Ciagle publications",
        )
        parser.add_argument(
            "--ignore-wydawnictwa-zwarte",
            action="store_true",
            default=False,
            help="Skip Wydawnictwo_Zwarte publications",
        )

    def handle(
        self,
        app_id,
        app_token,
        base_url,
        user_token,
        rok,
        upload_publication,
        ignore_wydawnictwa_ciagle,
        ignore_wydawnictwa_zwarte,
        *args,
        **options,
    ):
        client = self.get_client(app_id, app_token, base_url, user_token)
        wyslij_informacje_o_platnosciach(
            client,
            rok,
            upload_publication=upload_publication,
            ignore_ciagle=ignore_wydawnictwa_ciagle,
            ignore_zwarte=ignore_wydawnictwa_zwarte,
        )
