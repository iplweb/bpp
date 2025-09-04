# Create your views here.
import sentry_sdk
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView, RedirectView

from .client import OAuthMixin
from .exceptions import AuthenticationConfigurationError, AuthenticationResponseError
from .models import PBN_Export_Queue
from .signals import token_set_successfully

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from django.utils import timezone

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Uczelnia


class TokenRedirectPage(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        import base64
        import json

        from django.utils import timezone

        uczelnia = Uczelnia.objects.get_default()

        # Get the original page from 'next' parameter or HTTP referer
        next_url = self.request.GET.get("next")
        if not next_url:
            # Fall back to HTTP referer if no next parameter
            next_url = self.request.META.get("HTTP_REFERER", "/")

        # Create state data
        state_data = {"originalPage": next_url, "timestamp": timezone.now().timestamp()}

        # Encode state as base64 JSON
        state = base64.b64encode(json.dumps(state_data).encode()).decode()

        return OAuthMixin.get_auth_url(
            uczelnia.pbn_api_root, uczelnia.pbn_app_name, state=state
        )


class TokenLandingPage(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        import base64
        import json

        ott = self.request.GET.get("ott")
        state = self.request.GET.get("state")

        if not ott:
            raise HttpResponseBadRequest("Brak parametru OTT lub pusty")

        uczelnia = Uczelnia.objects.get_default()

        # Default redirect URL
        redirect_url = "/"

        # Try to decode state parameter if present
        if state:
            try:
                # Decode base64 state
                state_json = base64.b64decode(state).decode()
                state_data = json.loads(state_json)
                redirect_url = state_data.get("originalPage", "/")
            except (ValueError, json.JSONDecodeError, KeyError):
                # If state decoding fails, fall back to default
                pass

        try:
            user_token = OAuthMixin.get_user_token(
                uczelnia.pbn_api_root,
                uczelnia.pbn_app_name,
                uczelnia.pbn_app_token,
                ott,
            )
            user = self.request.user
            user.pbn_token = user_token
            user.pbn_token_updated = timezone.now()
            user.save()

            transaction.on_commit(lambda: token_set_successfully.send(sender=user))
            from pbn_api.tasks import kolejka_ponow_wysylke_prac_po_zalogowaniu

            transaction.on_commit(
                lambda user_pk=user.pk: kolejka_ponow_wysylke_prac_po_zalogowaniu.delay(
                    user_pk
                )
            )

            messages.info(
                self.request, "Autoryzacja w PBN API przeprowadzona pomyślnie."
            )

        except AuthenticationConfigurationError as e:
            messages.error(
                self.request, f"Nie można autoryzować zalogowania do PBN - {e}"
            )
            sentry_sdk.capture_exception(e)

        except AuthenticationResponseError as e:
            messages.error(
                self.request,
                "Bez możliwości autoryzacji - błąd odpowiedzi z serwera "
                "autoryzacyjnego. Ze względów bezpieczeństwa wyświetlenie niewskazane - "
                "błąd przekazano do administratora serwisu.  ",
            )
            sentry_sdk.capture_exception(e)

        return redirect_url


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
    template_name = "pbn_api/pbn_export_queue_list.html"
    context_object_name = "export_queue_items"
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by zakonczono_pomyslnie if parameter provided
        success_filter = self.request.GET.get("zakonczono_pomyslnie")
        if success_filter == "true":
            queryset = queryset.filter(zakonczono_pomyslnie=True)
        elif success_filter == "false":
            queryset = queryset.filter(zakonczono_pomyslnie=False)
        elif success_filter == "none":
            queryset = queryset.filter(zakonczono_pomyslnie=None)

        return queryset.select_related("zamowil", "content_type")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_filter"] = self.request.GET.get("zakonczono_pomyslnie", "all")
        return context


class PBNExportQueueTableView(
    LoginRequiredMixin, PBNExportQueuePermissionMixin, ListView
):
    """Table-only view for HTMX auto-refresh"""

    model = PBN_Export_Queue
    template_name = "pbn_api/pbn_export_queue_table.html"
    context_object_name = "export_queue_items"
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by zakonczono_pomyslnie if parameter provided
        success_filter = self.request.GET.get("zakonczono_pomyslnie")
        if success_filter == "true":
            queryset = queryset.filter(zakonczono_pomyslnie=True)
        elif success_filter == "false":
            queryset = queryset.filter(zakonczono_pomyslnie=False)
        elif success_filter == "none":
            queryset = queryset.filter(zakonczono_pomyslnie=None)

        return queryset.select_related("zamowil", "content_type")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_filter"] = self.request.GET.get("zakonczono_pomyslnie", "all")
        return context


import re

from django.utils.safestring import mark_safe


class PBNExportQueueDetailView(
    LoginRequiredMixin, PBNExportQueuePermissionMixin, DetailView
):
    """DetailView for PBN Export Queue showing logs and action buttons"""

    model = PBN_Export_Queue
    template_name = "pbn_api/pbn_export_queue_detail.html"
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Parse komunikat for links if the record was sent successfully
        if self.object.komunikat:
            context["parsed_links"] = self.parse_komunikat_links(self.object.komunikat)

        # Try to get the related SentData if it exists
        if self.object.zakonczono_pomyslnie:
            try:
                from pbn_api.models.sentdata import SentData

                sent_data = SentData.objects.get(
                    content_type=self.object.content_type,
                    object_id=self.object.object_id,
                )
                context["sent_data"] = sent_data
                if sent_data.pbn_uid_id:
                    # pbn_uid is a ForeignKey to Publication, so we need to use pbn_uid_id or pbn_uid.pbn_uid
                    context["pbn_publication_url"] = (
                        f"https://pbn.nauka.gov.pl/works/publication/{sent_data.pbn_uid_id}"
                    )
            except SentData.DoesNotExist:
                pass

        # Generate admin URL for the record if it exists
        if self.object.rekord_do_wysylki:
            from django.urls import reverse

            content_type = self.object.content_type
            if content_type:
                try:
                    # Generate admin change URL for the specific model
                    admin_url = reverse(
                        f"admin:{content_type.app_label}_{content_type.model}_change",
                        args=[self.object.object_id],
                    )
                    context["record_admin_url"] = admin_url
                except BaseException:
                    # If URL pattern doesn't exist, skip it
                    pass

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
            reverse_lazy("pbn_api:export-queue-detail", args=[pk])
        )

    queue_item = get_object_or_404(PBN_Export_Queue, pk=pk)
    # First prepare for resend
    queue_item.prepare_for_resend(
        user=request.user, message_suffix=f" przez {request.user}"
    )
    # Then trigger the send
    queue_item.sprobuj_wyslac_do_pbn()
    messages.success(request, "Przygotowano i zlecono ponowną wysyłkę do PBN.")
    return HttpResponseRedirect(reverse_lazy("pbn_api:export-queue-detail", args=[pk]))


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
            reverse_lazy("pbn_api:export-queue-detail", args=[pk])
        )

    queue_item = get_object_or_404(PBN_Export_Queue, pk=pk)
    queue_item.prepare_for_resend(
        user=request.user, message_suffix=f" przez {request.user}"
    )
    messages.success(request, "Przygotowano rekord do ponownej wysyłki.")
    return HttpResponseRedirect(reverse_lazy("pbn_api:export-queue-detail", args=[pk]))


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
            reverse_lazy("pbn_api:export-queue-detail", args=[pk])
        )

    queue_item = get_object_or_404(PBN_Export_Queue, pk=pk)
    queue_item.sprobuj_wyslac_do_pbn()
    messages.success(request, "Zlecono ponowną wysyłkę do PBN.")
    return HttpResponseRedirect(reverse_lazy("pbn_api:export-queue-detail", args=[pk]))
