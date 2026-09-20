"""Przetwarzanie zdjęcia autora.

Wejściowy plik (dowolny format obsługiwany przez Pillow, do 5 MB) jest
korygowany wg orientacji EXIF, przycinany centralnie do kwadratu, skalowany do
``ROZMIAR_ZDJECIA_AUTORA`` i zapisywany jako WebP. Walidacja rozmiaru pliku
i typu MIME należy do formularza; tutaj walidujemy tylko, że da się to w ogóle
otworzyć jako obraz.
"""

import io
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

ROZMIAR_ZDJECIA_AUTORA = 400
MAKS_ROZMIAR_PLIKU_ZDJECIA = 5 * 1024 * 1024  # 5 MB
JAKOSC_WEBP = 85


def przetworz_zdjecie_autora(plik, nazwa=None, rozmiar=ROZMIAR_ZDJECIA_AUTORA):
    """Zwróć ``ContentFile`` z kwadratowym zdjęciem WebP gotowym do zapisu.

    :raises ValidationError: gdy pliku nie da się odczytać jako obrazu.
    """
    try:
        obraz = Image.open(plik)
        obraz.load()
    except (UnidentifiedImageError, OSError) as e:
        raise ValidationError(
            "Nie udało się odczytać przesłanego pliku jako obrazu."
        ) from e

    # Korekta orientacji wg EXIF (zdjęcia z telefonów bywają obrócone), a potem
    # spłaszczenie do RGB (WebP zapisujemy bez kanału alfa) i przycięcie+skala
    # do kwadratu jednym przejściem (ImageOps.fit centruje kadr).
    obraz = ImageOps.exif_transpose(obraz)
    obraz = obraz.convert("RGB")
    obraz = ImageOps.fit(
        obraz, (rozmiar, rozmiar), method=Image.LANCZOS, centering=(0.5, 0.5)
    )

    bufor = io.BytesIO()
    obraz.save(bufor, format="WEBP", quality=JAKOSC_WEBP)

    rdzen_nazwy = Path(nazwa).stem if nazwa else "zdjecie"
    return ContentFile(bufor.getvalue(), name=f"{rdzen_nazwy}.webp")
