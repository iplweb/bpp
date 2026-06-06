"""Wspólny mixin DjangoQL dla adminów BPP.

Zbiera w jednym miejscu konfigurację, którą dotąd każdy admin powtarzał
(``djangoql_schema = BppQLSchema``) i włącza/poprawia query-UX z djangoql 0.25:

- ``djangoql_highlight = True`` — nakładka kolorująca składnię nad polem
  wyszukiwania,
- ``bpp/js/djangoql-admin.js`` — dorysowuje czerwoną falkę pod błędnym tokenem
  (admin sam tego nie robi), czytając koordynaty wstrzyknięte w komunikat błędu,
- rozbicie „dlaczego 0 wyników" pokazujemy tylko dla zapytań z rozgałęzieniami
  (dla jednowarunkowego nie ma wartości — admin i tak pokazuje „0 wyników").
"""

from django import forms
from django.contrib import messages
from django.core.exceptions import FieldError, ValidationError
from django.forms.utils import flatatt
from django.template.loader import render_to_string
from django.utils.html import format_html, mark_safe
from djangoql.admin import DjangoQLSearchMixin
from djangoql.breakdown import explain_empty
from djangoql.exceptions import DjangoQLError

from bpp.djangoql_schema import BppQLSchema


class BppDjangoQLSearchMixin(DjangoQLSearchMixin):
    """``DjangoQLSearchMixin`` ze wspólnym schematem BPP, podświetlaniem składni
    i drobnymi poprawkami query-UX (falka błędu, mniej szumu w rozbiciu „0")."""

    djangoql_schema = BppQLSchema
    # Nakładką highlight zarządzamy sami (własne media + bpp/js/djangoql-admin.js)
    # zamiast wbudowanego completion_admin_highlight.js — dzięki temu trzymamy
    # UCHWYT nakładki i rysujemy TRWAŁĄ falkę błędu (`setError`, które przeżywa
    # przemalowania). Wbudowane glue uchwyt gubi, więc djangoql_highlight=False,
    # a highlight.css/js dokładamy w ``media``.
    djangoql_highlight = False

    @property
    def media(self):
        return super().media + forms.Media(
            css={"all": ["djangoql/css/highlight.css"]},
            js=["djangoql/js/highlight.js", "bpp/js/djangoql-admin.js"],
        )

    def djangoql_error_message(self, exception):
        """Do komunikatu błędu doklejamy ukryty marker z lokalizacją błędu —
        ``bpp/js/djangoql-admin.js`` rysuje na jego podstawie czerwoną falkę.

        Błąd składni/leksera niesie ``line``+``column`` (podświetlamy ogon);
        błąd schematu (nieznane pole) niesie ``value`` — token lokalizuje już
        front (ma tekst zapytania)."""
        html = super().djangoql_error_message(exception)
        line = getattr(exception, "line", None)
        column = getattr(exception, "column", None)
        if line and column:
            attrs = {"data-line": line, "data-column": column}
        else:
            value = getattr(exception, "value", None)
            attrs = {"data-value": str(value)} if value else None
        if not attrs:
            return html
        marker = format_html(
            '<span class="bpp-dql-error-loc"{} hidden></span>', flatatt(attrs)
        )
        return mark_safe(marker + html)

    def djangoql_add_empty_breakdown(self, request, queryset, qs, search_term):
        """Rozbicie „dlaczego 0 wyników" pokazujemy TYLKO dla zapytań z
        rozgałęzieniami (wiele warunków). Dla prostego, jednowarunkowego
        zapytania rozbicie jest tylko powtórzeniem zapytania + „0", a admin i tak
        renderuje „0 wyników" — więc nie zaśmiecamy ekranu zbędnym komunikatem.

        Re-implementacja ``DjangoQLSearchMixin.djangoql_add_empty_breakdown`` z
        dodatkowym warunkiem ``breakdown['children']``."""
        if not self.djangoql_explain_empty:
            return
        exists = getattr(qs, "exists", None)
        if not callable(exists) or exists():
            return
        try:
            breakdown = explain_empty(
                queryset,
                search_term,
                self.djangoql_schema,
                max_nodes=self.djangoql_explain_empty_max_nodes,
            )
        except (DjangoQLError, ValueError, FieldError, ValidationError):
            return
        if breakdown is None or not breakdown.get("children"):
            return
        msg = render_to_string("djangoql/empty_breakdown.html", {"node": breakdown})
        messages.add_message(request, messages.WARNING, msg)
