from celery.utils.log import get_task_logger

from ai_search import schema_export
from django_bpp.celery_tasks import app

logger = get_task_logger(__name__)


@app.task(ignore_result=True)
def regenerate_schemas():
    """Odśwież cache'owany, zwarty opis schematu (dla LLM) dla „rekord"
    i „autor". Uruchamiane raz/dobę przez CELERYBEAT_SCHEDULE — schemat
    zawiera suggest_options wyciągane z bazy (np. wartości słownikowe),
    więc bez regeneracji cache trzymałby stare dane aż do wygaśnięcia TTL
    (``BPP_AI_SCHEMA_CACHE_TTL``)."""
    for key in ("rekord", "autor"):
        schema_export.regenerate(key)
        logger.info("ai_search: zregenerowano schemat dla %r", key)
