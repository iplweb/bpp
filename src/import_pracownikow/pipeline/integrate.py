"""Faza integracji (commit) importu pracowników.

``integruj`` materializuje odroczone create'y zapisane w
``ImportPracownikowRow.diff_do_utworzenia`` przez fazę analizy
(``import_pracownikow.pipeline.analyze``) — tworzy brakujące
Funkcja_Autora/Grupa_Pracownicza/Wymiar_Etatu oraz ``Autor_Jednostka``
przez ``get_or_create`` (idempotentne przy duplikacie osoby w pliku),
ustawia FK na wierszu, po czym robi świeży ``check_if_integration_needed()``
— baza mogła się zmienić od czasu analizy (dry-run), więc wiersz uznany
za "potrzebujący zmian" w analizie może już być nieaktualny. Gdy tak,
wiersz jest oznaczany ``pominiety_bo_nieaktualny=True`` i pomijany;
inaczej woła się istniejące ``ImportPracownikowRow.integrate()``.
"""

from django.db import transaction

from bpp.models import (
    Autor_Jednostka,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Wymiar_Etatu,
)
from import_common.normalization import (
    normalize_funkcja_autora,
    normalize_grupa_pracownicza,
    normalize_wymiar_etatu,
)
from import_pracownikow.models import ImportPracownikow


def _materializuj_diff(row):
    """Tworzy (get_or_create) obiekty odłożone przez analizę i podpina FK."""
    diff = row.diff_do_utworzenia or {}
    if "funkcja_autora" in diff:
        nazwa = normalize_funkcja_autora(diff["funkcja_autora"])
        row.funkcja_autora, _ = Funkcja_Autora.objects.get_or_create(
            nazwa=nazwa, defaults={"skrot": nazwa}
        )
    if "grupa_pracownicza" in diff:
        nazwa = normalize_grupa_pracownicza(diff["grupa_pracownicza"])
        row.grupa_pracownicza, _ = Grupa_Pracownicza.objects.get_or_create(nazwa=nazwa)
    if "wymiar_etatu" in diff:
        nazwa = normalize_wymiar_etatu(diff["wymiar_etatu"])
        row.wymiar_etatu, _ = Wymiar_Etatu.objects.get_or_create(nazwa=nazwa)
    if "autor_jednostka" in diff:
        row.autor_jednostka, _ = Autor_Jednostka.objects.get_or_create(
            autor_id=diff["autor_jednostka"]["autor"],
            jednostka_id=diff["autor_jednostka"]["jednostka"],
            defaults={"funkcja": row.funkcja_autora},
        )


def _integruj_wiersz(row):
    with transaction.atomic():
        _materializuj_diff(row)
        row.save(
            update_fields=[
                "funkcja_autora",
                "grupa_pracownicza",
                "wymiar_etatu",
                "autor_jednostka",
            ]
        )
        # Świeży re-check — baza mogła się zmienić od preview (dry-run).
        if not row.check_if_integration_needed():
            row.pominiety_bo_nieaktualny = True
            row.save(update_fields=["pominiety_bo_nieaktualny"])
            return
        row.integrate()


def integruj(parent, p):
    qs = parent.zmiany_potrzebne_set.all()
    for row in p.track(list(qs), total=qs.count(), label="Integracja"):
        _integruj_wiersz(row)

    parent.stan = ImportPracownikow.STAN_ZINTEGROWANY
    parent.save(update_fields=["stan"])

    p.result(
        {
            "zintegrowano": parent.importpracownikowrow_set.filter(
                log_zmian__isnull=False
            ).count(),
            "pominieto_nieaktualne": parent.importpracownikowrow_set.filter(
                pominiety_bo_nieaktualny=True
            ).count(),
            "stan": parent.stan,
        }
    )
