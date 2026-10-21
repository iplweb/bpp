from django import forms
from django.db import models

from bpp.fields import CommaDecimalField

# Pliki klawiatury znaków specjalnych (kbw-keypad, vendorowane w
# ``src/bpp/static/kbw-keypad``). Dołącza je ``Media`` widgetów z klasą
# ``charmap`` — dzięki temu ładują się WYŁĄCZNIE na stronach, które mają
# takie pole (formularze wydawnictw, autora, źródła), a nie na każdej
# stronie admina. ``bpp/js/charmap-keypad.js`` podpina klawiaturę pod
# pola ``.charmap`` (wcześniej robił to blok footer w base_site.html).
#
# ``admin/js/jquery.init.js`` na początku listy to KOTWICA kolejności, nie
# nowa zależność (ModelAdmin.media i tak go dołącza). Wtyczki kbw-keypad
# rejestrują się na GLOBALNYM ``jQuery``. Między ``vendor/jquery`` Django a
# ``jquery.init.js`` globalny ``jQuery`` to jQuery Django; dopiero
# ``jquery.init.js`` (``noConflict(true)``) przywraca globalnie jQuery
# grappelli (``grp.jQuery``). Bez kotwicy merge ``Media`` potrafi wstawić
# ``jquery.plugin.min.js`` właśnie w tę lukę — wtedy ``$.JQPlugin`` ląduje
# na złym jQuery i klawiatura się nie inicjalizuje. Widgety są więc
# przeznaczone dla formularzy admina (tam ``jquery.init.js`` już jest).
CHARMAP_JS = (
    "admin/js/jquery.init.js",
    "kbw-keypad/dist/js/jquery.plugin.min.js",
    "kbw-keypad/dist/js/jquery.keypad.js",
    "kbw-keypad/dist/js/jquery.keypad-pl.js",
    "bpp/js/charmap-keypad.js",
)
CHARMAP_CSS = {"all": ("kbw-keypad/dist/css/jquery.keypad.css",)}


class CharmapTextInput(forms.TextInput):
    """Jednoliniowe pole z przyciskiem klawiatury znaków specjalnych."""

    class Media:
        js = CHARMAP_JS
        css = CHARMAP_CSS


class CharmapTextarea(forms.Textarea):
    """Pole tekstowe z przyciskiem klawiatury znaków specjalnych."""

    class Media:
        js = CHARMAP_JS
        css = CHARMAP_CSS


CHARMAP_SINGLE_LINE = CharmapTextInput(
    attrs={"class": "charmap", "style": "width: 500px"}
)

COMMA_DECIMAL_FIELD_OVERRIDE = {
    models.DecimalField: {"form_class": CommaDecimalField},
}

NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW = {
    models.TextField: {
        "widget": CharmapTextarea(attrs={"rows": 2, "cols": 90, "class": "charmap"})
    },
}
