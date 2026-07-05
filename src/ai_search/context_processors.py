from django.conf import settings


def ai_search_flags(request):
    return {"BPP_AI_SEARCH_ENABLED": settings.BPP_AI_SEARCH_ENABLED}
