from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import (
    ButtonHolder,
    Column,
    Fieldset,
    Layout,
    Row,
    Submit,
)
from django.conf import settings
from password_policies.forms import PasswordPoliciesChangeForm


class BppPasswordChangeForm(PasswordPoliciesChangeForm):
    def __init__(self, *args, **kw):
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            Fieldset(
                "Zmień hasło",
                Row(Column("old_password")),
                Row(Column("new_password1")),
                Row(Column("new_password2")),
            ),
            ButtonHolder(Submit("submit", "Zmień hasło", css_class="button white")),
        )

        super().__init__(*args, **kw)
        self.fields["new_password1"].help_text = (
            f"Co najmniej {settings.PASSWORD_MIN_LENGTH} znaków. Nie musi "
            "zawierać cyfr ani znaków specjalnych — najłatwiej zapamiętać "
            "kilka słów, np. całe zdanie."
        )
