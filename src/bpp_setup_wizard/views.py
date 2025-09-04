from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import FormView

from .forms import SetupAdminForm, UczelniaSetupForm

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required

from django.utils.decorators import method_decorator

from bpp.models import Uczelnia

BppUser = get_user_model()


class SetupWizardView(FormView):
    """Main setup wizard view for initial system configuration."""

    template_name = "bpp_setup_wizard/setup.html"
    form_class = SetupAdminForm

    def dispatch(self, request, *args, **kwargs):
        # Check if setup is already complete (users exist)
        if BppUser.objects.exists():
            messages.info(
                request,
                "System został już skonfigurowany. Kreator konfiguracji jest niedostępny.",
            )
            return redirect("/")

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Create the admin user
        user = form.save()

        # Log the user in automatically using the Django ModelBackend
        # Since this is a fresh setup, we use the standard backend
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")

        messages.success(
            self.request,
            f"Administrator '{user.username}' został utworzony pomyślnie. "
            f"Zostałeś automatycznie zalogowany.",
        )

        # Redirect to main page (which will trigger Uczelnia setup if needed)
        return redirect("/")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Kreator konfiguracji BPP"
        context["subtitle"] = "Konfiguracja początkowa systemu"
        return context


class SetupStatusView(View):
    """View to check if setup is required."""

    def get(self, request):
        needs_setup = not BppUser.objects.exists()

        return render(
            request,
            "bpp_setup_wizard/status.html",
            {"needs_setup": needs_setup, "user_count": BppUser.objects.count()},
        )


@method_decorator(login_required, name="dispatch")
class UczelniaSetupView(FormView):
    """Setup wizard for Uczelnia (University) configuration."""

    template_name = "bpp_setup_wizard/uczelnia_setup.html"
    form_class = UczelniaSetupForm

    def dispatch(self, request, *args, **kwargs):
        # Check if Uczelnia is already configured
        if Uczelnia.objects.exists():
            messages.info(request, "Uczelnia została już skonfigurowana.")
            return redirect("/")

        # Check if user is authenticated and is superuser
        if not request.user.is_superuser:
            messages.error(request, "Tylko administrator może skonfigurować uczelnię.")
            return redirect("/")

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Create the Uczelnia
        uczelnia = form.save()

        messages.success(
            self.request,
            f"Uczelnia '{uczelnia.nazwa}' została skonfigurowana pomyślnie.",
        )

        # Redirect to main page
        return redirect("/")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Konfiguracja uczelni"
        context["subtitle"] = "Podstawowe dane instytucji"
        return context
