from django.apps import AppConfig


class BppSetupWizardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bpp_setup_wizard"
    verbose_name = "BPP Setup Wizard"

    def ready(self):
        from first_run_wizard import registry
        from first_run_wizard.registry import StepAlreadyRegistered

        from bpp_setup_wizard.steps import PbnSetupStep, UczelniaSetupStep

        for step in (UczelniaSetupStep(), PbnSetupStep()):
            try:
                registry.register(step)
            except StepAlreadyRegistered:
                pass  # ready() bywa wołane ponownie (np. w testach)
