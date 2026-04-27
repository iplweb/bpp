import os
import time

from django import template

from django_bpp.version import VERSION

register = template.Library()


@register.simple_tag
def bpp_version():
    return VERSION


@register.simple_tag
def bpp_localtime():
    return time.ctime()


@register.simple_tag
def bpp_git_sha_short():
    """Krótki (7-znakowy) git SHA dla obrazów dev (PR/feature/lokalne).

    Master release zwraca pusty string (BPP_BUILD_FLAVOR=release ustawione
    przez workflow build-docker-images.yml). Wartości brane są z env, które
    `docker/bpp_base/Dockerfile` (runtime stage) zapisuje do obrazu.

    Pusty wynik = nic nie pokazujemy w stopce.
    """
    if os.environ.get("BPP_BUILD_FLAVOR", "dev") == "release":
        return ""
    sha = os.environ.get("BPP_GIT_SHA", "")
    if not sha or sha == "unknown":
        return ""
    return sha[:7]
