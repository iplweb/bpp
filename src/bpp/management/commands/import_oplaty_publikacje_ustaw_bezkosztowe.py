from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import OplatyPublikacjiLog, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from bpp.util import pbar


class Command(BaseCommand):
    help = (
        "Set opl_pub_cost_free=True for publications with PBN UID but without fee data"
    )

    def add_arguments(self, parser):
        parser.add_argument("--rok", type=int, required=True)
        parser.add_argument(
            "--dry-run",
            "--dry",
            dest="dry",
            action="store_true",
            default=False,
            help="Run without saving changes",
        )

    @transaction.atomic
    def handle(self, rok, dry, *args, **options):
        total_count = 0

        for model in [Wydawnictwo_Ciagle, Wydawnictwo_Zwarte]:
            ct = ContentType.objects.get_for_model(model)
            queryset = model.objects.filter(
                rok=rok,
                pbn_uid__isnull=False,
                opl_pub_cost_free__isnull=True,
            )

            # Collect publications and log entries for bulk operations
            pubs_to_update = []
            logs_to_create = []

            for pub in pbar(queryset):
                logs_to_create.append(
                    OplatyPublikacjiLog(
                        content_type=ct,
                        object_id=pub.pk,
                        changed_by="import_oplaty_publikacje_ustaw_bezkosztowe",
                        prev_opl_pub_cost_free=pub.opl_pub_cost_free,
                        prev_opl_pub_research_potential=pub.opl_pub_research_potential,
                        prev_opl_pub_research_or_development_projects=pub.opl_pub_research_or_development_projects,
                        prev_opl_pub_other=pub.opl_pub_other,
                        prev_opl_pub_amount=pub.opl_pub_amount,
                        rok=pub.rok,
                        new_opl_pub_cost_free=True,
                    )
                )
                pub.opl_pub_cost_free = True
                pubs_to_update.append(pub)

            # Bulk operations
            if pubs_to_update:
                model.objects.bulk_update(pubs_to_update, ["opl_pub_cost_free"])
                OplatyPublikacjiLog.objects.bulk_create(logs_to_create)

            total_count += len(pubs_to_update)

        print(f"Updated {total_count} publications")
        if dry:
            transaction.set_rollback(True)
            print("DRY RUN - changes rolled back")
