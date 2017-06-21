# -*- encoding: utf-8 -*-
from crispy_forms.helper import FormHelper
from dal import autocomplete
from django import forms


class UserGlobalNavForm(forms.Form):
    global_nav_value = forms.CharField(
        label="",
        widget=autocomplete.ListSelect2(
            url='bpp:user-navigation-autocomplete',
            attrs={'data-html': True})
    )

    def __init__(self):
        super(UserGlobalNavForm, self).__init__()
        self.helper = FormHelper(self)
        self.helper.form_show_labels = False
        self.helper.form_tag = False


def user(request):
    return dict(global_nav_form=UserGlobalNavForm())
