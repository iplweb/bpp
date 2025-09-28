from django import forms
from django.core.exceptions import ValidationError

from bpp.models import Jednostka


class PrzemapoaniePracAutoraForm(forms.Form):
    jednostka_z = forms.ModelChoiceField(
        queryset=Jednostka.objects.all(),
        label="Jednostka źródłowa",
        help_text="Jednostka, z której zostaną przemapowane prace",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    jednostka_do = forms.ModelChoiceField(
        queryset=Jednostka.objects.all(),
        label="Jednostka docelowa",
        help_text="Jednostka, do której zostaną przemapowane prace",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, autor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.autor = autor

        if autor:
            # Ogranicz wybór do jednostek, w których autor ma przypisane prace
            from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

            jednostki_ids = set()

            # Znajdź jednostki z prac ciągłych
            jednostki_ids.update(
                Wydawnictwo_Ciagle_Autor.objects.filter(autor=autor)
                .values_list("jednostka_id", flat=True)
                .distinct()
            )

            # Znajdź jednostki z prac zwartych
            jednostki_ids.update(
                Wydawnictwo_Zwarte_Autor.objects.filter(autor=autor)
                .values_list("jednostka_id", flat=True)
                .distinct()
            )

            # Ogranicz queryset do jednostek z pracami
            self.fields["jednostka_z"].queryset = Jednostka.objects.filter(
                id__in=jednostki_ids
            ).order_by("nazwa")

            # Dla jednostki docelowej pokaż wszystkie jednostki OPRÓCZ "Jednostka Domyślna"
            self.fields["jednostka_do"].queryset = Jednostka.objects.exclude(
                nazwa="Jednostka Domyślna"
            ).order_by("nazwa")

            # Ustaw domyślne wartości
            self.set_default_values(autor, jednostki_ids)

    def set_default_values(self, autor, jednostki_ids):
        """Ustaw domyślne wartości dla formularza"""
        # Jeśli autor ma prace tylko w jednej jednostce, ustaw ją jako źródłową
        if len(jednostki_ids) == 1:
            jednostka_id = list(jednostki_ids)[0]
            self.fields["jednostka_z"].initial = jednostka_id

            # Jeśli autor ma aktualną jednostkę różną od źródłowej, ustaw ją jako docelową
            if autor.aktualna_jednostka and autor.aktualna_jednostka.id != jednostka_id:
                # Upewnij się, że aktualna jednostka nie jest Jednostką Domyślną
                if autor.aktualna_jednostka.nazwa != "Jednostka Domyślna":
                    self.fields["jednostka_do"].initial = autor.aktualna_jednostka.id
            return

        # W przeciwnym razie, spróbuj znaleźć "Jednostkę Domyślną"
        try:
            jednostka_domyslna = Jednostka.objects.get(nazwa="Jednostka Domyślna")

            # Sprawdź czy autor ma prace w jednostce domyślnej
            has_works_in_default = jednostka_domyslna.id in jednostki_ids

            if has_works_in_default:
                self.fields["jednostka_z"].initial = jednostka_domyslna.id

                # Jeśli autor ma aktualną jednostkę (i nie jest to Jednostka Domyślna), ustaw ją jako docelową
                if (
                    autor.aktualna_jednostka
                    and autor.aktualna_jednostka != jednostka_domyslna
                ):
                    self.fields["jednostka_do"].initial = autor.aktualna_jednostka.id
        except Jednostka.DoesNotExist:
            pass

    def clean_jednostka_do(self):
        """Walidacja jednostki docelowej"""
        jednostka_do = self.cleaned_data.get("jednostka_do")

        if jednostka_do and jednostka_do.nazwa == "Jednostka Domyślna":
            raise ValidationError(
                'Nie można przemapować prac do "Jednostki Domyślnej". '
                "Jednostka Domyślna jest przeznaczona tylko dla prac importowanych."
            )

        return jednostka_do

    def clean(self):
        cleaned_data = super().clean()
        jednostka_z = cleaned_data.get("jednostka_z")
        jednostka_do = cleaned_data.get("jednostka_do")

        if jednostka_z and jednostka_do:
            if jednostka_z == jednostka_do:
                raise ValidationError("Jednostka źródłowa i docelowa muszą być różne.")

            # Sprawdź czy autor ma jakieś prace w jednostce źródłowej
            if self.autor:
                from bpp.models import (
                    Wydawnictwo_Ciagle_Autor,
                    Wydawnictwo_Zwarte_Autor,
                )

                has_works = (
                    Wydawnictwo_Ciagle_Autor.objects.filter(
                        autor=self.autor, jednostka=jednostka_z
                    ).exists()
                ) or (
                    Wydawnictwo_Zwarte_Autor.objects.filter(
                        autor=self.autor, jednostka=jednostka_z
                    ).exists()
                )

                if not has_works:
                    raise ValidationError(
                        f"Autor {self.autor} nie ma żadnych prac w jednostce {jednostka_z}."
                    )

        return cleaned_data
