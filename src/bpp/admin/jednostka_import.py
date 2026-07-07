"""Import wydziałów i jednostek z pliku XLSX (django-import-export).

Spodziewane kolumny:

    * ``Uczelnia``
    * ``Wydział``
    * ``Katedra/Zakład/Klinika``

Założenia:

* Uczelnie muszą już istnieć w bazie (lookup po ``nazwa``). Jeżeli
  uczelnia z wiersza nie istnieje, import wiersza zgłasza błąd
  widoczny w GUI.
* Tam, gdzie wiersz nie ma wydziału, tworzony jest jeden wydział
  o domyślnej nazwie ``"Wydział <skrót uczelni>"``.
* Tam, gdzie wiersz nie ma jednostki, tworzona jest jednostka
  ``"Jednostka Wydziału <X>"`` (gdzie ``<X>`` to fragment nazwy
  wydziału po prefiksie ``"Wydział "``).
* Skróty (``Jednostka.skrot`` -- max 128) są generowane jako unikalne.
"""

from __future__ import annotations

from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from bpp.models.jednostka import Jednostka
from bpp.models.uczelnia import Uczelnia

COLUMN_UCZELNIA = "Uczelnia"
COLUMN_WYDZIAL = "Wydział"
COLUMN_JEDNOSTKA = "Katedra/Zakład/Klinika"


def abbreviate_wydzial(name: str) -> str:
    """Akronim z dużych liter w nazwie wydziału (max 10 znaków)."""
    out: list[str] = []
    for token in name.split():
        if not token:
            continue
        ch = token[0]
        if ch.isupper():
            out.append(ch)
        elif ch.isalpha():
            out.append(ch.lower())
    if not out:
        out = [name[:1] or "X"]
    return "".join(out)[:10] or "X"


def unique_skrot(base: str, used: set[str], max_len: int) -> str:
    """Skrót unikalny w obrębie ``used``, ograniczony do ``max_len``."""
    candidate = base[:max_len]
    if candidate and candidate not in used:
        used.add(candidate)
        return candidate

    n = 2
    while True:
        suffix = str(n)
        prefix_len = max(1, max_len - len(suffix))
        candidate = f"{base[:prefix_len]}{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        n += 1


def domyslna_nazwa_wydzialu(uczelnia: Uczelnia) -> str:
    return f"Wydział {uczelnia.skrot}"


def domyslna_nazwa_jednostki(wydzial_nazwa: str) -> str:
    for prefix in ("Wydział ", "Wydzial "):
        if wydzial_nazwa.startswith(prefix):
            return f"Jednostka Wydziału {wydzial_nazwa[len(prefix) :]}"
    return f"Jednostka {wydzial_nazwa}"


class WydzialGetOrCreateWidget(ForeignKeyWidget):
    """ForeignKey widget: get-or-create jednostki TOP-LEVEL po ``nazwa``.

    Faza C (#438): model ``Wydzial`` usunięty — „wydział" to jednostka z
    ``parent IS NULL``. Widget zwraca root-``Jednostka``, a pole zasobu pisze
    go do ``parent`` importowanej jednostki. Uczelnia odczytywana z kolumny
    ``Uczelnia`` (obiekt ``Jednostka`` dopiero powstaje, więc nie da się
    sięgnąć przez FK na obiekcie).
    """

    def __init__(self, **kwargs):
        super().__init__(Jednostka, field="nazwa", **kwargs)

    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        nazwa = str(value).strip()
        if not nazwa:
            return None

        # ``Jednostka.nazwa`` jest UNIQUE globalnie (nie per-poziom), więc
        # szukamy BEZ ograniczenia ``parent__isnull`` — inaczej ``create()``
        # wybuchłby ``IntegrityError`` na kolizji z jednostką niższego poziomu
        # (Fable F8). Istniejąca jednostka podrzędna o tej nazwie nie może
        # pełnić roli wydziału → błąd jawny zamiast cichego złego drzewa.
        existing = Jednostka.objects.filter(nazwa=nazwa).first()
        if existing is not None:
            if existing.parent_id is not None:
                raise ValueError(
                    f"Jednostka '{nazwa}' istnieje już jako jednostka "
                    f"podrzędna (pod '{existing.parent}') i nie może pełnić "
                    "roli wydziału (jednostki najwyższego poziomu)."
                )
            return existing

        uczelnia_value = (row or {}).get(COLUMN_UCZELNIA)
        if not uczelnia_value:
            raise ValueError(
                f"Brak kolumny '{COLUMN_UCZELNIA}' dla wydziału '{nazwa}'."
            )
        uczelnia_nazwa = str(uczelnia_value).strip()
        try:
            uczelnia = Uczelnia.objects.get(nazwa=uczelnia_nazwa)
        except Uczelnia.DoesNotExist as exc:
            raise ValueError(
                f"Uczelnia '{uczelnia_nazwa}' nie istnieje. "
                "Utwórz ją ręcznie i ponów import."
            ) from exc

        used_skroty = set(Jednostka.objects.values_list("skrot", flat=True))
        skrot = unique_skrot(abbreviate_wydzial(nazwa), used_skroty, max_len=128)
        return Jednostka.objects.create(
            uczelnia=uczelnia,
            nazwa=nazwa,
            skrot=skrot,
            parent=None,
        )


