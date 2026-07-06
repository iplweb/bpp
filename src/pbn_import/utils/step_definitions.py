"""PBN import step definitions and configuration (model faz)."""

from .author_import import AuthorImporter
from .conference_import import ConferenceImporter
from .fee_import import FeeImporter
from .initial_setup import InitialSetup
from .institution_import import InstitutionImporter
from .publication_import import PublicationImporter
from .publisher_import import PublisherImporter
from .source_import import SourceImporter
from .source_scoring_import import SourceScoringImporter
from .statement_import import StatementImporter


def _split(entity, label):
    """Zbuduj dwie fazy (download/process) dla rozdzielanej encji."""
    return [
        {
            "phase": "download",
            "method": "download",
            "form_field": f"{entity}_download",
            "disable_key": f"disable_{entity}_download",
            "display": f"{label} — pobieranie",
            "column": "download",
            "legacy_key": f"disable_{entity}",
        },
        {
            "phase": "process",
            "method": "process",
            "form_field": f"{entity}_process",
            "disable_key": f"disable_{entity}_process",
            "display": f"{label} — przetwarzanie",
            "column": "process",
            "legacy_key": f"disable_{entity}",
        },
    ]


def _single(form_field, label, column):
    """Zbuduj pojedynczą fazę dla kroku niepodzielnego/jednofazowego."""
    return [
        {
            "phase": "single",
            "method": "run",
            "form_field": form_field,
            "disable_key": f"disable_{form_field}",
            "display": label,
            "column": column,
            "legacy_key": None,
        }
    ]


# Pojedyncze źródło prawdy o krokach importu.
ALL_STEP_DEFINITIONS = [
    {
        "name": "initial_setup",
        "display": "Konfiguracja początkowa",
        "class": InitialSetup,
        "icon": "fi-wrench",
        "required": True,
        "show_in_form": True,
        "phases": _single("initial", "Konfiguracja początkowa", "both"),
    },
    {
        "name": "institution_setup",
        "display": "Konfiguracja jednostek",
        "class": InstitutionImporter,
        "icon": "fi-home",
        "required": True,
        "show_in_form": True,
        "phases": _single("institutions", "Konfiguracja jednostek", "both"),
    },
    {
        "name": "source_import",
        "display": "Źródła",
        "class": SourceImporter,
        "icon": "fi-book",
        "required": False,
        "show_in_form": True,
        "phases": _split("zrodla", "Źródła"),
    },
    {
        "name": "source_scoring_import",
        "display": "Punktacja i dyscypliny źródeł",
        "class": SourceScoringImporter,
        "icon": "fi-graph-bar",
        "required": False,
        "show_in_form": True,
        "phases": _single(
            "punktacja_zrodel", "Synchronizacja punktów i dyscyplin źródeł", "process"
        ),
    },
    {
        "name": "publisher_import",
        "display": "Wydawcy",
        "class": PublisherImporter,
        "icon": "fi-page-multiple",
        "required": False,
        "show_in_form": True,
        "phases": _split("wydawcy", "Wydawcy"),
    },
    {
        "name": "conference_import",
        "display": "Konferencje",
        "class": ConferenceImporter,
        "icon": "fi-calendar",
        "required": False,
        "show_in_form": True,
        "phases": _split("konferencje", "Konferencje"),
    },
    {
        "name": "author_import",
        "display": "Autorzy",
        "class": AuthorImporter,
        "icon": "fi-torsos-all",
        "required": False,
        "show_in_form": True,
        "phases": _split("autorzy", "Autorzy"),
    },
    {
        "name": "publication_import",
        "display": "Publikacje",
        "class": PublicationImporter,
        "icon": "fi-page-copy",
        "required": False,
        "show_in_form": True,
        "phases": _split("publikacje", "Publikacje"),
    },
    {
        "name": "statement_import",
        "display": "Oświadczenia",
        "class": StatementImporter,
        "icon": "fi-clipboard-pencil",
        "required": False,
        "show_in_form": True,
        "phases": _split("oswiadczenia", "Oświadczenia"),
    },
    {
        "name": "fee_import",
        "display": "Opłaty",
        "class": FeeImporter,
        "icon": "fi-dollar",
        "required": False,
        "show_in_form": True,
        "phases": _single("oplaty", "Import opłat", "both"),
    },
]

