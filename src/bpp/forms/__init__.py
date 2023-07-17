from crispy_forms.helper import FormHelper
from crispy_forms.layout import Hidden
from crispy_forms_foundation.layout import ButtonHolder, Fieldset, Layout, Submit

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm


class MyAuthenticationForm(AuthenticationForm):
    def __init__(self, request=None, *args, **kw):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."
        self.helper.layout = Layout(
            Fieldset(
                "Zaloguj się!",
                "username",
                "password",
                Hidden(REDIRECT_FIELD_NAME, """"{{next}}"""),
            ),
            ButtonHolder(
                Submit(
                    "submit",
                    "Zaloguj się",
                    css_id="id_submit",
                    css_class="submit button",
                ),
            ),
        )
        AuthenticationForm.__init__(self, request, *args, **kw)
