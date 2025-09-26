from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import HTML, ButtonHolder
from crispy_forms_foundation.layout import Column as F4Column
from crispy_forms_foundation.layout import Fieldset, Hidden, Layout, Row, Submit
from dal import autocomplete
from django import forms
from django.core import validators
from django.db.models import Exists, OuterRef, Q

from bpp.models import Charakter_Formalny, Jednostka, Typ_KBN, Uczelnia, Wydzial


def ustaw_rok(rok, lata):
    lata = list(lata)
    try:
        rok.field.min_value = lata[0]
    except IndexError:
        pass

    try:
        rok.field.max_value = lata[-1]
        rok.field.initial = lata[-2]
    except IndexError:
        pass

    if rok.field.max_value is not None:
        rok.field.validators.append(validators.MaxValueValidator(rok.field.max_value))
    if rok.field.min_value is not None:
        rok.field.validators.append(validators.MinValueValidator(rok.field.min_value))


class WydzialChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.nazwa


class JednostkaChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.nazwa


OUTPUT_FORMATS = [
    ("html", "Wyświetl w przeglądarce"),
    ("json", "JSON"),
    ("csv", "CSV"),
    ("xlsx", "XLSX"),
    ("xls", "XLS"),
    ("ods", "ODS"),
]


class RankingAutorowForm(forms.Form):
    wydzial = WydzialChoiceField(
        label="Ogranicz do wydziału:",
        required=False,
        widget=autocomplete.ModelSelect2(
            url="bpp:wydzial-autocomplete",
            attrs={
                "data-placeholder": "Wybierz wydział...",
                "data-allow-clear": "true",
            },
        ),
        queryset=Wydzial.objects.none(),  # Will be set in __init__
        help_text="Jeżeli nie wybierzesz wydziału, system wygeneruje dane dla wszystkich wydziałów.",
    )

    jednostka = JednostkaChoiceField(
        label="Ogranicz do:",
        required=False,
        widget=autocomplete.ModelSelect2(
            url="bpp:public-jednostka-autocomplete",
            attrs={
                "data-placeholder": "Wybierz jednostkę...",
                "data-allow-clear": "true",
            },
        ),
        queryset=Jednostka.objects.none(),  # Will be set in __init__
        help_text="Jeżeli nie wybierzesz jednostki, system wygeneruje dane dla wszystkich jednostek.",
    )

    rozbij_na_jednostki = forms.BooleanField(
        label="Rozbij punktację na jednostki i wydziały",
        required=False,
        initial=lambda: Uczelnia.objects.first().ranking_autorow_rozbij_domyslnie,
    )

    tylko_afiliowane = forms.BooleanField(
        label="Tylko prace afiliowane na jednostki uczelni",
        required=False,
        initial=False,
        help_text="Pokaż tylko prace, gdzie autor afiliował na jednostkę "
        "wchodzącą w struktury uczelni",
    )

    bez_nieaktualnych = forms.BooleanField(
        label="Bez nieaktualnych autorów",
        initial=True,
        required=False,
        help_text="""Nie pokazuj autorów, którzy nie mają określonego pola 'Aktualna jednostka'.""",
    )

    od_roku = forms.IntegerField(initial=Uczelnia.objects.do_roku_default)
    do_roku = forms.IntegerField(initial=Uczelnia.objects.do_roku_default)

    _export = forms.ChoiceField(
        label="Format wyjściowy", required=True, choices=OUTPUT_FORMATS, initial="html"
    )

    charakter_formalny = forms.ModelMultipleChoiceField(
        label="Ogranicz do charakteru formalnego:",
        queryset=Charakter_Formalny.objects.filter(wliczaj_do_rankingu=True).order_by(
            "nazwa"
        ),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "charakter-checkboxes"}),
        help_text=(
            "Możesz wybrać jeden lub więcej charakterów formalnych. "
            "Jeżeli nie wybierzesz żadnego, system uwzględni wszystkie."
        ),
    )

    typ_kbn = forms.ModelMultipleChoiceField(
        label="Ogranicz do typu MNiSW/MEiN:",
        queryset=Typ_KBN.objects.filter(wliczaj_do_rankingu=True).order_by("nazwa"),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "typ-kbn-checkboxes"}),
        help_text=(
            "Możesz wybrać jeden lub więcej typów publikacji. "
            "Jeżeli nie wybierzesz żadnego, system uwzględni wszystkie."
        ),
    )

    def __init__(self, lata, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Import models here to avoid circular imports
        from bpp.models import (
            Patent_Autor,
            Praca_Doktorska,
            Praca_Habilitacyjna,
            Wydawnictwo_Ciagle_Autor,
            Wydawnictwo_Zwarte_Autor,
        )

        # Filter Jednostka to show only those with associated works
        jednostka_with_works = (
            Jednostka.objects.filter(widoczna=True, wchodzi_do_raportow=True)
            .filter(
                Q(
                    Exists(
                        Wydawnictwo_Ciagle_Autor.objects.filter(
                            jednostka=OuterRef("pk")
                        )
                    )
                )
                | Q(
                    Exists(
                        Wydawnictwo_Zwarte_Autor.objects.filter(
                            jednostka=OuterRef("pk")
                        )
                    )
                )
                | Q(Exists(Patent_Autor.objects.filter(jednostka=OuterRef("pk"))))
                | Q(Exists(Praca_Doktorska.objects.filter(jednostka=OuterRef("pk"))))
                | Q(
                    Exists(Praca_Habilitacyjna.objects.filter(jednostka=OuterRef("pk")))
                )
            )
            .distinct()
        )

        self.fields["jednostka"].queryset = jednostka_with_works

        self.helper = FormHelper()
        self.helper.form_method = "post"

        # Check if uczelnia uses wydzialy
        uczelnia = Uczelnia.objects.first()
        uzywaj_wydzialow = uczelnia.uzywaj_wydzialow if uczelnia else True

        # Build layout fields based on uzywaj_wydzialow
        layout_fields = [
            Row(
                F4Column("od_roku", css_class="large-6 small-6"),
                F4Column("do_roku", css_class="large-6 small-6"),
            ),
            Row(F4Column("_export", css_class="large-12 small-12")),
            Row(F4Column("rozbij_na_jednostki", css_class="large-12 small-12")),
            Row(F4Column("tylko_afiliowane", css_class="large-12 small-12")),
            Row(F4Column("bez_nieaktualnych", css_class="large-12 small-12")),
            # Collapsible section for charakter_formalny
            HTML(
                """
                <div class="row">
                    <div class="large-12 small-12 columns">
                        <div class="collapsible-section">
                            <a href="#" class="collapsible-trigger" data-target="charakter-section">
                                <span class="fi-plus"></span> <span class="fi-minus" style="display:none;"></span>
                                Filtry charakteru formalnego (opcjonalne)
                            </a>
                            <div id="charakter-section" class="collapsible-content"
                                 style="display:none; margin-top: 1rem;">
                """
            ),
            Row(F4Column("charakter_formalny", css_class="large-12 small-12")),
            HTML(
                """
                            </div>
                        </div>
                    </div>
                </div>
                """
            ),
            # Collapsible section for typ_kbn
            HTML(
                """
                <div class="row">
                    <div class="large-12 small-12 columns">
                        <div class="collapsible-section">
                            <a href="#" class="collapsible-trigger" data-target="typ-kbn-section">
                                <span class="fi-plus"></span> <span class="fi-minus" style="display:none;"></span>
                                Filtry typu MNiSW/MEiN (opcjonalne)
                            </a>
                            <div id="typ-kbn-section" class="collapsible-content"
                                 style="display:none; margin-top: 1rem;">
                """
            ),
            Row(F4Column("typ_kbn", css_class="large-12 small-12")),
            HTML(
                """
                            </div>
                        </div>
                    </div>
                </div>
                """
            ),
        ]

        # Always show jednostka field
        layout_fields.append(Row(F4Column("jednostka", css_class="large-12 small-12")))

        if uzywaj_wydzialow:
            # Filter Wydzial to show only those with associated works through their jednostki
            wydzial_with_works = (
                Wydzial.objects.filter(widoczny=True, zezwalaj_na_ranking_autorow=True)
                .filter(
                    Exists(
                        Jednostka.objects.filter(
                            wydzial=OuterRef("pk"),
                            widoczna=True,
                            wchodzi_do_raportow=True,
                        ).filter(
                            Q(
                                Exists(
                                    Wydawnictwo_Ciagle_Autor.objects.filter(
                                        jednostka=OuterRef("pk")
                                    )
                                )
                            )
                            | Q(
                                Exists(
                                    Wydawnictwo_Zwarte_Autor.objects.filter(
                                        jednostka=OuterRef("pk")
                                    )
                                )
                            )
                            | Q(
                                Exists(
                                    Patent_Autor.objects.filter(
                                        jednostka=OuterRef("pk")
                                    )
                                )
                            )
                            | Q(
                                Exists(
                                    Praca_Doktorska.objects.filter(
                                        jednostka=OuterRef("pk")
                                    )
                                )
                            )
                            | Q(
                                Exists(
                                    Praca_Habilitacyjna.objects.filter(
                                        jednostka=OuterRef("pk")
                                    )
                                )
                            )
                        )
                    )
                )
                .distinct()
            )

            self.fields["wydzial"].queryset = wydzial_with_works

            # Only show wydzial field when there's more than one wydział
            if wydzial_with_works.count() > 1:
                layout_fields.append(
                    Row(F4Column("wydzial", css_class="large-12 small-12"))
                )
            else:
                # Remove wydzial field if only one wydział exists
                del self.fields["wydzial"]
        else:
            # Remove wydzial field from form when not using wydzialy
            del self.fields["wydzial"]
            # Update rozbij_na_jednostki label when not using wydzialy
            self.fields["rozbij_na_jednostki"].label = "Rozbij punktację na jednostki"

        layout_fields.append(Hidden("report", "ranking-autorow"))

        self.helper.layout = Layout(
            Fieldset("Ranking autorów", *layout_fields),
            ButtonHolder(Submit("submit", "Otwórz", css_class="button white")),
        )
