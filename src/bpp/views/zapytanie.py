import json

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import FieldError, ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.views.generic import FormView, View
from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search
from djangoql.schema import DjangoQLSchema
from djangoql.serializers import SuggestionsAPISerializer
from djangoql.views import SuggestionsAPIView

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor
from bpp.models.cache import Rekord

MODEL_REKORD = "rekord"
MODEL_AUTOR = "autor"

MODEL_CHOICES = (
    (MODEL_REKORD, "Rekord"),
    (MODEL_AUTOR, "Autor"),
)

MODELS = {
    MODEL_REKORD: Rekord,
    MODEL_AUTOR: Autor,
}


class WprowadzanieDanychOrSuperuserMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Dostep dla superuserow lub uzytkownikow w grupie 'wprowadzanie danych'
    bedacych jednoczesnie w staffie."""

    raise_exception = True

    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        return (
            user.is_staff and user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
        )


class ZapytanieForm(forms.Form):
    model = forms.ChoiceField(
        choices=MODEL_CHOICES,
        widget=forms.RadioSelect,
        initial=MODEL_REKORD,
        label="Model do przeszukania",
    )
    query = forms.CharField(
        label="Zapytanie DjangoQL",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": ('tytul_oryginalny ~ "nowotwor" and rok >= 2020'),
                "spellcheck": "false",
                "autocomplete": "off",
            }
        ),
        required=False,
        help_text=(
            "Skladnia DjangoQL: pole operator wartosc, laczone przez "
            "<code>and</code> / <code>or</code>. "
            "Operatory: <code>=</code>, <code>!=</code>, <code>&gt;</code>, "
            "<code>&gt;=</code>, <code>&lt;</code>, <code>&lt;=</code>, "
            "<code>~</code> (zawiera), <code>!~</code> (nie zawiera), "
            "<code>in</code>, <code>not in</code>. "
            "Stringi w cudzyslowach. "
            'Przyklady: <code>tytul_oryginalny ~ "rak"</code>, '
            '<code>rok = 2024 and charakter_formalny.skrot = "AC"</code>, '
            '<code>nazwisko ~ "Kowal" or imiona ~ "Jan"</code>.'
        ),
    )


class ZapytanieView(WprowadzanieDanychOrSuperuserMixin, FormView):
    template_name = "bpp/zapytanie.html"
    form_class = ZapytanieForm
    paginate_by = 25

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.method == "GET" and "model" in self.request.GET:
            kwargs["data"] = self.request.GET
        return kwargs

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if "query" in request.GET and form.is_valid() and form.cleaned_data["query"]:
            return self.render_results(form)
        return self.render_to_response(self.get_context_data(form=form))

    def render_results(self, form):
        model_key = form.cleaned_data["model"]
        query = form.cleaned_data["query"].strip()
        model = MODELS[model_key]
        queryset = model.objects.all()
        error = None
        results_page = None
        count = None

        try:
            queryset = apply_search(queryset, query)
            count = queryset.count()
            paginator = Paginator(queryset, self.paginate_by)
            page_number = self.request.GET.get("page") or 1
            results_page = paginator.get_page(page_number)
        except (DjangoQLError, FieldError, ValidationError, ValueError) as exc:
            error = self._format_error(exc)

        context = self.get_context_data(
            form=form,
            results=results_page,
            count=count,
            error=error,
            model_key=model_key,
            query=query,
        )
        return self.render_to_response(context)

    @staticmethod
    def _format_error(exc):
        if isinstance(exc, ValidationError):
            return "; ".join(exc.messages)
        return str(exc)


def _resolve_model_or_404(model_key):
    try:
        return MODELS[model_key]
    except KeyError:
        raise Http404(f"Nieznany model: {model_key}")


class ZapytanieIntrospectView(WprowadzanieDanychOrSuperuserMixin, View):
    def get(self, request, model_key):
        model = _resolve_model_or_404(model_key)
        suggestions_url = reverse(
            "bpp:zapytanie_suggestions", kwargs={"model_key": model_key}
        )
        schema = DjangoQLSchema(model)
        payload = SuggestionsAPISerializer(suggestions_url).serialize(schema)
        return HttpResponse(
            content=json.dumps(payload),
            content_type="application/json; charset=utf-8",
        )


class ZapytanieSuggestionsView(WprowadzanieDanychOrSuperuserMixin, View):
    def get(self, request, model_key):
        model = _resolve_model_or_404(model_key)
        view = SuggestionsAPIView.as_view(schema=DjangoQLSchema(model))
        return view(request)
