"""Ładowanie ŹRÓDŁA szablonu z dysku z pominięciem loadera dbtemplates.

``get_template`` z Django idzie łańcuchem loaderów, w którym dbtemplates stoi
pierwszy — więc dla nazwy istniejącej w bazie zwraca treść z DB, nie z dysku.
Ten helper konstruuje własny ``Engine`` wyłącznie z loaderami dyskowymi, żeby
odpowiedzieć na pytanie „co jest NA DYSKU pod tą nazwą"."""

from django.conf import settings
from django.template import Engine, TemplateDoesNotExist

_disk_engine = None


def _get_disk_engine():
    global _disk_engine
    if _disk_engine is None:
        dirs = []
        for cfg in settings.TEMPLATES:
            if cfg.get("BACKEND", "").endswith("DjangoTemplates"):
                dirs = list(cfg.get("DIRS", []))
                break
        # Jawne loadery dyskowe (bez cached, bez dbtemplates) — świeży odczyt
        # z dysku przy każdym wywołaniu. NIE 'loaders=[...] + app_dirs=True'
        # (ImproperlyConfigured w Dj5.2).
        # libraries/builtins skopiowane z domyślnego Engine — inaczej surowy
        # Engine nie zna custom tag-libów ({% load prace %} w opisie), bo tylko
        # backend DjangoTemplates auto-odkrywa je z INSTALLED_APPS.
        default = Engine.get_default()
        _disk_engine = Engine(
            dirs=dirs,
            loaders=[
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            libraries=default.libraries,
            builtins=default.builtins,
        )
    return _disk_engine


def disk_template_source(name):
    try:
        template = _get_disk_engine().get_template(name)
    except TemplateDoesNotExist:
        return None
    return template.source
