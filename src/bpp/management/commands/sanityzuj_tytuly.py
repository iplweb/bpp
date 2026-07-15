"""Jednorazowa sanityzacja istniejących tytułów publikacji.

Save-hook (``DwaTytuly.save()`` / ``Patent.save()``) czyści tytuły przy każdym
zapisie, ale dane sprzed wdrożenia mogą nadal zawierać niebezpieczny HTML
(``<script>``) lub pseudo-znaczniki liter greckich (``<beta>``). Komenda
przechodzi wszystkie konkretne modele z polem ``tytul_oryginalny``, sanityzuje
tytuły przez ``safe_tytul_html`` i — z opcją ``--napraw`` — zapisuje zmiany
(``save()`` wyzwala też przebudowę ``opis_bibliograficzny_cache`` przez denorm).

Bez ``--napraw`` tylko raportuje, ile tytułów wymagałoby zmiany.
"""

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand
from django.db import models
from django.db.models import Q

from bpp.util import safe_tytul_html


def _ma_pole_tekstowe(model, nazwa):
    """True, gdy ``model`` ma KONKRETNE pole tekstowe o tej nazwie. Odsiewa
    relacje o nazwie ``tytul`` (np. FK ``tytul`` do słownika ``Tytul``), dla
    których ``tytul__contains`` rzuciłoby ``FieldError``."""
    try:
        f = model._meta.get_field(nazwa)
    except FieldDoesNotExist:
        return False
    return isinstance(f, (models.TextField, models.CharField))


def _modele_z_tytulem():
    """Konkretne (nie-abstrakcyjne) modele z tekstowym ``tytul_oryginalny`` LUB
    ``tytul`` — to drugie łapie tytuły w pozostałych językach
    (``BazaModeluTytulow`` → ``Wydawnictwo_*_Tytul``), które mają wyłącznie
    ``tytul`` i wcześniej wypadały z czyszczenia (XSS #3)."""
    out = []
    for m in apps.get_models():
        # Pomijamy modele niezarządzane (np. ``Rekord`` to SQL VIEW — zapis do
        # nich nie tknąłby realnej tabeli i rzuciłby „did not affect any rows").
        if m._meta.abstract or not m._meta.managed:
            continue
        if _ma_pole_tekstowe(m, "tytul_oryginalny") or _ma_pole_tekstowe(m, "tytul"):
            out.append(m)
    return sorted(out, key=lambda m: m.__name__)


class Command(BaseCommand):
    help = "Sanityzuje istniejące tytuły publikacji (XSS, litery greckie)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--napraw",
            action="store_true",
            help="Zapisz zmiany (domyślnie tylko raport).",
        )

    @staticmethod
    def _przypisz_czyste_tytuly(obj, ma_oryginalny, ma_tytul):
        """Ustaw na obiekcie sanityzowane tytuły; zwróć listę zmienionych pól."""
        fields = []
        if ma_oryginalny:
            nowy_oryg = safe_tytul_html(obj.tytul_oryginalny)
            if nowy_oryg != obj.tytul_oryginalny:
                obj.tytul_oryginalny = nowy_oryg
                fields.append("tytul_oryginalny")
        if ma_tytul:
            nowy_t = safe_tytul_html(obj.tytul)
            if nowy_t != obj.tytul:
                obj.tytul = nowy_t
                fields.append("tytul")
        return fields

    def _sanityzuj_model(self, model, napraw):
        ma_oryginalny = _ma_pole_tekstowe(model, "tytul_oryginalny")
        ma_tytul = _ma_pole_tekstowe(model, "tytul")
        flt = Q()
        if ma_oryginalny:
            flt |= Q(tytul_oryginalny__contains="<")
        if ma_tytul:
            flt |= Q(tytul__contains="<")

        zmienione = 0
        for obj in model.objects.filter(flt).iterator():
            fields = self._przypisz_czyste_tytuly(obj, ma_oryginalny, ma_tytul)
            if not fields:
                continue
            zmienione += 1
            if napraw:
                # save() (nie update()) — wyzwala denorm → przebudowa
                # opis_bibliograficzny_cache z czystego tytułu.
                obj.save(update_fields=fields)
        return zmienione

    def handle(self, *args, **options):
        napraw = options["napraw"]
        laczna_zmiana = 0

        for model in _modele_z_tytulem():
            zmienione = self._sanityzuj_model(model, napraw)
            if zmienione:
                laczna_zmiana += zmienione
                self.stdout.write(f"{model.__name__}: {zmienione} tytułów")

        czasownik = "naprawiono" if napraw else "do naprawy"
        self.stdout.write(
            self.style.SUCCESS(f"Łącznie {czasownik}: {laczna_zmiana} tytułów.")
        )
        if not napraw and laczna_zmiana:
            self.stdout.write("Uruchom ponownie z --napraw, aby zapisać zmiany.")
