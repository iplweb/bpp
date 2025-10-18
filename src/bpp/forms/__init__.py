from crispy_forms.helper import FormHelper
from crispy_forms.layout import Hidden
from crispy_forms.utils import TEMPLATE_PACK
from crispy_forms_foundation.layout import ButtonHolder, Fieldset, Layout, Submit
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm
from django.template.loader import render_to_string


class SecureNextLink(Hidden):
    def render(self, form, context, template_pack=TEMPLATE_PACK, **kwargs):
        """
        Renders an `<input />` if container is used as a Layout object.
        Input button value can be a variable in context.
        """
        # django-crispy-forms traktuje wartość jako... templatkę, więc w ten sposób moglibyśmy
        # umożliwić zdalnemu użytkownikowi uruchamianie kodu na serwerze:

        # self.value = Template(str(self.value)).render(context)

        template = self.get_template_name(template_pack)
        context.update({"input": self})
        return render_to_string(template, context.flatten())


class MyAuthenticationForm(AuthenticationForm):
    def __init__(self, request=None, *args, **kw):
        self.helper = FormHelper()
        self.helper.form_class = "custom"
        self.helper.form_action = "."

        # Get the next parameter from the request
        next_url = ""
        if request:
            next_url = request.GET.get(REDIRECT_FIELD_NAME, "")

        self.helper.layout = Layout(
            Fieldset(
                "Zaloguj się!",
                "username",
                "password",
                SecureNextLink(REDIRECT_FIELD_NAME, next_url),
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
