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


def _is_release():
    return os.environ.get("BPP_BUILD_FLAVOR", "dev") == "release"


@register.simple_tag
def bpp_git_sha_short():
    """Krótki (7-znakowy) git SHA dla obrazów dev (PR/feature/lokalne).

    Master release zwraca pusty string (BPP_BUILD_FLAVOR=release ustawione
    przez workflow build-docker-images.yml). Wartości brane są z env, które
    `docker/bpp_base/Dockerfile` (runtime stage) zapisuje do obrazu.

    Pusty wynik = nic nie pokazujemy w stopce.
    """
    if _is_release():
        return ""
    sha = os.environ.get("BPP_GIT_SHA", "")
    if not sha or sha == "unknown":
        return ""
    return sha[:7]


@register.simple_tag
def bpp_image_tag():
    """Tag obrazu Docker (np. "119-merge") dla obrazów dev.

    Master release zwraca pusty string. Wartość ustawia workflow
    build-docker-images.yml na podstawie `final_tag` (PR# dla pull_request,
    nazwa brancha dla feature/fix/hotfix, BASE_VERSION dla mastera).
    """
    if _is_release():
        return ""
    tag = os.environ.get("BPP_IMAGE_TAG", "")
    if not tag or tag == "unknown":
        return ""
    return tag
