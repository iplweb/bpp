"""FD#528: „Moje wartości domyślne" w formularzu raportu autorów → błąd 500.

Klasa formularza raportu jest budowana dynamicznie (``form_class_dla``) pod
``__module__ = "nowe_raporty.forms_dynamiczne"``. django-formdefaults odtwarza
klasę z tej nazwy przy otwieraniu okna wartości domyślnych — a modułu nie było,
więc import kończył się ``ModuleNotFoundError`` → 500. Dotyczyło każdego
raportu z ``nowe_raporty`` na każdej instalacji, nie tylko UAFM.
"""

import pytest
from django.urls import reverse
from formdefaults.models import FormFieldDefaultValue, FormRepresentation
from model_bakery import baker

from bpp.models import Autor
from nowe_raporty.forms import form_class_dla
from nowe_raporty.models import DefinicjaRaportu
from nowe_raporty.seeding import seed_default_reports

FULL_NAME = "nowe_raporty.forms_dynamiczne.RaportForm_raport_autorow"


def _otworz_formularz(client):
    seed_default_reports()
    url = reverse("nowe_raporty:raport_form", args=["raport-autorow"])
    res = client.get(url)
    assert res.status_code == 200
    # formularz rejestruje FormRepresentation i pokazuje przycisk
    assert FormRepresentation.objects.filter(full_name=FULL_NAME).exists()
    edit_url = reverse("formdefaults:user-edit", args=[FULL_NAME])
    assert edit_url in res.content.decode()
    return edit_url


@pytest.mark.django_db
def test_fd528_moje_wartosci_domyslne_otwiera_sie(admin_client, uczelnia):
    edit_url = _otworz_formularz(admin_client)

    res = admin_client.get(edit_url)

    assert res.status_code == 200
    assert "sortowanie" in res.content.decode()


@pytest.mark.django_db
def test_fd528_moje_wartosci_domyslne_zapisuja_sie(
    admin_client, admin_user, uczelnia
):
    edit_url = _otworz_formularz(admin_client)

    res = admin_client.post(
        edit_url, {"_override_od_roku": "on", "od_roku": "2019"}
    )

    assert res.status_code == 200
    v = FormFieldDefaultValue.objects.get(
        parent__full_name=FULL_NAME, field__name="od_roku", user=admin_user
    )
    assert v.value == 2019


@pytest.mark.django_db
def test_fd528_modul_odtwarza_klase_po_nazwie():
    from formdefaults.util import get_python_class_by_name

    d = baker.make(
        DefinicjaRaportu, slug="moj-raport", poziom=DefinicjaRaportu.POZIOM_AUTOR
    )
    klasa = get_python_class_by_name(
        "nowe_raporty.forms_dynamiczne.RaportForm_moj_raport"
    )
    assert klasa.__name__ == form_class_dla(d).__name__
    assert "obiekt" in klasa.base_fields


@pytest.mark.django_db
def test_fd528_brak_definicji_to_attribute_error():
    from nowe_raporty import forms_dynamiczne

    with pytest.raises(AttributeError):
        forms_dynamiczne.RaportForm_nie_ma_takiego  # noqa: B018
    with pytest.raises(AttributeError):
        forms_dynamiczne.cokolwiek  # noqa: B018


@pytest.mark.django_db
def test_fd528_nieaktualny_autor_w_wartosciach_domyslnych_nie_wywala(
    admin_client, admin_user, uczelnia
):
    """Zapisany domyślny ``obiekt`` wskazujący na usuniętego autora nie
    może wywracać ani formularza raportu, ani okna wartości domyślnych."""
    edit_url = _otworz_formularz(admin_client)
    autor = baker.make(Autor)
    admin_client.post(edit_url, {"_override_obiekt": "on", "obiekt": autor.pk})
    assert FormFieldDefaultValue.objects.filter(
        parent__full_name=FULL_NAME, field__name="obiekt", user=admin_user
    ).exists()
    autor.delete()

    assert admin_client.get(edit_url).status_code == 200
    res = admin_client.get(
        reverse("nowe_raporty:raport_form", args=["raport-autorow"])
    )
    assert res.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("widok", ["formdefaults:user-edit", "formdefaults:system-edit"])
def test_fd528_nieaktualna_klasa_formularza_daje_404(admin_client, widok):
    """Raport po zmianie sluga / usunięciu definicji: zapisany ``full_name``
    wskazuje na klasę, której już nie ma → 404, nie 500."""
    for full_name in (
        "nowe_raporty.forms_dynamiczne.RaportForm_usuniety_raport",
        "nie_ma.takiego_modulu.Formularz",
    ):
        FormRepresentation.objects.create(full_name=full_name, label=full_name)
        res = admin_client.get(reverse(widok, args=[full_name]))
        assert res.status_code == 404


@pytest.mark.django_db
def test_fd528_lata_nie_znikaja_przy_kolejnym_snapshocie(admin_user, uczelnia):
    """formdefaults pomija pola z wywoływalnym ``initial`` — i przy KAŻDYM
    kolejnym odświeżeniu reprezentacji (co 60 s na proces) KASUJE je z bazy
    razem z zapisanymi wartościami użytkowników. „Od roku"/„Do roku" znikały
    więc co drugie odświeżenie z okna „Moje wartości domyślne", a zapisane
    tam lata przepadały."""
    from formdefaults import core

    seed_default_reports()
    klasa = form_class_dla(DefinicjaRaportu.objects.get(slug="raport-autorow"))

    def snapshot():
        core.clear_snapshot_cache()  # jak po upływie TTL / w nowym procesie
        core.get_form_defaults(klasa(), "Raport autorów", user=admin_user)
        rep = FormRepresentation.objects.get(full_name=FULL_NAME)
        return rep, set(rep.fields_set.values_list("name", flat=True))

    rep, pola = snapshot()
    assert {"od_roku", "do_roku"} <= pola
    FormFieldDefaultValue.objects.update_or_create(
        parent=rep,
        field=rep.fields_set.get(name="od_roku"),
        user=admin_user,
        defaults={"value": 2019, "is_auto_snapshot": False},
    )

    for _ in range(3):
        rep, pola = snapshot()
        assert {"od_roku", "do_roku"} <= pola
        assert FormFieldDefaultValue.objects.get(
            parent=rep, field__name="od_roku", user=admin_user
        ).value == 2019
