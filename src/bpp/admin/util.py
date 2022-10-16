"""Backport klasy z customizowalnymi parametrami formsetu czyli
ModelAdmin.get_formset_kwargs

"""
import django


class CustomizableFormsetParamsAdminMixinWyrzucWDjango40:
    """Mixin zapewniający funkcję ``get_formset_kwargs`` z Django 4.0,
    można go usunąć po przejściu na tą wersję.

    https://github.com/django/django/commit/3119a6decab7788eca662b10e8c18351d20df212
    """

    def get_formset_kwargs(self, request, obj, inline, prefix):
        formset_params = {
            "instance": obj,
            "prefix": prefix,
            "queryset": inline.get_queryset(request),
        }
        if request.method == "POST":
            formset_params.update(
                {
                    "data": request.POST.copy(),
                    "files": request.FILES,
                    "save_as_new": "_saveasnew" in request.POST,
                }
            )
        return formset_params

    def _create_formsets(self, request, obj, change):
        "Helper function to generate formsets for add/change_view."

        class AlreadyImplementedError(NotImplementedError):
            pass

        if django.VERSION >= (4, 0):
            # Nie wymagamy tego w Django 4.0
            raise AlreadyImplementedError(
                "Uzywasz Django 4.0, wyrzuc ten mixin i uzyj natywnej funkcji"
            )

        formsets = []
        inline_instances = []
        prefixes = {}
        get_formsets_args = [request]
        if change:
            get_formsets_args.append(obj)
        for FormSet, inline in self.get_formsets_with_inlines(*get_formsets_args):
            prefix = FormSet.get_default_prefix()
            prefixes[prefix] = prefixes.get(prefix, 0) + 1
            if prefixes[prefix] != 1 or not prefix:
                prefix = f"{prefix}-{prefixes[prefix]}"
            formset_params = self.get_formset_kwargs(request, obj, inline, prefix)
            formset = FormSet(**formset_params)

            def user_deleted_form(request, obj, formset, index, inline=inline):
                """Return whether or not the user deleted the form."""
                return (
                    inline.has_delete_permission(request, obj)
                    and f"{formset.prefix}-{index}-DELETE" in request.POST
                )

            # Bypass validation of each view-only inline form (since the form's
            # data won't be in request.POST), unless the form was deleted.
            if not inline.has_change_permission(request, obj if change else None):
                for index, form in enumerate(formset.initial_forms):
                    if user_deleted_form(request, obj, formset, index):
                        continue
                    form._errors = {}
                    form.cleaned_data = form.initial
            formsets.append(formset)
            inline_instances.append(inline)
        return formsets, inline_instances
