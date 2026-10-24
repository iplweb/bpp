"""Walidacja plików graficznych wgrywanych do ``Uczelnia`` (logo SVG, favicon).

Pliki te są zapisywane w publicznym ``MEDIA_ROOT`` i serwowane bezpośrednio,
więc przyjmujemy wyłącznie obrazy o oczekiwanym formacie. Plik SVG jest
odrzucany, jeżeli zawiera elementy lub atrybuty aktywne (skrypty, obsługę
zdarzeń, obce dokumenty, adresy z niedozwolonym schematem).
"""

import os

from django.core.exceptions import ValidationError
from lxml import etree
from PIL import Image, UnidentifiedImageError

from bpp.util.bezpieczny_url import czy_bezpieczny_link, jawny_schemat, normalizuj_url

MAKS_ROZMIAR_SVG = 2 * 1024 * 1024
MAKS_ROZMIAR_FAVICON = 1024 * 1024

ROZSZERZENIA_FAVICON = (".ico", ".png")
FORMATY_FAVICON = ("ICO", "PNG")

ZABRONIONE_ELEMENTY_SVG = frozenset(
    {
        "script",
        "foreignobject",
        "iframe",
        "embed",
        "object",
        "handler",
        "listener",
    }
)
ELEMENTY_ANIMACJI_SVG = frozenset(
    {"set", "animate", "animatemotion", "animatetransform", "animatecolor"}
)


def _odczytaj(plik, maks_rozmiar, etykieta):
    if plik.size is not None and plik.size > maks_rozmiar:
        raise ValidationError(f"Plik {etykieta} jest zbyt duży.")
    plik.seek(0)
    dane = plik.read(maks_rozmiar + 1)
    plik.seek(0)
    if len(dane) > maks_rozmiar:
        raise ValidationError(f"Plik {etykieta} jest zbyt duży.")
    return dane


def _localname(nazwa):
    return etree.QName(nazwa).localname.lower()


DOZWOLONE_OBRAZY_DATA_URI = tuple(
    f"data:image/{typ};" for typ in ("png", "jpeg", "jpg", "gif", "webp")
)


def _czy_dozwolony_href(wartosc):
    wartosc = normalizuj_url(wartosc)
    if wartosc == "" or wartosc.startswith("#"):
        return True
    if jawny_schemat(wartosc) is None:
        return True  # adres względny
    if wartosc.lower().startswith(DOZWOLONE_OBRAZY_DATA_URI):
        return True
    return czy_bezpieczny_link(wartosc)


BLAD_SVG = (
    "Plik SVG zawiera niedozwolone elementy (np. skrypty, obsługę zdarzeń, "
    "deklarację DOCTYPE lub odnośniki spoza http/https)."
)


def _parsuj_svg(dane):
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
    )
    try:
        return etree.fromstring(dane, parser=parser).getroottree()
    except etree.XMLSyntaxError as e:
        raise ValidationError("Plik SVG nie jest poprawnym dokumentem XML.") from e


def _czy_dozwolony_element(el):
    nazwa = _localname(el.tag)
    if nazwa in ZABRONIONE_ELEMENTY_SVG:
        return False

    if nazwa in ELEMENTY_ANIMACJI_SVG:
        cel = (el.get("attributeName") or "").strip().lower()
        if cel.split(":")[-1] == "href" or cel.startswith("on"):
            return False

    if nazwa == "style" and "javascript:" in "".join(el.itertext()).lower():
        return False

    for atrybut, wartosc in el.attrib.items():
        nazwa_atr = _localname(atrybut)
        if nazwa_atr.startswith("on"):
            return False
        if nazwa_atr == "href" and not _czy_dozwolony_href(wartosc):
            return False
        if "javascript:" in "".join(wartosc.split()).lower():
            return False
    return True


def waliduj_svg(plik):
    """Sprawdź, czy wgrany plik jest „biernym” obrazem SVG."""
    if not plik.name.lower().endswith(".svg"):
        raise ValidationError("Logo wektorowe musi być plikiem .svg.")

    drzewo = _parsuj_svg(_odczytaj(plik, MAKS_ROZMIAR_SVG, "SVG"))
    if drzewo.docinfo.doctype:
        raise ValidationError(BLAD_SVG)

    korzen = drzewo.getroot()
    if not isinstance(korzen.tag, str) or _localname(korzen.tag) != "svg":
        raise ValidationError("Plik nie jest dokumentem SVG.")

    # Instrukcje przetwarzania (np. xml-stylesheet) obok korzenia.
    sasiedzi = list(korzen.itersiblings(preceding=True)) + list(korzen.itersiblings())
    if any(isinstance(x, etree._ProcessingInstruction) for x in sasiedzi):
        raise ValidationError(BLAD_SVG)

    for el in korzen.iter():
        if isinstance(el, (etree._ProcessingInstruction, etree._Entity)):
            raise ValidationError(BLAD_SVG)
        if not isinstance(el.tag, str):
            continue  # komentarze
        if not _czy_dozwolony_element(el):
            raise ValidationError(BLAD_SVG)


def waliduj_favicon(plik):
    """Sprawdź, czy wgrany plik jest obrazem ICO lub PNG."""
    _, rozszerzenie = os.path.splitext(plik.name.lower())
    if rozszerzenie not in ROZSZERZENIA_FAVICON:
        raise ValidationError("Ikona ulubionych musi być plikiem .ico lub .png.")

    _odczytaj(plik, MAKS_ROZMIAR_FAVICON, "ikony")
    try:
        plik.seek(0)
        with Image.open(plik) as obraz:
            format_obrazu = obraz.format
            obraz.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as e:
        raise ValidationError(
            "Ikona ulubionych nie jest poprawnym plikiem graficznym."
        ) from e
    finally:
        plik.seek(0)

    if format_obrazu not in FORMATY_FAVICON:
        raise ValidationError("Ikona ulubionych musi być w formacie ICO lub PNG.")
