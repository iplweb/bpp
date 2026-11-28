"""Panel admina: podgląd operacji generowania danych demo z kreatora.

Read-only ``LiveOperationAdmin`` z liveops (stan, traceback, wynik) — tu
administrator znajdzie szczegóły błędu generowania.
"""

from django.contrib import admin
from liveops.admin import LiveOperationAdmin

from bpp_setup_wizard.models import GenerowanieDanychDemo


@admin.register(GenerowanieDanychDemo)
class GenerowanieDanychDemoAdmin(LiveOperationAdmin):
    pass
