"""django-favicon-plus-reloaded działa z Pillow, którego sam nie dopuszcza.

Paczka (1.2.4) deklaruje ``pillow<13``, a my wymuszamy Pillow 13 przez
``[tool.uv] override-dependencies`` (CVE). Ten test pilnuje, że jedyne, czego
favicon używa z Pillow — ``Image.open`` / ``thumbnail(LANCZOS)`` /
``save(PNG)`` w ``FaviconImg.generate_image`` — nadal działa.
"""

from io import BytesIO

import pytest
from django.contrib.sites.models import Site
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from favicon.models import Favicon, FaviconImg


def _png(rozmiar):
    buf = BytesIO()
    Image.new("RGB", (rozmiar, rozmiar), "red").save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.django_db
def test_favicon_generuje_przeskalowane_ikony():
    favicon = Favicon.objects.create(
        title="pillow",
        site=Site.objects.get_current(),
        faviconImage=SimpleUploadedFile(
            "pillow.png", _png(256), content_type="image/png"
        ),
    )

    ikony = list(FaviconImg.objects.filter(faviconFK=favicon))
    assert ikony, "save() powinno wygenerować FaviconImg dla rozmiarów z configu"
    for ikona in ikony:
        with ikona.faviconImage.open() as plik, Image.open(plik) as obraz:
            assert obraz.format == "PNG"
            assert obraz.size == (ikona.size, ikona.size)
