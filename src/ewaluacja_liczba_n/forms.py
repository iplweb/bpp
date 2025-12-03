from django import forms
from django.forms import modelformset_factory

from .models import LiczbaNDlaUczelni


class SankcjeForm(forms.ModelForm):
    class Meta:
        model = LiczbaNDlaUczelni
        fields = ["sankcje"]
        widgets = {
            "sankcje": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "class": "text-right",
                    "style": "width: 80px;",
                }
            )
        }


SankcjeFormSet = modelformset_factory(LiczbaNDlaUczelni, form=SankcjeForm, extra=0)