class JednostkaImportResource(resources.ModelResource):
    """Resource importu jednostek z XLSX.

    * Lookup po ``nazwa`` -- jednostki o tej nazwie są aktualizowane,
      brakujące tworzone.
    * Wydziały i jednostki bez wartości w odpowiedniej kolumnie są
      zastępowane wartościami domyślnymi (patrz docstring modułu).
    * ``Wydzial`` jest tworzony przez :class:`WydzialGetOrCreateWidget`,
      jeżeli nie istnieje.
    """

    uczelnia = fields.Field(
        column_name=COLUMN_UCZELNIA,
        attribute="uczelnia",
        widget=ForeignKeyWidget(Uczelnia, field="nazwa"),
    )
    # Faza C (#438): pole „wydział" pisze do ``parent`` (root-Jednostka), a
    # denorm ``wydzial`` (korzeń) wyliczy się przy zapisie jednostki.
    wydzial = fields.Field(
        column_name=COLUMN_WYDZIAL,
        attribute="parent",
        widget=WydzialGetOrCreateWidget(),
    )
    nazwa = fields.Field(
        column_name=COLUMN_JEDNOSTKA,
        attribute="nazwa",
    )

    class Meta:
        model = Jednostka
        import_id_fields = ("nazwa",)
        fields = ("uczelnia", "wydzial", "nazwa")
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        """Wypełnij domyślne wartości (Wydział / Jednostka), gdy puste."""
        nazwa_uczelni = row.get(COLUMN_UCZELNIA) or ""
        nazwa_uczelni = str(nazwa_uczelni).strip()
        if not nazwa_uczelni:
            return

        try:
            uczelnia = Uczelnia.objects.get(nazwa=nazwa_uczelni)
        except Uczelnia.DoesNotExist:
            # Walidację robi widget kolumny ``Uczelnia`` -- niech zgłosi
            # czytelny błąd dla danego wiersza.
            return

        wydzial_nazwa = str(row.get(COLUMN_WYDZIAL) or "").strip()
        if not wydzial_nazwa:
            wydzial_nazwa = domyslna_nazwa_wydzialu(uczelnia)
            row[COLUMN_WYDZIAL] = wydzial_nazwa

        jednostka_nazwa = str(row.get(COLUMN_JEDNOSTKA) or "").strip()
        if not jednostka_nazwa:
            row[COLUMN_JEDNOSTKA] = domyslna_nazwa_jednostki(wydzial_nazwa)

    def before_save_instance(self, instance, row, **kwargs):
        """Auto-generuj ``skrot`` jednostki i ustaw ``aktualna=True``."""
        if not instance.pk:
            if not instance.skrot:
                used = set(Jednostka.objects.values_list("skrot", flat=True))
                instance.skrot = unique_skrot(instance.nazwa, used, max_len=128)
            instance.aktualna = True
