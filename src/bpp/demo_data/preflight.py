"""Pre-flight checks dla create_demo_data: wymagane fixtury slownikowe."""

from __future__ import annotations

from django.apps import apps

REQUIRED_DICTIONARIES: list[tuple[str, str]] = [
    ("bpp.Charakter_Formalny", "loaddata charakter_formalny"),
    ("bpp.Typ_KBN", "loaddata typ_kbn"),
    ("bpp.Jezyk", "loaddata jezyk"),
    ("bpp.Status_Korekty", "loaddata status_korekty"),
    ("bpp.Rodzaj_Zrodla", "loaddata rodzaj_zrodla"),
    ("bpp.Funkcja_Autora", "loaddata funkcja_autora"),
    ("bpp.Typ_Odpowiedzialnosci", "loaddata typ_odpowiedzialnosci_v2"),
    ("bpp.Tytul", "loaddata tytul"),
    ("bpp.Plec", "loaddata plec"),
    ("bpp.Zrodlo_Informacji", "loaddata zrodlo_informacji"),
    ("bpp.Dyscyplina_Naukowa", "import dyscyplin (zewnetrzny seed)"),
]


def check_required() -> list[tuple[str, str]]:
    """Zwraca liste (label, hint) dla brakujacych slownikow.

    Pusta lista = OK, mozna jechac.
    """
    missing: list[tuple[str, str]] = []
    for label, hint in REQUIRED_DICTIONARIES:
        app_label, model_name = label.split(".")
        model = apps.get_model(app_label, model_name)
        if not model.objects.exists():
            missing.append((label, hint))
    return missing
