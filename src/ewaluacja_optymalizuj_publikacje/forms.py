from django import forms
from django.db.models import Q

from bpp.models import Rekord


class OptymalizacjaForm(forms.Form):
    """Form for selecting a publication to optimize"""

    publikacja_input = forms.CharField(
        label="Tytuł publikacji",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Wprowadź tytuł lub fragment tytułu publikacji",
            }
        ),
        help_text="Wpisz tytuł lub fragment tytułu publikacji",
    )

    def clean_publikacja_input(self):
        publikacja_input = self.cleaned_data["publikacja_input"].strip()

        # Search by title (case-insensitive partial match)
        publikacje = Rekord.objects.filter(
            Q(tytul_oryginalny__icontains=publikacja_input)
            | Q(tytul__icontains=publikacja_input)
        )[
            :20
        ]  # Limit results to 20

        if publikacje.count() == 0:
            raise forms.ValidationError(
                f'Nie znaleziono publikacji pasującej do "{publikacja_input}". '
                f"Spróbuj podać inny fragment tytułu."
            )
        elif publikacje.count() == 1:
            # If exactly one match, return it
            return publikacje.first().slug
        else:
            # Multiple matches found, show them to the user
            matches = []
            for i, pub in enumerate(publikacje, 1):
                matches.append(f"{i}. {pub.tytul_oryginalny[:150]}")
            matches_str = "\n".join(matches)
            raise forms.ValidationError(
                f'Znaleziono {publikacje.count()} publikacji pasujących do "{publikacja_input}". '
                f"Spróbuj podać dokładniejszy fragment tytułu.\n\n"
                f"Znalezione publikacje:\n{matches_str}"
            )


class UnpinDisciplineForm(forms.Form):
    """Form for unpinning a discipline"""

    cache_id = forms.IntegerField(widget=forms.HiddenInput())
    confirm = forms.BooleanField(
        required=False,
        label="Potwierdź odpięcie dyscypliny",
        widget=forms.CheckboxInput(),
    )
