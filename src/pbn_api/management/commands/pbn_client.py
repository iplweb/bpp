# -*- encoding: utf-8 -*-


from pbn_api.management.commands.util import PBNBaseCommand


class Command(PBNBaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument("command", nargs="+")

    def handle(
        self, app_id, app_token, base_url, user_token, command=None, *args, **options
    ):
        client = self.get_client(app_id, app_token, base_url, user_token)
        client.exec(command)
