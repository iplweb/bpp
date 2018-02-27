# -*- encoding: utf-8 -*-
from crispy_forms.helper import FormHelper
from dal import autocomplete
from django import forms

from bpp.forms import MediaLessListSelect2


def make_nav_form(url):
    class GlobalNavForm(forms.Form):
        global_nav_value = forms.CharField(
            label="",
            widget=MediaLessListSelect2(
                url=url,
                attrs={
                    'data-html': True,
                    'data-placeholder': 'Wpisz, aby wyszukać...'
                })
        )

        def __init__(self):
            super(GlobalNavForm, self).__init__()

            self.helper = FormHelper(self)
            self.helper.form_show_labels = False
            self.helper.form_tag = False

    return GlobalNavForm


GlobalNavForm = make_nav_form('bpp:navigation-autocomplete')

AdminNavForm = make_nav_form('bpp:admin-navigation-autocomplete')


def user(request):
    if request.path.startswith("/admin/"):
        return dict(global_nav_form=AdminNavForm())
    return dict(global_nav_form=GlobalNavForm())
