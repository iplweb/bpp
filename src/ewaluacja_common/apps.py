from django.apps import AppConfig
from django.db.models.signals import post_migrate


class EwaluacjaCommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ewaluacja_common"

    def ready(self):
        from ewaluacja_common.okres import zasiej_okresy_po_migracji

        post_migrate.connect(
            zasiej_okresy_po_migracji,
            sender=self,
            dispatch_uid="ewaluacja_common.zasiej_okresy_po_migracji",
        )
