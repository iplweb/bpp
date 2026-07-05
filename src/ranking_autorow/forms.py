from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import (
    HTML,
    ButtonHolder,
    Fieldset,
    Hidden,
    Layout,
    Row,
    Submit,
)
from crispy_forms_foundation.layout import Column as F4Column
from dal import autocomplete
from django import forms
from django.core import validators
from django.db.models import Exists, OuterRef, Q

from bpp.models import Charakter_Formalny, Jednostka, Typ_KBN, Uczelnia


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
            url="bpp:public-jednostka-toplevel-autocomplete",
            attrs={
                "data-placeholder": "Wybierz wydział...",
                "data-allow-clear": "true",
            },
        ),
        # Faza B (#438): „wydział" = jednostka-korzeń (parent IS NULL).
        queryset=Jednostka.objects.none(),  # Will be set in __init__
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

    def __init__(self, lata, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)

        uczelnia = Uczelnia.objects.get_for_request(request)
        self.fields["rozbij_na_jednostki"].initial = (
            uczelnia.ranking_autorow_rozbij_domyslnie if uczelnia else False
        )

        # Import models here to avoid circular imports (używane niżej przy
        # budowie listy „wydziałów" mających prace w poddrzewie).
        from bpp.models import (
            Patent_Autor,
            Praca_Doktorska,
            Praca_Habilitacyjna,
            Wydawnictwo_Ciagle_Autor,
            Wydawnictwo_Zwarte_Autor,
        )

        # Czy uczelnia używa wydziałów? Steruje pickerem jednostki (poniżej)
        # oraz osobnym selektorem „wydział" (dalej).
        uzywaj_wydzialow = uczelnia.uzywaj_wydzialow if uczelnia else True

        # Faza B (#438): queryset WALIDACYJNY pola „jednostka" musi być
        # NADZBIOREM tego, co pokazuje picker (autocomplete) — inaczej wybór
        # opcji widocznej w pickerze wywala „Wybierz poprawną opcję" (dawny
        # ``jednostka_with_works`` był węższy niż picker ``publiczne()``:
        # picker pokazywał m.in. korzenie-„wydziały" i jednostki bez prac
        # bezpośrednich, a walidacja je odrzucała). Trzymamy walidację na
        # ``publiczne()`` (nadzbiór per-uczelnia scope'owanego pickera).
        #
        # Gdy uczelnia UŻYWA wydziałów: „wydziały" (korzenie) wybiera osobny
        # selektor, więc z listy „jednostka" wykluczamy korzenie i przełączamy
        # picker na wariant „nie-toplevel" (parent IS NOT NULL).
        jednostka_qs = Jednostka.objects.publiczne()
        if uzywaj_wydzialow:
            jednostka_qs = jednostka_qs.filter(parent__isnull=False)
            self.fields[
                "jednostka"
            ].widget.url = "bpp:public-jednostka-nietoplevel-autocomplete"
        self.fields["jednostka"].queryset = jednostka_qs

        self.helper = FormHelper()
        self.helper.form_method = "post"

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
                                <span class="fi-plus"></span> <span class="fi-minus hidden"></span>
                                Filtry charakteru formalnego (opcjonalne)
                            </a>
                            <div id="charakter-section" class="collapsible-content">
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
                                <span class="fi-plus"></span> <span class="fi-minus hidden"></span>
                                Filtry typu MNiSW/MEiN (opcjonalne)
                            </a>
                            <div id="typ-kbn-section" class="collapsible-content">
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
            # Faza B (#438): „wydziały" = jednostki-korzenie (parent IS NULL)
            # z pracami w poddrzewie. ``wydzial=OuterRef("pk")`` (self-FK)
            # łapie jednostki, których korzeniem jest dany root.
            wydzial_with_works = (
                Jednostka.objects.filter(
                    parent__isnull=True,
                    widoczna=True,
                    zezwalaj_na_ranking_autorow=True,
                )
                .filter(
                    Exists(
                        # Faza B (#438): kandydaci „z pracami" to PODDRZEWO
                        # korzenia (``wydzial=root``) ORAZ SAM korzeń
                        # (``pk=root``; korzeń ma ``wydzial=NULL``, więc bez
                        # tego prace autorów siedzących wprost na wydziale nie
                        # liczyłyby się → selektor mógł zniknąć).
                        Jednostka.objects.filter(
                            Q(wydzial=OuterRef("pk")) | Q(pk=OuterRef("pk")),
                            widoczna=True,
                            wchodzi_do_rankingu_autorow=True,
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

            # Faza B (#438): walidacja pola „wydział" = NADZBIÓR pickera
            # (``public-jednostka-toplevel-autocomplete`` = widoczne korzenie
            # per-uczelnia), żeby wybór z pickera nie wywalał „Wybierz
            # poprawną opcję". ``wydzial_with_works`` (węższy, works-aware)
            # służy TYLKO decyzji, czy w ogóle pokazać selektor.
            self.fields["wydzial"].queryset = Jednostka.objects.widoczne().filter(
                parent__isnull=True
            )

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
