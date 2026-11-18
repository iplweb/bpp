from crispy_forms.helper import FormHelper
from crispy_forms_foundation.layout import (
    HTML,
    ButtonHolder,
    Column,
    Fieldset,
    Layout,
    Row,
    Submit,
)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import is_password_usable
from password_policies.forms import (
    PasswordPoliciesChangeForm,
    PasswordPoliciesForm,
    PasswordResetForm,
)


class BppSetPasswordForm(PasswordPoliciesForm):
    """Set a new password after following a reset link.

    Marks both fields as ``new-password`` so password managers (Bitwarden
    etc.) offer a generated password and update the saved login.
    """

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        for name in ("new_password1", "new_password2"):
            self.fields[name].widget.attrs["autocomplete"] = "new-password"


class BppPasswordChangeForm(PasswordPoliciesChangeForm):
    AUTOCOMPLETE = {
        "old_password": "current-password",
        "new_password1": "new-password",
        "new_password2": "new-password",
    }

    def __init__(self, *args, **kw):
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            Fieldset(
                "Zmień hasło",
                # Hidden username lets password managers (Bitwarden etc.) tell
                # which saved login the new password belongs to.
                HTML(
                    '<input type="text" name="username" autocomplete="username"'
                    ' value="{{ form.user.get_username }}" hidden>'
                ),
                Row(Column("old_password")),
                Row(Column("new_password1")),
                Row(Column("new_password2")),
            ),
            ButtonHolder(Submit("submit", "Zmień hasło", css_class="button white")),
        )

        super().__init__(*args, **kw)
        # Without autocomplete hints password managers do not recognise this
        # as a "change password" form and offer no generated password.
        for name, hint in self.AUTOCOMPLETE.items():
            self.fields[name].widget.attrs["autocomplete"] = hint
        self.fields["new_password1"].help_text = (
            f"Co najmniej {settings.PASSWORD_MIN_LENGTH} znaków. Nie musi "
            "zawierać cyfr ani znaków specjalnych — najłatwiej zapamiętać "
            "kilka słów, np. całe zdanie. Unikaj imion, nazwisk, nazw "
            "miejscowości i dat z dopisanymi cyframi."
        )


class BppPasswordResetForm(PasswordResetForm):
    """Formularz resetu hasła, który NIE informuje, czy konto istnieje.

    Bazowy formularz ``password_policies`` zgłasza błąd walidacji dla adresu
    bez konta (lub z kontem bez używalnego hasła). Tutaj każdy poprawny
    składniowo adres przechodzi walidację; wiadomość dostają wyłącznie aktywne
    konta z używalnym hasłem, a pozostałe przypadki kończą się tą samą
    odpowiedzią — zachowanie zgodne z ``django.contrib.auth``.
    """

    def clean_email(self):
        email = self.cleaned_data["email"]
        self.users_cache = [
            user
            for user in get_user_model().objects.filter(
                email__iexact=email, is_active=True
            )
            if is_password_usable(user.password)
        ]
        return email