STEP_ICONS = {step["name"]: step["icon"] for step in ALL_STEP_DEFINITIONS}


def _iter_phases():
    """Iteruj (step_def, phase_def) dla wszystkich kroków pokazywanych w formie."""
    for step in ALL_STEP_DEFINITIONS:
        if not step.get("show_in_form", True):
            continue
        for phase in step["phases"]:
            yield step, phase


def _phase_disabled(config, phase):
    """Czy faza wyłączona? granular > legacy > domyślnie włączona."""
    if phase["disable_key"] in config:
        return bool(config[phase["disable_key"]])
    legacy = phase.get("legacy_key")
    if legacy and legacy in config:
        return bool(config[legacy])
    return False


def get_form_steps():
    """Wiersze formularza: encja + komórki download/process/single.

    Dla kroków podzielonych (split): komórki "download" i "process".
    Dla kroków jednofazowych (single): komórka wyznaczona przez pole "column":
      - "both"    → "single"
      - "process" → "process"
      - "download"→ "download"
    """
    rows = []
    for step in ALL_STEP_DEFINITIONS:
        if not step.get("show_in_form", True):
            continue
        row = {
            "name": step["name"],
            "display": step["display"],
            "icon": step["icon"],
            "required": step["required"],
            "download": None,
            "process": None,
            "single": None,
        }
        for phase in step["phases"]:
            cell = {"form_field": phase["form_field"], "display": phase["display"]}
            if phase["phase"] == "single":
                column = phase.get("column", "both")
                target = column if column in ("download", "process") else "single"
                row[target] = cell
            else:
                row[phase["phase"]] = cell
        rows.append(row)
    return rows


def get_command_steps():
    """Pary (form_field, display) dla CLI — jedna na fazę."""
    return [(phase["form_field"], phase["display"]) for _, phase in _iter_phases()]


def get_legacy_command_aliases():
    """Mapa legacy form_field → lista granularnych disable_key (dla CLI alias)."""
    aliases = {}
    for step in ALL_STEP_DEFINITIONS:
        phases = step["phases"]
        if len(phases) == 2:  # krok rozdzielany
            entity = phases[0]["form_field"].rsplit("_", 1)[0]
            aliases[entity] = [p["disable_key"] for p in phases]
    return aliases


def get_all_disable_keys():
    """Mapa form_field → disable_key (granularna, wszystkie fazy)."""
    return {phase["form_field"]: phase["disable_key"] for _, phase in _iter_phases()}


def _get_step_args(step_name, config):
    """Dynamiczne argumenty konstruktora kroku na podstawie config."""
    if step_name == "institution_setup":
        return {
            "wydzial_domyslny": config.get("wydzial_domyslny", "Wydział Domyślny"),
            "wydzial_domyslny_skrot": config.get("wydzial_domyslny_skrot"),
        }
    elif step_name == "publication_import":
        return {"delete_existing": config.get("delete_existing", False)}
    return {}


def get_step_definitions(config):
    """Płaska, uporządkowana lista faz do wykonania (po odfiltrowaniu)."""
    result = []
    for step in ALL_STEP_DEFINITIONS:
        for phase in step["phases"]:
            if _phase_disabled(config, phase):
                continue
            phase_name = phase["phase"]
            result_key = (
                step["name"]
                if phase_name == "single"
                else f"{step['name']}:{phase_name}"
            )
            result.append(
                {
                    "name": step["name"],
                    "phase": phase_name,
                    "display": phase["display"],
                    "class": step["class"],
                    "method": phase["method"],
                    "required": step["required"],
                    "args": _get_step_args(step["name"], config),
                    "result_key": result_key,
                }
            )
    return result


def get_icon_for_step(step_name):
    """Zwróć klasę ikony Foundation dla kroku."""
    return STEP_ICONS.get(step_name, "fi-download")
