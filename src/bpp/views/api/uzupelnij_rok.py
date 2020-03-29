# -*- encoding: utf-8 -*-
import logging
import re

from braces.views import LoginRequiredMixin
from django import forms
from django.utils.decorators import method_decorator
from django.views.generic.base import View

from bpp.models.wydawnictwo_zwarte import MIEJSCE_I_ROK_MAX_LENGTH, Wydawnictwo_Zwarte
from bpp.decorators import json_view

logger = logging.getLogger(__name__)

BRAK_DANYCH = {"rok": "b/d"}


class ValidationFormWydawnictwoZwarte(forms.Form):
    miejsce_i_rok = forms.CharField(required=False, max_length=MIEJSCE_I_ROK_MAX_LENGTH)

    wydawnictwo_nadrzedne = forms.ModelChoiceField(
        Wydawnictwo_Zwarte.objects.all(), required=False
    )


class ValidationFormWydawnictwoCiagle(forms.Form):
    informacje = forms.CharField(required=True)


class ApiJsonView(LoginRequiredMixin, View):
    @method_decorator(json_view)
    def post(self, request, *args, **kwargs):
        form = self.validation_form_class(request.POST)
        if not form.is_valid():
            return {"error": "form", "message": form.errors.as_json()}
        return self.get_data(form.cleaned_data)


class ApiUzupelnijRokWydawnictwoZwarteView(ApiJsonView):
    validation_form_class = ValidationFormWydawnictwoZwarte

    def get_data(self, data):
        if data.get("miejsce_i_rok"):
            try:
                rok = re.search(r"\d{4}", data["miejsce_i_rok"]).group(0)
                return {"rok": rok}
            except (IndexError, AttributeError):
                pass

        if data.get("wydawnictwo_nadrzedne"):
            return {"rok": data["wydawnictwo_nadrzedne"].rok}

        return BRAK_DANYCH


class ApiUzupelnijRokWydawnictwoCiagleView(ApiJsonView):
    validation_form_class = ValidationFormWydawnictwoCiagle

    def get_data(self, data):
        try:
            rok = re.search(r"\d{4}", data["informacje"]).group(0)
            return {"rok": rok}
        except (IndexError, AttributeError):
            pass

        return BRAK_DANYCH
