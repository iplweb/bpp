from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import (
    ButtonHolder,
    Column,
    Fieldset,
    Layout,
    Row,
    Submit,
)
from django import forms
from django.db import models
from django.forms import RadioSelect
from django.urls import reverse

from . import OUTPUT_FORMATS

from bpp.const import PBN_MAX_ROK, PBN_MIN_ROK
from bpp.models import Uczelnia
from bpp.util import formdefaults_html_after, formdefaults_html_before


class RaportSlotowZerowyParametryFormularz(forms.Form):
    class RodzajeRaportu(models.TextChoices):
        KAZDY_ROK_ODDZIELNIE = "KO", "pokaż za każdy rok oddzielnie"
        SUMA_LAT = "SL", "pokaż występujących we wszystkich latach z zakresu"

    od_roku = forms.IntegerField(
        initial=Uczelnia.objects.do_roku_default, min_value=PBN_MIN_ROK
    )
    do_roku = forms.IntegerField(
        initial=Uczelnia.objects.do_roku_default,
        min_value=PBN_MIN_ROK,
        max_value=PBN_MAX_ROK,
    )

    _export = forms.ChoiceField(
        label="Format wyjściowy",
        choices=OUTPUT_FORMATS,
        required=True,
        widget=RadioSelect,
        initial="html",
    )

    min_pk = forms.IntegerField(
        label="Minimalna wartość PK",
        initial=0,
        help_text="""Nie bierz pod uwagę prac poniżej zadanego PK. Wpisz "zero" aby wyłączyć.""",
    )

    rodzaj_raportu = forms.ChoiceField(
        choices=RodzajeRaportu.choices,
        initial=RodzajeRaportu.SUMA_LAT,
        help_text="""Opcja "<b>pokaż za każdy rok oddzielnie</b>" pokazuje każdy rok bycia zerowym dla autora dla
        wybranego zakresu lat oddzielnie. Czyli jeżeli
        analizujemy zakres 2020-2025 i autor jest "zerowy" w latach 2021 oraz 2023 to te lata zostaną wykazane
        w raporcie.<br/><br/>Opcja "<B>pokaż występujących we wszystkich latach z zakresu</b>" z kolei wykaże wyłącznie
        autorów którzy są "zerowi" w każdym roku z zakresu, czyli wyżej wymieniony przykładowy autor w takim raporcie
        nie wyświetli się wcale. Raport będzie zawierał wyłącznie nazwiska osób "zerowych" przez cały wybrany
        czasokres, czyli w tym przykładzie autorów którzy byli zerowi od 2020 do 2025 w każdym z lat: 2020, 2021,
        2022, 2023, 2024, 2025.
        """,
    )

    @property
    def helper(self):
        helper = FormHelper()
        helper.form_method = "GET"
        helper.form_class = "custom"
        helper.form_action = reverse("raport_slotow:raport-slotow-zerowy-wyniki")
        helper.layout = Layout(
            Fieldset(
                "Wybierz parametry",
                formdefaults_html_before(self),
                Row(
                    Column("od_roku", css_class="large-6 small-6"),
                    Column("do_roku", css_class="large-6 small-6"),
                ),
                Row(Column("rodzaj_raportu")),
                Row(Column("min_pk")),
                Row(Column("_export")),
                formdefaults_html_after(self),
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Wyślij formularz",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )
        return helper
