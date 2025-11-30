"""Detail view for PBN export queue."""

import json
import re

from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.safestring import mark_safe
from django.views.generic import DetailView

from pbn_export_queue.models import PBN_Export_Queue

from .constants import AI_PROMPT_TEMPLATE, HELPDESK_EMAIL_TEMPLATE
from .mixins import PBNExportQueuePermissionMixin
from .utils import (
    extract_pbn_error_from_komunikat,
    format_submission_date,
    get_record_title,
    get_user_info,
    parse_error_details,
    parse_pbn_api_error,
)


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
        error_info = parse_error_details(sent_data)

        # Format submission date
        submitted_date = format_submission_date(sent_data)

        # Get user info
        user_info = get_user_info(self.request.user)

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
        record_title = get_record_title(self.object.rekord_do_wysylki)

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
