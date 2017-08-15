from django.conf import settings


def theme_name(request):
    return {'THEME_NAME': 'scss/' + settings.THEME_NAME + '.css'}


def enable_new_reports(request):
    return {'ENABLE_NEW_REPORTS': settings.ENABLE_NEW_REPORTS}
