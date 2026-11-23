from django import forms
from django.contrib.contenttypes.admin import GenericTabularInline

from bpp.models import Element_Repozytorium
from bpp.models.soft_delete_context import soft_delete_context


class Element_RepozytoriumInline(GenericTabularInline):
    model = Element_Repozytorium
    extra = 0
    # Usunięcie pliku w formularzu przenosi go do kosza (inline niżej),
    # skąd można go przywrócić — plik nigdy nie znika z dysku.
    verbose_name_plural = (
        "elementy repozytorium (usunięty plik trafia do kosza niżej — "
        "można go przywrócić)"
    )


class Element_RepozytoriumKoszForm(forms.ModelForm):
    przywroc = forms.BooleanField(label="♻️ Przywróć z kosza", required=False)

    class Meta:
        model = Element_Repozytorium
        fields = []

    def save(self, commit=True):
        # Pozostałe pola są tylko do odczytu: zapis formularza = wyłącznie
        # przywrócenie z kosza (``restore()``, z wpisem w SoftDeleteLog).
        if self.cleaned_data.get("przywroc"):
            self.instance.restore(strict=False)
        return self.instance


class Element_RepozytoriumKoszInline(GenericTabularInline):
    """Pliki repozytorium rekordu, które są w koszu (FD#587). Zaznaczenie
    „♻️ Przywróć z kosza” i zapis rekordu wyjmuje plik z kosza."""

    model = Element_Repozytorium
    form = Element_RepozytoriumKoszForm
    fields = ["nazwa_pliku", "rodzaj", "tryb_dostepu", "deleted_at", "przywroc"]
    readonly_fields = ["nazwa_pliku", "rodzaj", "tryb_dostepu", "deleted_at"]
    extra = 0
    can_delete = False
    verbose_name = "plik w koszu"
    verbose_name_plural = (
        "pliki repozytorium w koszu — zaznacz „♻️ Przywróć z kosza” i zapisz rekord"
    )

    def get_queryset(self, request):
        qs = Element_Repozytorium.deleted_objects.all()
        if not self.has_view_or_change_permission(request):
            qs = qs.none()
        return qs

    def has_add_permission(self, request, obj=None):
        return False

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        class FormsetZUzytkownikiem(formset):
            def add_fields(self, form, index):
                super().add_fields(form, index)
                # Pole ``id`` formsetu szuka wiersza w domyślnym menedżerze,
                # który ukrywa kosz — bez tego każdy zapis tego inline'a
                # kończyłby się błędem „niepoprawny wybór”.
                pole_pk = form.fields.get(self.model._meta.pk.name)
                if pole_pk is not None:
                    pole_pk.queryset = Element_Repozytorium.deleted_objects.all()

            def save(self, commit=True):
                with soft_delete_context(user=request.user):
                    return super().save(commit=commit)

        return FormsetZUzytkownikiem
