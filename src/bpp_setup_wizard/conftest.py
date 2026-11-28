"""Wspólne fixtury testów kreatora pierwszego uruchomienia."""

import pytest


@pytest.fixture(autouse=True)
def enable_first_run_wizard_middleware(settings):
    """Re-enable the first-run wizard middleware for the wizard tests.

    `settings/test.py` strips it from MIDDLEWARE globally; we want it
    back for these specific tests of the wizard flow.
    """
    middleware = list(settings.MIDDLEWARE)
    if "bpp_setup_wizard.middleware.BppFirstRunWizardMiddleware" not in middleware:
        try:
            auth_index = middleware.index(
                "django.contrib.auth.middleware.AuthenticationMiddleware"
            )
            middleware.insert(
                auth_index + 1,
                "bpp_setup_wizard.middleware.BppFirstRunWizardMiddleware",
            )
        except ValueError:
            middleware.insert(
                0, "bpp_setup_wizard.middleware.BppFirstRunWizardMiddleware"
            )
        settings.MIDDLEWARE = middleware
