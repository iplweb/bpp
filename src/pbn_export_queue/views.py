import json
import re
import sys

import rollbar
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import F
from django.db.models.functions import Coalesce
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from bpp.const import GR_WPROWADZANIE_DANYCH

from .models import PBN_Export_Queue

# Email template for PBN helpdesk error reporting
HELPDESK_EMAIL_TEMPLATE = """Temat: Błąd eksportu do PBN - {record_title_short}
Do: pomoc@pbn.nauka.gov.pl
Od: {user_email}

Dzień dobry,

Zwracam się z prośbą o pomoc w rozwiązaniu problemu z eksportem publikacji do systemu PBN.

SZCZEGÓŁY BŁĘDU:
- Data i godzina wysyłki: {submitted_date}
- Kod błędu HTTP: {error_code}
- Endpoint API: {error_endpoint}
- Tytuł publikacji: {record_title}

ODPOWIEDŹ Z API PBN:
{error_details}

KONTEKST:
Próbowaliśmy wysłać publikację do systemu PBN, jednak otrzymaliśmy błąd. Nie mamy pewności, co jest przyczyną problemu i prosimy o pomoc Helpdesku PBN w zidentyfikowaniu przyczyny oraz wskazówki, jak poprawić dane.

DANE TECHNICZNE:
- ID kolejki eksportu: {queue_pk}
- Typ rekordu: {content_type}
- Ilość prób wysyłki: {ilosc_prob}

KOD JSON WYSŁANY DO PBN API:
{json_data}

Z poważaniem,
{user_name}
"""

# AI prompt template for analyzing PBN export errors
AI_PROMPT_TEMPLATE = """Proszę o pomoc w naprawieniu błędu eksportu publikacji do systemu PBN (Polski Narodowy Bibliografii).

# KONTEKST
Próbuję wysłać publikację do PBN API, ale otrzymuję błąd. Potrzebuję wskazówek, co jest nie tak z wysyłanymi danymi.

# DANE WYSŁANE DO PBN API
```json
{json_data}
```

# OTRZYMANY BŁĄD
- Kod HTTP: {error_code}
- Szczegóły błędu:
{error_details}
- Tytuł publikacji: {record_title}

# ZADANIE
Przeanalizuj wysłane dane JSON oraz otrzymany błąd i wskaż:
1. Co jest nie tak z danymi JSON zgodnie z dokumentacją API PBN?
2. Jakie pola są błędne lub brakujące?
3. Jak poprawić dane, aby eksport się powiódł?

# DOKUMENTACJA
Dokumentacja API PBN jest dostępna pod adresem: https://pbn.nauka.gov.pl/api/

Proszę o szczegółową analizę i konkretne wskazówki naprawcze.
"""


def sanitize_filename(text, max_length=100):
    """
    Sanitize text to create safe filename.
    Removes unsafe characters and limits length.
    """
    if not text:
        return "export"

    # Use slugify to create safe filename
    safe_name = slugify(text, allow_unicode=False)

    # Limit length
    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length]

    return safe_name or "export"


def get_filename_from_record(rekord):
    """Generate filename from publication record."""
    if hasattr(rekord, "slug") and rekord.slug:
        return sanitize_filename(rekord.slug)
    elif hasattr(rekord, "tytul_oryginalny") and rekord.tytul_oryginalny:
        return sanitize_filename(rekord.tytul_oryginalny)
    else:
        return "export"


def _extract_exception_type(exception_text, has_pbn_prefix):
    """Extract exception type and message part from exception text."""
    exception_type = "HttpException"  # Default for tuple format
    message_part = exception_text.strip()

    if has_pbn_prefix and ":" in exception_text:
        parts = exception_text.split(":", 1)
        exception_class = parts[0].strip()
        message_part = parts[1].strip()

        # Extract exception type (e.g., "HttpException", "StatementsMissing")
        if "." in exception_class:
            exception_type = exception_class.split(".")[-1]
        else:
            exception_type = exception_class

    return exception_type, message_part


def _parse_json_error(error_json):
    """Parse JSON error response from PBN API."""
    # Handle both dict and list responses from PBN API
    if isinstance(error_json, dict):
        error_message = error_json.get("message", "")
        error_description = error_json.get("description", "")

        # Format details as pretty JSON
        if "details" in error_json:
            error_details_json = json.dumps(
                error_json["details"], indent=2, ensure_ascii=False
            )
        else:
            # If no details, show the whole error JSON
            error_details_json = json.dumps(error_json, indent=2, ensure_ascii=False)

        return error_message, error_description, error_details_json

    elif isinstance(error_json, list):
        # PBN API returned a list instead of dict
        error_message = "PBN API zwróciło listę błędów"
        error_details_json = json.dumps(error_json, indent=2, ensure_ascii=False)
        return error_message, None, error_details_json

    else:
        # Unexpected JSON type
        error_message = "Nieoczekiwany typ odpowiedzi PBN API"
        error_details_json = json.dumps(error_json, indent=2, ensure_ascii=False)
        return error_message, None, error_details_json


