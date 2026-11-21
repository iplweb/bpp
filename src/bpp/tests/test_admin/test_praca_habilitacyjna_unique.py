"""Formularz admina musi łapać drugą ŻYWĄ habilitację tego samego autora.

Do fazy 03 pilnowało tego ``OneToOneField`` — Django sprawdzał to zwykłym
``validate_unique()`` i operator dostawał błąd formularza.

Faza 03 zamieniła pole na ``ForeignKey`` + warunkowy
``UniqueConstraint(condition=Q(deleted_at__isnull=True))``, żeby habilitacja
w koszu nie blokowała scalania autorów. To przenosi walidację z
``validate_unique()`` (patrzy na ``Meta.unique_together``/``unique``) do
``validate_constraints()`` (patrzy na ``Meta.constraints``, Django >=4.1).

I tu jest pułapka: ``Model.validate_constraints()`` **CICHO POMIJA** constraint,
którego pole warunku (``deleted_at``) jest wykluczone z walidacji — a jest,
bo ``_get_validation_exclusions()`` wyklucza wszystko spoza ``Meta.fields``,
które admin nadpisuje spłaszczonymi ``fieldsets``. Bez jawnego sprawdzenia
admin przepuściłby duplikat i wywalił się ``IntegrityError``-em (HTTP 500)
dopiero przy zapisie.

Stąd ``Praca_HabilitacyjnaForm.clean_autor()``. Te testy pilnują trzech rzeczy
naraz: że kolizja jest łapana, że rekord nie koliduje SAM ZE SOBĄ przy edycji,
i że praca w koszu NIE blokuje wprowadzenia nowej (bo inaczej „naprawą" byłby
powrót do bezwarunkowej unikalności, czyli cofnięcie całej pozycji 3.2).
"""

import pytest
from django.contrib import admin as django_admin
from django.test import RequestFactory
from model_bakery import baker

from bpp.models import Autor, Jednostka, Praca_Habilitacyjna


def _klasa_formularza(admin_user):
    """Formularz DOKŁADNIE taki, jaki zbuduje admin.

    ``Praca_HabilitacyjnaForm`` sam nie ma ``Meta.model`` — dostaje go dopiero
    z ``ModelAdmin.get_form()``. Idziemy tą samą drogą, bo testujemy zachowanie
    admina, a nie wyizolowanej klasy formularza.
    """
    request = RequestFactory().get("/")
    request.user = admin_user
    model_admin = django_admin.site._registry[Praca_Habilitacyjna]
    return model_admin.get_form(request, obj=None, change=False)


def _dane_formularza(autor, jednostka, typy_kbn, statusy_korekt, jezyki):
    from bpp.models import Jezyk, Typ_KBN

    return {
        "tytul_oryginalny": "Druga habilitacja tego samego autora",
        "autor": autor.pk,
        "jednostka": jednostka.pk,
        "rok": 2023,
        "jezyk": Jezyk.objects.get(skrot="pol.").pk,
        "typ_kbn": Typ_KBN.objects.first().pk,
        "status_korekty": statusy_korekt["przed korektą"].pk,
        # Pola punktacji są wymagane przez formularz. Wypełniamy KOMPLET,
        # żeby jedynym możliwym powodem odrzucenia był konflikt autora —
        # inaczej pierwszy test byłby czerwony z byle powodu.
        "punkty_kbn": 0,
        "impact_factor": 0,
        "index_copernicus": 0,
        "punktacja_snip": 0,
        "punktacja_wewnetrzna": 0,
    }


@pytest.mark.django_db
def test_admin_nie_pozwala_na_druga_zywa_habilitacje_autora(
    admin_user,
    typy_kbn,
    statusy_korekt,
    jezyki,
    charaktery_formalne,
    typy_odpowiedzialnosci,
):
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)
    baker.make(Praca_Habilitacyjna, autor=autor)

    form = _klasa_formularza(admin_user)(
        data=_dane_formularza(autor, jednostka, typy_kbn, statusy_korekt, jezyki)
    )

    assert not form.is_valid(), (
        "formularz przepuscil druga zywa habilitacje — przy zapisie poleci "
        "IntegrityError (HTTP 500) zamiast bledu formularza"
    )
    # Komunikat ma być dla człowieka, a nie „Constraint “phab_uniq_autor_zywy”
    # is violated." — Django nie umie zmapować UniqueConstraint z `condition`
    # na pole, więc bez `violation_error_message` operator dostaje nazwę
    # ograniczenia z bazy.
    assert "Ten autor ma już pracę habilitacyjną." in str(form.errors), (
        f"blad nie tlumaczy przyczyny: {form.errors.as_json()}"
    )


@pytest.mark.django_db
def test_admin_pozwala_zapisac_edycje_istniejacej_habilitacji(
    admin_user,
    typy_kbn,
    statusy_korekt,
    jezyki,
    charaktery_formalne,
    typy_odpowiedzialnosci,
):
    """Kontrola: rekord nie może kolidować SAM ZE SOBĄ.

    Bez wykluczenia edytowanego wiersza każda zmiana istniejącej habilitacji
    (poprawka literówki w tytule!) byłaby odrzucana jako duplikat.
    """
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)
    habilitacja = baker.make(Praca_Habilitacyjna, autor=autor)

    request = RequestFactory().get("/")
    request.user = admin_user
    model_admin = django_admin.site._registry[Praca_Habilitacyjna]
    FormKlasa = model_admin.get_form(request, obj=habilitacja, change=True)

    form = FormKlasa(
        instance=habilitacja,
        data=_dane_formularza(autor, jednostka, typy_kbn, statusy_korekt, jezyki),
    )

    assert form.is_valid(), (
        f"edycja wlasnej habilitacji odrzucona jako duplikat: {form.errors.as_json()}"
    )


@pytest.mark.django_db
def test_admin_pozwala_na_habilitacje_gdy_poprzednia_jest_w_koszu(
    admin_user,
    typy_kbn,
    statusy_korekt,
    jezyki,
    charaktery_formalne,
    typy_odpowiedzialnosci,
):
    """Kontrola: warunkowy unique NIE obejmuje kosza.

    Bez tej asercji „naprawą" pierwszego testu mogłoby być przywrócenie
    bezwarunkowej unikalności — czyli cofnięcie całej pozycji 3.2.
    """
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)
    stara = baker.make(Praca_Habilitacyjna, autor=autor)
    stara.delete()

    form = _klasa_formularza(admin_user)(
        data=_dane_formularza(autor, jednostka, typy_kbn, statusy_korekt, jezyki)
    )

    assert form.is_valid(), (
        f"habilitacja w koszu nie moze blokowac wprowadzenia nowej: "
        f"{form.errors.as_json()}"
    )
