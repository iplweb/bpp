from django import forms
from django.db import models
from django.forms.widgets import Textarea

from bpp.fields import CommaDecimalField

CHARMAP_SINGLE_LINE = forms.TextInput(
    attrs={"class": "charmap", "style": "width: 500px"}
)

COMMA_DECIMAL_FIELD_OVERRIDE = {
    models.DecimalField: {"form_class": CommaDecimalField},
}

NIZSZE_TEXTFIELD_Z_MAPA_ZNAKOW = {
    models.TextField: {
        "widget": Textarea(attrs={"rows": 2, "cols": 90, "class": "charmap"})
    },
}