def _parse_error_tuple(message_part, exception_type):
    """Parse error tuple format: (code, endpoint, json_str)."""
    import ast

    try:
        exception_tuple = ast.literal_eval(message_part.strip())
        if not (isinstance(exception_tuple, tuple) and len(exception_tuple) >= 3):
            return None

        error_code = int(exception_tuple[0])
        error_endpoint = exception_tuple[1]
        error_json_str = exception_tuple[2]

        result = {
            "is_pbn_api_error": True,
            "exception_type": exception_type,
            "error_code": error_code,
            "error_endpoint": error_endpoint,
        }

        # Try to parse the JSON error response
        try:
            error_json = json.loads(error_json_str)
            error_message, error_description, error_details_json = _parse_json_error(
                error_json
            )

            result["error_message"] = error_message
            if error_description:
                result["error_description"] = error_description
            result["error_details_json"] = error_details_json

        except (json.JSONDecodeError, TypeError, KeyError):
            # JSON parsing failed, but we still have the code and endpoint
            result["error_details_json"] = error_json_str

        return result

    except (ValueError, SyntaxError):
        return None


def parse_pbn_api_error(exception_text):
    """
    Parse PBN API exception to extract error details.

    Returns dict with:
    - is_pbn_api_error: bool
    - error_code: int (if parsed)
    - error_endpoint: str (if parsed)
    - error_message: str (if parsed)
    - error_description: str (if parsed)
    - error_details_json: str (formatted JSON if parsed)
    - exception_type: str (exception class name)
    - raw_error: str (fallback)
    """
    result = {
        "is_pbn_api_error": False,
        "raw_error": exception_text or "Brak szczegółów błędu",
    }

    if not exception_text:
        return result

    # Check if this looks like a PBN error (either with prefix or just a tuple)
    has_pbn_prefix = "pbn_api.exceptions" in exception_text
    looks_like_tuple = exception_text.strip().startswith("(") and "," in exception_text

    if not has_pbn_prefix and not looks_like_tuple:
        return result

    # Extract exception type and message part
    exception_type, message_part = _extract_exception_type(
        exception_text, has_pbn_prefix
    )

    # Security: limit string length to prevent DoS
    if len(message_part.strip()) > 512:
        if has_pbn_prefix:
            result["is_pbn_api_error"] = True
            result["exception_type"] = exception_type
            result["error_message"] = "Error message too long (>512 chars)"
        return result

    # Try to parse as tuple (HttpException format)
    tuple_result = _parse_error_tuple(message_part, exception_type)
    if tuple_result:
        return tuple_result

    # If not a tuple, it's a simple exception like StatementsMissing (only if has pbn_prefix)
    if has_pbn_prefix:
        result["is_pbn_api_error"] = True
        result["exception_type"] = exception_type
        result["error_message"] = message_part.strip()

    return result


def extract_pbn_error_from_komunikat(komunikat):
    """
    Extract PBN API error from komunikat field (traceback).
    Looks for the last line containing 'pbn_api.exceptions'.

    Returns the exception line or None if not found.
    """
    if not komunikat:
        return None

    lines = komunikat.strip().split("\n")

    # Search from the end for a line with pbn_api.exceptions
    for line in reversed(lines):
        if "pbn_api.exceptions" in line:
            return line.strip()

    return None


def _get_record_title(rekord):
    """
    Extract title from a publication record.

    Tries tytul_oryginalny first, then opis_bibliograficzny_cache.
    Returns "Nieznany rekord" if no title is found.
    """
    if not rekord:
        return "Nieznany rekord"

    if hasattr(rekord, "tytul_oryginalny") and rekord.tytul_oryginalny:
        return rekord.tytul_oryginalny
    elif (
        hasattr(rekord, "opis_bibliograficzny_cache")
        and rekord.opis_bibliograficzny_cache
    ):
        return rekord.opis_bibliograficzny_cache

    return "Nieznany rekord"


