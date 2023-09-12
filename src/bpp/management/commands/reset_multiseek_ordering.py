from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import BppMultiseekVisibility
from bpp.multiseek_registry import registry


class Command(BaseCommand):
    help = "Resetuje sortowanie opcji w wyszukiwarce zgodnie z kodem"

    @transaction.atomic
    def handle(self, *args, **options):
        # Tu użyjemy registry.fields, gdyż registry.get_fields() zwraca pola w kolejności takiej,
        # jak w bazie danych. registry.fields zawiera pola tak, jak zostały zadeklarowane w kodzie.
        for no, elem in enumerate(registry.fields, 1):
            try:
                field_name = elem.bpp_multiseek_visibility_field_name
            except AttributeError:
                field_name = elem.field_name

            try:
                i = BppMultiseekVisibility.objects.get(field_name=field_name)
            except BppMultiseekVisibility.DoesNotExist:
                continue

            if i.sort_order != no:
                i.sort_order = no
                i.save()
