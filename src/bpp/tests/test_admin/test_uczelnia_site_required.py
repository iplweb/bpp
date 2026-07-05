"""Multi-hosted: admin-owy formularz Uczelni wymaga jawnie pola ``site``
(domena), z przyjaznym komunikatem.

Na poziomie DB ``site`` jest już NOT NULL (migracja 0417), ale domyślny
komunikat Django ("To pole jest wymagane.") nie tłumaczy, DLACZEGO — w trybie
multi-hosted to Site wiąże uczelnię z domeną. Forma dostarcza komunikat
dziedzinowy.
"""

import pytest
from django.forms import modelform_factory

from bpp.admin.uczelnia import UczelniaAdminForm
from bpp.models import Uczelnia


def _form_with_site():
    return modelform_factory(
        Uczelnia,
        form=UczelniaAdminForm,
        fields=["nazwa", "skrot", "site", "theme_name"],
    )


@pytest.mark.django_db
def test_uczelnia_form_site_wymagany_przyjazny_komunikat():
    """Brak ``site`` → forma niewalidna, a komunikat wspomina o domenie/Site."""
    form = _form_with_site()(data={"nazwa": "Testowa", "skrot": "T"})

    assert not form.is_valid()
    assert "site" in form.errors
    assert "domen" in " ".join(form.errors["site"]).lower()