def _parse_error_details(sent_data):
    """
    Parse error details from SentData.

    Returns a dict with:
    - error_code: HTTP error code or fallback
    - error_endpoint: API endpoint where error occurred
    - error_details: Formatted error details (JSON or string)
    """
    error_code = "Brak kodu błędu"
    error_endpoint = "Nieznany endpoint"
    error_details = "Brak szczegółów błędu"

    if sent_data.exception:
        try:
            # Try to parse tuple format: (code, endpoint, json_str)
            import ast

            exception_tuple = ast.literal_eval(sent_data.exception)
            if isinstance(exception_tuple, tuple) and len(exception_tuple) >= 3:
                error_code = exception_tuple[0]
                error_endpoint = exception_tuple[1]
                error_json_str = exception_tuple[2]
                try:
                    error_json = json.loads(error_json_str)
                    error_details = json.dumps(error_json, indent=2, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    error_details = error_json_str
            else:
                error_details = sent_data.exception
        except (ValueError, SyntaxError):
            # If parsing fails, use the raw exception
            error_details = sent_data.exception

    # Use api_response_status as fallback for error code
    if error_code == "Brak kodu błędu" and sent_data.api_response_status:
        error_code = sent_data.api_response_status

    return {
        "error_code": error_code,
        "error_endpoint": error_endpoint,
        "error_details": error_details,
    }


def _format_submission_date(sent_data):
    """
    Format submission date for display.

    Uses submitted_at if available, falls back to last_updated_on,
    then to "Nieznana data".
    """
    if sent_data.submitted_at:
        return sent_data.submitted_at.strftime("%Y-%m-%d %H:%M:%S")
    elif sent_data.last_updated_on:
        return sent_data.last_updated_on.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return "Nieznana data"


def _get_user_info(user):
    """
    Extract user email and full name from User object.

    Returns a dict with:
    - user_email: User's email or username as fallback
    - user_name: User's full name or username as fallback
    """
    user_email = user.email if user.email else user.username
    user_name = user.get_full_name() or user.username

    return {
        "user_email": user_email,
        "user_name": user_name,
    }


class PBNExportQueuePermissionMixin(UserPassesTestMixin):
    """Mixin for permission checking - user must be staff or have GR_WPROWADZANIE_DANYCH group"""

    def test_func(self):
        user = self.request.user
        return user.is_staff or user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()


class PBNExportQueueListView(
    LoginRequiredMixin, PBNExportQueuePermissionMixin, ListView
):
    """ListView for PBN Export Queue with filtering by success status"""

    model = PBN_Export_Queue
    template_name = "pbn_export_queue/pbn_export_queue_list.html"
    context_object_name = "export_queue_items"
    paginate_by = 25

    def _filter_by_success_status(self, queryset):
        """Filter queryset by zakonczono_pomyslnie parameter."""
        success_filter = self.request.GET.get("zakonczono_pomyslnie")
        if success_filter == "true":
            return queryset.filter(zakonczono_pomyslnie=True)
        elif success_filter == "false":
            return queryset.filter(zakonczono_pomyslnie=False)
        elif success_filter == "none":
            return queryset.filter(zakonczono_pomyslnie=None)
        return queryset

    def _find_matching_record_ids(self, queryset, search_query):
        """Find record IDs that match search query in their title fields."""
        matching_ids = []

        for item in queryset.select_related("content_type"):
            if not item.rekord_do_wysylki:
                continue

            try:
                record = item.rekord_do_wysylki
                # Check if record has title fields
                if hasattr(record, "tytul_oryginalny") and record.tytul_oryginalny:
                    if search_query.lower() in record.tytul_oryginalny.lower():
                        matching_ids.append(item.pk)
                elif (
                    hasattr(record, "opis_bibliograficzny_cache")
                    and record.opis_bibliograficzny_cache
                ):
                    if (
                        search_query.lower()
                        in record.opis_bibliograficzny_cache.lower()
                    ):
                        matching_ids.append(item.pk)
            except BaseException:
                pass

        return matching_ids

    def _apply_search_filter(self, queryset):
        """Apply search query filter to queryset."""
        search_query = self.request.GET.get("q")
        if not search_query:
            return queryset

        from django.db.models import Q

        # Search in komunikat field which contains publication info
        queryset = queryset.filter(Q(komunikat__icontains=search_query))

        # Additionally filter by checking the actual related objects
        matching_ids = self._find_matching_record_ids(queryset, search_query)

        # If we found matching IDs, filter by them
        if matching_ids:
            queryset = queryset.filter(
                Q(pk__in=matching_ids) | Q(komunikat__icontains=search_query)
            )

        return queryset

    def _apply_sorting(self, queryset):
        """Apply sorting to queryset based on sort parameter."""
        sort_by = self.request.GET.get("sort", "-ostatnia_aktualizacja")
        allowed_sorts = {
            "pk": "pk",
            "-pk": "-pk",
            "zamowiono": "zamowiono",
            "-zamowiono": "-zamowiono",
            "ostatnia_aktualizacja": "ostatnia_aktualizacja_sort",
            "-ostatnia_aktualizacja": "-ostatnia_aktualizacja_sort",
            "ilosc_prob": "ilosc_prob",
            "-ilosc_prob": "-ilosc_prob",
            "zakonczono_pomyslnie": "zakonczono_pomyslnie",
            "-zakonczono_pomyslnie": "-zakonczono_pomyslnie",
        }
        if sort_by in allowed_sorts:
            queryset = queryset.order_by(allowed_sorts[sort_by])
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()

        # Annotate with ostatnia_aktualizacja for sorting
        queryset = queryset.annotate(
            ostatnia_aktualizacja_sort=Coalesce(
                F("wysylke_zakonczono"), F("wysylke_podjeto"), F("zamowiono")
            )
        )

        # Apply filters
        queryset = self._filter_by_success_status(queryset)
        queryset = self._apply_search_filter(queryset)
        queryset = self._apply_sorting(queryset)

        return queryset.select_related("zamowil", "content_type")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_filter"] = self.request.GET.get("zakonczono_pomyslnie", "all")
        context["search_query"] = self.request.GET.get("q", "")
        # Add count of error records for the resend button
        context["error_count"] = PBN_Export_Queue.objects.filter(
            zakonczono_pomyslnie=False
        ).count()
        # Add count of waiting records for the resend button
        context["waiting_count"] = PBN_Export_Queue.objects.filter(
            retry_after_user_authorised=True
        ).count()
        # Add count of never sent records for the wake up button
        context["never_sent_count"] = PBN_Export_Queue.objects.filter(
            wysylke_podjeto=None,
            wysylke_zakonczono=None,
        ).count()
        # Add counts for filter buttons
        context["total_count"] = PBN_Export_Queue.objects.count()
        context["success_count"] = PBN_Export_Queue.objects.filter(
            zakonczono_pomyslnie=True
        ).count()
        context["pending_count"] = PBN_Export_Queue.objects.filter(
            zakonczono_pomyslnie=None
        ).count()
        # Add current sort parameter
        context["current_sort"] = self.request.GET.get("sort", "-ostatnia_aktualizacja")
        return context


class PBNExportQueueTableView(
    LoginRequiredMixin, PBNExportQueuePermissionMixin, ListView
):
    """Table-only view for HTMX auto-refresh"""

    model = PBN_Export_Queue
    template_name = "pbn_export_queue/pbn_export_queue_table.html"
    context_object_name = "export_queue_items"
    paginate_by = 25

    def _filter_by_success_status(self, queryset):
        """Filter queryset by zakonczono_pomyslnie parameter."""
        success_filter = self.request.GET.get("zakonczono_pomyslnie")
        if success_filter == "true":
            return queryset.filter(zakonczono_pomyslnie=True)
        elif success_filter == "false":
            return queryset.filter(zakonczono_pomyslnie=False)
        elif success_filter == "none":
            return queryset.filter(zakonczono_pomyslnie=None)
        return queryset

    def _find_matching_record_ids(self, queryset, search_query):
        """Find record IDs that match search query in their title fields."""
        matching_ids = []

        for item in queryset.select_related("content_type"):
            if not item.rekord_do_wysylki:
                continue

            try:
                record = item.rekord_do_wysylki
                # Check if record has title fields
                if hasattr(record, "tytul_oryginalny") and record.tytul_oryginalny:
                    if search_query.lower() in record.tytul_oryginalny.lower():
                        matching_ids.append(item.pk)
                elif (
                    hasattr(record, "opis_bibliograficzny_cache")
                    and record.opis_bibliograficzny_cache
                ):
                    if (
                        search_query.lower()
                        in record.opis_bibliograficzny_cache.lower()
                    ):
                        matching_ids.append(item.pk)
            except BaseException:
                pass

        return matching_ids

    def _apply_search_filter(self, queryset):
        """Apply search query filter to queryset."""
        search_query = self.request.GET.get("q")
        if not search_query:
            return queryset

        from django.db.models import Q

        # Search in komunikat field which contains publication info
        queryset = queryset.filter(Q(komunikat__icontains=search_query))

        # Additionally filter by checking the actual related objects
        matching_ids = self._find_matching_record_ids(queryset, search_query)

        # If we found matching IDs, filter by them
        if matching_ids:
            queryset = queryset.filter(
                Q(pk__in=matching_ids) | Q(komunikat__icontains=search_query)
            )

        return queryset

    def _apply_sorting(self, queryset):
        """Apply sorting to queryset based on sort parameter."""
        sort_by = self.request.GET.get("sort", "-ostatnia_aktualizacja")
        allowed_sorts = {
            "pk": "pk",
            "-pk": "-pk",
            "zamowiono": "zamowiono",
            "-zamowiono": "-zamowiono",
            "ostatnia_aktualizacja": "ostatnia_aktualizacja_sort",
            "-ostatnia_aktualizacja": "-ostatnia_aktualizacja_sort",
            "ilosc_prob": "ilosc_prob",
            "-ilosc_prob": "-ilosc_prob",
            "zakonczono_pomyslnie": "zakonczono_pomyslnie",
            "-zakonczono_pomyslnie": "-zakonczono_pomyslnie",
        }
        if sort_by in allowed_sorts:
            queryset = queryset.order_by(allowed_sorts[sort_by])
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()

        # Annotate with ostatnia_aktualizacja for sorting
        queryset = queryset.annotate(
            ostatnia_aktualizacja_sort=Coalesce(
                F("wysylke_zakonczono"), F("wysylke_podjeto"), F("zamowiono")
            )
        )

        # Apply filters
        queryset = self._filter_by_success_status(queryset)
        queryset = self._apply_search_filter(queryset)
        queryset = self._apply_sorting(queryset)

        return queryset.select_related("zamowil", "content_type")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_filter"] = self.request.GET.get("zakonczono_pomyslnie", "all")
        context["search_query"] = self.request.GET.get("q", "")
        # Add count of error records for the resend button
        context["error_count"] = PBN_Export_Queue.objects.filter(
            zakonczono_pomyslnie=False
        ).count()
        # Add count of waiting records for the resend button
        context["waiting_count"] = PBN_Export_Queue.objects.filter(
            retry_after_user_authorised=True
        ).count()
        # Add count of never sent records for the wake up button
        context["never_sent_count"] = PBN_Export_Queue.objects.filter(
            wysylke_podjeto=None,
            wysylke_zakonczono=None,
        ).count()
        # Add counts for filter buttons
        context["total_count"] = PBN_Export_Queue.objects.count()
        context["success_count"] = PBN_Export_Queue.objects.filter(
            zakonczono_pomyslnie=True
        ).count()
        context["pending_count"] = PBN_Export_Queue.objects.filter(
            zakonczono_pomyslnie=None
        ).count()
        # Add current sort parameter
        context["current_sort"] = self.request.GET.get("sort", "-ostatnia_aktualizacja")
        return context


class PBNExportQueueDetailView(
    LoginRequiredMixin, PBNExportQueuePermissionMixin, DetailView
):
    """DetailView for PBN Export Queue showing logs and action buttons"""

    model = PBN_Export_Queue
    template_name = "pbn_export_queue/pbn_export_queue_detail.html"
    context_object_name = "export_queue_item"

    def get_queryset(self):
        return super().get_queryset().select_related("zamowil", "content_type")

    def parse_komunikat_links(self, komunikat):
        """Parse the komunikat field to extract and format links"""
        if not komunikat:
            return None

        # Find the SentData link
        sentdata_match = re.search(
            r'href="(/admin/pbn_api/sentdata/\d+/change/)"', komunikat
        )

        links = {}
        if sentdata_match:
            links["sentdata_url"] = sentdata_match.group(1)

            # Try to extract PBN publication ID from the komunikat
            # Looking for patterns like "PBN ID: xxx" or similar
            pbn_match = re.search(r"publication/([a-f0-9-]+)", komunikat)
            if pbn_match:
                links["pbn_uid"] = pbn_match.group(1)
                links["pbn_url"] = (
                    f"https://pbn.nauka.gov.pl/works/publication/{pbn_match.group(1)}"
                )

        # Check if this was successful
        if "Wysłano poprawnie" in komunikat:
            links["success"] = True
        else:
            links["success"] = False

        # Make the komunikat HTML-safe but preserve existing HTML
        links["formatted_komunikat"] = mark_safe(komunikat.replace("\n", "<br>"))

        return links

    def _build_helpdesk_email(
        self,
        sent_data,
        record_title,
        json_data,
    ):
        """Build helpdesk email content using template and parsed error details."""
        # Parse error details
        error_info = _parse_error_details(sent_data)

        # Format submission date
        submitted_date = _format_submission_date(sent_data)

        # Get user info
        user_info = _get_user_info(self.request.user)

        # Format email using template
        return HELPDESK_EMAIL_TEMPLATE.format(
            record_title_short=record_title[:100],
            user_email=user_info["user_email"],
            submitted_date=submitted_date,
            error_code=error_info["error_code"],
            error_endpoint=error_info["error_endpoint"],
            record_title=record_title,
            error_details=error_info["error_details"],
            queue_pk=self.object.pk,
            content_type=self.object.content_type,
            ilosc_prob=self.object.ilosc_prob,
            json_data=json_data,
            user_name=user_info["user_name"],
        )

    def _extract_error_details_from_pbn_error(self, pbn_error):
        """Extract error details from parsed PBN error dict."""
        if pbn_error.get("error_details_json"):
            return pbn_error["error_details_json"]
        elif pbn_error.get("error_message"):
            return pbn_error["error_message"]
        elif pbn_error.get("raw_error"):
            return pbn_error["raw_error"]
        return None

    def _extract_error_from_exception(self, sent_data):
        """Extract error code and details from sent_data.exception."""
        if not sent_data.exception:
            return None, None

        pbn_error = parse_pbn_api_error(sent_data.exception)
        if not pbn_error.get("is_pbn_api_error"):
            return None, None

        error_code = pbn_error.get("error_code")
        error_details = self._extract_error_details_from_pbn_error(pbn_error)

        return error_code, error_details

    def _extract_error_from_komunikat(self):
        """Extract error code and details from komunikat field."""
        if not self.object.komunikat:
            return None, None

        error_line = extract_pbn_error_from_komunikat(self.object.komunikat)
        if not error_line:
            return None, None

        pbn_error = parse_pbn_api_error(error_line)
        if not pbn_error.get("is_pbn_api_error"):
            return None, None

        error_code = pbn_error.get("error_code")
        error_details = self._extract_error_details_from_pbn_error(pbn_error)

        return error_code, error_details

    def _build_ai_prompt(
        self,
        sent_data,
        record_title,
        json_data,
    ):
        """Build AI prompt using template and parsed error details."""
        # Try to get error from sent_data.exception first
        ai_error_code, ai_error_details = self._extract_error_from_exception(sent_data)

        # If still no error details, try to extract from komunikat
        if not ai_error_details:
            komunikat_code, komunikat_details = self._extract_error_from_komunikat()
            if komunikat_code:
                ai_error_code = ai_error_code or komunikat_code
            if komunikat_details:
                ai_error_details = komunikat_details

        # Fallback to api_response_status for error code
        if not ai_error_code and sent_data.api_response_status:
            ai_error_code = sent_data.api_response_status

        # Use defaults if still not found
        ai_error_code = ai_error_code or "Brak kodu błędu"
        ai_error_details = ai_error_details or "Brak szczegółów błędu"

        # Format AI prompt using template
        return AI_PROMPT_TEMPLATE.format(
            json_data=json_data,
            error_code=ai_error_code,
            error_details=ai_error_details,
            record_title=record_title,
        )

    def _add_sent_data_context(self, context):
        """Add SentData related context if it exists."""
        try:
            from pbn_api.models.sentdata import SentData

            sent_data = SentData.objects.get(
                content_type=self.object.content_type,
                object_id=self.object.object_id,
            )
            context["sent_data"] = sent_data

            if sent_data.pbn_uid_id:
                context["pbn_publication_url"] = (
                    f"https://pbn.nauka.gov.pl/works/publication/{sent_data.pbn_uid_id}"
                )

            # Parse PBN API error if this was a failed submission
            if self.object.zakonczono_pomyslnie is False and sent_data.exception:
                context["pbn_error_info"] = parse_pbn_api_error(sent_data.exception)

            return sent_data

        except SentData.DoesNotExist:
            return None

    def _add_pbn_error_from_komunikat(self, context):
        """Add PBN error info extracted from komunikat if not already in context."""
        if (
            self.object.zakonczono_pomyslnie is False
            and "pbn_error_info" not in context
            and self.object.komunikat
        ):
            error_line = extract_pbn_error_from_komunikat(self.object.komunikat)
            if error_line:
                context["pbn_error_info"] = parse_pbn_api_error(error_line)

    def _add_record_admin_url(self, context):
        """Add admin URL for the related record if it exists."""
        if not self.object.rekord_do_wysylki:
            return

        from django.urls import reverse

        content_type = self.object.content_type
        if content_type:
            try:
                admin_url = reverse(
                    f"admin:{content_type.app_label}_{content_type.model}_change",
                    args=[self.object.object_id],
                )
                context["record_admin_url"] = admin_url
            except BaseException:
                # If URL pattern doesn't exist, skip it
                pass

    def _add_clipboard_data(self, context, sent_data):
        """Pre-fetch clipboard data for Safari compatibility."""
        if not sent_data:
            return

        # 1. JSON data for clipboard
        context["json_data"] = json.dumps(
            sent_data.data_sent, indent=2, ensure_ascii=False
        )

        # 2. Get record title
        record_title = _get_record_title(self.object.rekord_do_wysylki)

        # 3. Build helpdesk email content
        context["helpdesk_email"] = self._build_helpdesk_email(
            sent_data,
            record_title,
            context["json_data"],
        )

        # 4. Build AI prompt
        context["ai_prompt"] = self._build_ai_prompt(
            sent_data,
            record_title,
            context["json_data"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Parse komunikat for links if the record was sent successfully
        if self.object.komunikat:
            context["parsed_links"] = self.parse_komunikat_links(self.object.komunikat)

        # Try to get the related SentData and add to context
        sent_data = self._add_sent_data_context(context)

        # If no SentData or no exception in SentData, try to extract error from komunikat
        self._add_pbn_error_from_komunikat(context)

        # Generate admin URL for the record if it exists
        self._add_record_admin_url(context)

        # Pre-fetch clipboard data if SentData exists
        self._add_clipboard_data(context, sent_data)

        return context


@login_required
@require_POST
def resend_to_pbn(request, pk):
    """View to resend an export queue item to PBN (combines prepare and send)"""
    if not (
        request.user.is_staff
        or request.user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
    ):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(
            reverse_lazy("pbn_export_queue:export-queue-detail", args=[pk])
        )

    queue_item = get_object_or_404(PBN_Export_Queue, pk=pk)
    # First prepare for resend
    queue_item.prepare_for_resend(
        user=request.user, message_suffix=f" przez {request.user}"
    )
    # Then trigger the send
    queue_item.sprobuj_wyslac_do_pbn()
    messages.success(request, "Przygotowano i zlecono ponowną wysyłkę do PBN.")
    return HttpResponseRedirect(
        reverse_lazy("pbn_export_queue:export-queue-detail", args=[pk])
    )


# Keep old views for backward compatibility but they won't be used in new UI
@login_required
@require_POST
def prepare_for_resend(request, pk):
    """View to prepare an export queue item for resending - DEPRECATED"""
    if not (
        request.user.is_staff
        or request.user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
    ):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(
            reverse_lazy("pbn_export_queue:export-queue-detail", args=[pk])
        )

    queue_item = get_object_or_404(PBN_Export_Queue, pk=pk)
    queue_item.prepare_for_resend(
        user=request.user, message_suffix=f" przez {request.user}"
    )
    messages.success(request, "Przygotowano rekord do ponownej wysyłki.")
    return HttpResponseRedirect(
        reverse_lazy("pbn_export_queue:export-queue-detail", args=[pk])
    )


@login_required
@require_POST
def try_send_to_pbn(request, pk):
    """View to trigger sending an export queue item to PBN - DEPRECATED"""
    if not (
        request.user.is_staff
        or request.user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
    ):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(
            reverse_lazy("pbn_export_queue:export-queue-detail", args=[pk])
        )

    queue_item = get_object_or_404(PBN_Export_Queue, pk=pk)
    queue_item.sprobuj_wyslac_do_pbn()
    messages.success(request, "Zlecono ponowną wysyłkę do PBN.")
    return HttpResponseRedirect(
        reverse_lazy("pbn_export_queue:export-queue-detail", args=[pk])
    )


@login_required
@require_POST
def resend_all_waiting(request):
    """View to resend all export queue items waiting for authorization"""
    if not (
        request.user.is_staff
        or request.user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
    ):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Get items waiting for authorization (retry_after_user_authorised=True) with limit
    waiting_items = PBN_Export_Queue.objects.filter(retry_after_user_authorised=True)[
        :100
    ]  # Limit do 100

    if not waiting_items:
        messages.warning(request, "Brak rekordów oczekujących na autoryzację.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Process each waiting item
    from django.core.cache import cache

    from pbn_export_queue.tasks import LOCK_PREFIX

    count = 0
    skipped = 0
    for queue_item in waiting_items:
        try:
            # Sprawdź czy nie ma już locka dla tego elementu
            lock_key = f"{LOCK_PREFIX}{queue_item.pk}"
            if not cache.get(lock_key):
                # Prepare for resend
                queue_item.prepare_for_resend(
                    user=request.user,
                    message_suffix=f" przez {request.user} (masowa wysyłka oczekujących)",
                )
                # Trigger the send
                queue_item.sprobuj_wyslac_do_pbn()
                count += 1
            else:
                skipped += 1
        except Exception:
            # Log the error but continue processing other items
            rollbar.report_exc_info(sys.exc_info())
            continue

    msg = f"Przygotowano i zlecono ponowną wysyłkę {count} rekordów oczekujących na autoryzację."
    if skipped > 0:
        msg += f" ({skipped} pominięto - już w trakcie przetwarzania)"

    messages.success(request, msg)
    return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))


@login_required
@require_POST
def resend_all_errors(request):
    """View to resend all export queue items with error status"""
    if not (
        request.user.is_staff
        or request.user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
    ):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Get items with errors (zakonczono_pomyslnie=False) with limit
    error_items = PBN_Export_Queue.objects.filter(zakonczono_pomyslnie=False)[
        :100
    ]  # Limit do 100

    if not error_items:
        messages.warning(request, "Brak rekordów z błędami do ponownej wysyłki.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Process each error item
    from django.core.cache import cache

    from pbn_export_queue.tasks import LOCK_PREFIX

    count = 0
    skipped = 0
    for queue_item in error_items:
        try:
            # Sprawdź czy nie ma już locka dla tego elementu
            lock_key = f"{LOCK_PREFIX}{queue_item.pk}"
            if not cache.get(lock_key):
                # Prepare for resend
                queue_item.prepare_for_resend(
                    user=request.user,
                    message_suffix=f" przez {request.user} (masowa wysyłka błędów)",
                )
                # Trigger the send
                queue_item.sprobuj_wyslac_do_pbn()
                count += 1
            else:
                skipped += 1
        except Exception:
            # Log the error but continue processing other items
            rollbar.report_exc_info(sys.exc_info())
            continue

    msg = f"Przygotowano i zlecono ponowną wysyłkę {count} rekordów z błędami."
    if skipped > 0:
        msg += f" ({skipped} pominięto - już w trakcie przetwarzania)"

    messages.success(request, msg)
    return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))


@login_required
@require_POST
def wake_up_queue(request):
    """View to wake up and start sending all export queue items that were never attempted"""
    if not (
        request.user.is_staff
        or request.user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
    ):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Get items that were never attempted to send (with limit)
    # (wysylke_podjeto=None means sending was never started)
    never_sent_items = PBN_Export_Queue.objects.filter(
        wysylke_podjeto=None,
        wysylke_zakonczono=None,
    )[:100]  # Limit do 100 rekordów na raz

    if not never_sent_items:
        messages.warning(request, "Brak rekordów oczekujących na pierwszą wysyłkę.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Process each never-sent item
    from django.core.cache import cache

    from pbn_export_queue.tasks import LOCK_PREFIX, task_sprobuj_wyslac_do_pbn

    count = 0
    skipped = 0
    for queue_item in never_sent_items:
        try:
            # Sprawdź czy nie ma już locka dla tego elementu
            lock_key = f"{LOCK_PREFIX}{queue_item.pk}"
            if not cache.get(lock_key):
                # Brak locka - można wysyłać
                task_sprobuj_wyslac_do_pbn.delay(queue_item.pk)
                count += 1
            else:
                skipped += 1
        except Exception:
            # Log the error but continue processing other items
            rollbar.report_exc_info(sys.exc_info())
            continue

    msg = f"Obudzono wysyłkę dla {count} rekordów które nigdy nie były wysyłane."
    if skipped > 0:
        msg += f" ({skipped} pominięto - już w trakcie przetwarzania)"

    messages.success(request, msg)
    return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))


class PBNExportQueueCountsView(LoginRequiredMixin, PBNExportQueuePermissionMixin, View):
    """JSON view that returns current counts for filter buttons"""

    def get(self, request, *args, **kwargs):
        """Return JSON response with current counts"""
        counts = {
            "total_count": PBN_Export_Queue.objects.count(),
            "success_count": PBN_Export_Queue.objects.filter(
                zakonczono_pomyslnie=True
            ).count(),
            "error_count": PBN_Export_Queue.objects.filter(
                zakonczono_pomyslnie=False
            ).count(),
            "pending_count": PBN_Export_Queue.objects.filter(
                zakonczono_pomyslnie=None
            ).count(),
            "waiting_count": PBN_Export_Queue.objects.filter(
                retry_after_user_authorised=True
            ).count(),
        }
        return JsonResponse(counts)
