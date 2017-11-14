# -*- encoding: utf-8 -*-
from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import Layout, Fieldset, ButtonHolder, \
    Submit, Row, Column
from password_policies.forms import PasswordPoliciesChangeForm

class BppPasswordChangeForm(PasswordPoliciesChangeForm):
    def __init__(self, *args, **kw):

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'Zmień hasło',
                Row(Column('old_password')),
                Row(Column('new_password1')),
                Row(Column('new_password2')),
            ),
            ButtonHolder(
                Submit('submit', 'Zmień hasło', css_class='button white')
            )
        )

        super(BppPasswordChangeForm, self).__init__(*args, **kw)
