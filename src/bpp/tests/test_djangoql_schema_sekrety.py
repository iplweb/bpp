"""Schematy DjangoQL (adminy, widok zapytań, API) nie wystawiają modeli
uwierzytelniania ani pól z poświadczeniami jako pól filtrowalnych. Model
użytkownika jest dostępny wyłącznie z polami z białej listy i bez relacji."""

import re

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search
from djangoql.schema import RelationField

from bpp.djangoql_schema import BppQLSchema, BppQLSchemaOgraniczony, RekordLLMSchema
from bpp.models import Autor, Rekord, Uczelnia
from zglos_publikacje.models import Zgloszenie_Publikacji

#: Aplikacje z danymi uwierzytelniania / audytu / konfiguracji — żaden ich model
#: nie może być osiągalny ze schematu.
APLIKACJE_ZABRONIONE = frozenset(
    {
        "admin",
        "auth",
        "authtoken",
        "axes",
        "constance",
        "django_celery_results",
        "easyaudit",
        "oauth2_provider",
        "password_policies",
        "reversion",
        "sessions",
    }
)

#: Jedyne pola modelu użytkownika dopuszczalne w schemacie.
POLA_UZYTKOWNIKA = {"username", "first_name", "last_name"}

WZORZEC_SEKRETU = re.compile(
    r"password|passwd|haslo|hasło|secret|token|api_key|apikey|klucz_api", re.I
)


def _schematy_adminow():
    for model, model_admin in admin.site._registry.items():
        schema_cls = getattr(model_admin, "djangoql_schema", None)
        if schema_cls is not None:
            yield f"admin:{model._meta.label}", schema_cls, model


def _wszystkie_schematy():
    yield from _schematy_adminow()
    yield "BppQLSchemaOgraniczony", BppQLSchemaOgraniczony, Rekord
    yield "RekordLLMSchema:Rekord", RekordLLMSchema, Rekord
    yield "RekordLLMSchema:Autor", RekordLLMSchema, Autor
    yield "BppQLSchema:Autor", BppQLSchema, Autor


def _nazwa(field):
    return field if isinstance(field, str) else getattr(field, "name", "")


def _naruszenia(schema_cls, model):
    schema = schema_cls(model)
    user_label = schema.model_label(get_user_model())
    bledy = []
    for label, pola in schema.models.items():
        app_label = label.split(".", 1)[0]
        if app_label in APLIKACJE_ZABRONIONE:
            bledy.append(f"model {label}")
        if label == user_label and set(pola) - POLA_UZYTKOWNIKA:
            bledy.append(f"pola {label}: {sorted(set(pola) - POLA_UZYTKOWNIKA)}")
        for nazwa, pole in pola.items():
            if WZORZEC_SEKRETU.search(nazwa):
                bledy.append(f"pole {label}.{nazwa}")
            related = getattr(pole, "related_model", None)
            if related is not None and related._meta.app_label in APLIKACJE_ZABRONIONE:
                bledy.append(f"relacja {label}.{nazwa} -> {related._meta.label}")
    return bledy


def test_sa_adminy_z_djangoql():
    assert len(list(_schematy_adminow())) >= 10


def test_admin_djangoql_uzywa_schematu_bpp():
    """Każdy admin z wyszukiwarką DjangoQL używa schematu BPP (z wykluczeniami)."""
    bez_schematu_bpp = [
        nazwa
        for nazwa, schema_cls, _model in _schematy_adminow()
        if not issubclass(schema_cls, BppQLSchema)
    ]
    assert bez_schematu_bpp == []


@pytest.mark.parametrize(
    "nazwa,schema_cls,model",
    list(_wszystkie_schematy()),
    ids=[x[0] for x in _wszystkie_schematy()],
)
def test_schemat_nie_wystawia_sekretow(nazwa, schema_cls, model):
    assert _naruszenia(schema_cls, model) == []


def test_pola_uczelni_z_sekretami_sa_ukryte():
    schema = BppQLSchema(Uczelnia)
    pola = schema.models[schema.model_label(Uczelnia)]
    for nazwa in (
        "pbn_app_token",
        "orcid_client_secret",
        "dspace_api_password",
        "clarivate_password",
    ):
        assert nazwa not in pola
    assert "nazwa" in pola


def test_model_uzytkownika_tylko_pola_z_bialej_listy_bez_relacji():
    schema = BppQLSchema(Zgloszenie_Publikacji)
    pola = schema.models[schema.model_label(get_user_model())]
    assert set(pola) == POLA_UZYTKOWNIKA
    assert not any(isinstance(pole, RelationField) for pole in pola.values())


def test_relacja_do_uzytkownika_jest_polem():
    schema = BppQLSchema(Zgloszenie_Publikacji)
    pole = schema.models[schema.model_label(Zgloszenie_Publikacji)]["utworzyl"]
    assert isinstance(pole, RelationField)
    assert pole.related_model is get_user_model()


@pytest.mark.parametrize(
    "schema_cls,model",
    [
        (BppQLSchemaOgraniczony, Rekord),
        (RekordLLMSchema, Rekord),
        (RekordLLMSchema, Autor),
    ],
)
def test_schematy_z_allow_lista_nie_wystawiaja_uzytkownika(schema_cls, model):
    schema = schema_cls(model)
    assert schema.model_label(get_user_model()) not in schema.models


def _zgloszenia_admin_schema():
    return admin.site._registry[Zgloszenie_Publikacji].djangoql_schema


@pytest.mark.django_db
@pytest.mark.parametrize(
    "zapytanie",
    [
        'utworzyl.username = "x"',
        'utworzyl.first_name ~ "x"',
        'utworzyl.last_name = "x"',
        "utworzyl = None",
    ],
)
def test_zapytanie_po_dozwolonym_polu_uzytkownika_dziala(zapytanie):
    wynik = apply_search(
        Zgloszenie_Publikacji.objects.all(),
        zapytanie,
        schema=_zgloszenia_admin_schema(),
    )
    assert list(wynik) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "zapytanie",
    [
        'utworzyl.password ~ "x"',
        'utworzyl.email ~ "x"',
        "utworzyl.is_superuser = True",
        "utworzyl.is_staff = True",
        'utworzyl.pbn_token ~ "x"',
        'utworzyl.last_login > "2020-01-01"',
        'utworzyl.groups.name = "x"',
        'utworzyl.user_permissions.codename = "x"',
        'utworzyl.accessible_uczelnie.nazwa = "x"',
        'utworzyl.autor.nazwisko = "x"',
        "utworzyl.id = 1",
    ],
)
def test_zapytanie_po_niedozwolonym_polu_uzytkownika_jest_odrzucone(zapytanie):
    with pytest.raises(DjangoQLError):
        list(
            apply_search(
                Zgloszenie_Publikacji.objects.all(),
                zapytanie,
                schema=_zgloszenia_admin_schema(),
            )
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "zapytanie",
    [
        'jednostki.uczelnia.pbn_app_token = "x"',
        'aktualna_jednostka.uczelnia.orcid_client_secret = "x"',
        'aktualna_jednostka.uczelnia.clarivate_password = "x"',
    ],
)
def test_zapytanie_po_sekrecie_uczelni_jest_odrzucone(zapytanie):
    with pytest.raises(DjangoQLError):
        list(apply_search(Autor.objects.all(), zapytanie, schema=BppQLSchema))


@pytest.mark.django_db
def test_zapytanie_po_nazwie_uczelni_dziala():
    wynik = apply_search(
        Autor.objects.all(),
        'aktualna_jednostka.uczelnia.nazwa = "x"',
        schema=BppQLSchema,
    )
    assert list(wynik) == []
