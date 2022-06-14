import json

from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.management.commands.util import PBNBaseCommand

from django.contrib.contenttypes.models import ContentType


class Command(PBNBaseCommand):
    help = "pokaż kod JSON wygenerowany dla publikacji"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("model_name")
        parser.add_argument("id", type=int)

    def handle(self, model_name, id, *args, **kw):
        obj = ContentType.objects.get(
            app_label="bpp", model=model_name
        ).get_object_for_this_type(id=id)
        adapted = WydawnictwoPBNAdapter(obj)
        data = adapted.pbn_get_json()
        print(json.dumps(data, indent=4, sort_keys=True))
