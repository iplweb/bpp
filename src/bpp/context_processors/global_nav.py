from crispy_forms.helper import FormHelper
from dal_select2.widgets import ListSelect2
from django import forms


def make_nav_form(url, dropdownCssClass=""):
    class GlobalNavForm(forms.Form):
        global_nav_value = forms.CharField(
            label="",
            widget=ListSelect2(
                url=url,
                attrs={
                    "data-dropdown-css-class": dropdownCssClass,
                    "data-html": True,
                    "data-placeholder": "Wpisz, aby wyszukać...",
                    "data-minimum-input-length": 3,
                },
            ),
        )

        def __init__(self):
            super().__init__()

            self.helper = FormHelper(self)
            self.helper.form_show_labels = False
            self.helper.form_tag = False

    return GlobalNavForm


GlobalNavForm = make_nav_form("bpp:navigation-autocomplete", "globalNavUser")

AdminNavForm = make_nav_form("bpp:admin-navigation-autocomplete", "globalNavAdmin")


def user(request):
    if request.path.startswith("/admin/"):
        return dict(global_nav_form=AdminNavForm())
    return dict(global_nav_form=GlobalNavForm())
