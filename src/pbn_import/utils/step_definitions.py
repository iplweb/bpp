"""PBN import step definitions and configuration"""

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

# All possible import steps with their configuration
# This is the single source of truth for import steps
ALL_STEP_DEFINITIONS = [
    {
        "name": "initial_setup",
        "display": "Konfiguracja początkowa",
        "class": InitialSetup,
        "disable_key": "disable_initial",
        "form_field": "initial",
        "icon": "fi-wrench",
        "required": True,
        "show_in_form": True,
    },
    {
        "name": "institution_setup",
        "display": "Konfiguracja jednostek",
        "class": InstitutionImporter,
        "disable_key": "disable_institutions",
        "form_field": "institutions",
        "icon": "fi-home",
        "required": True,
        "show_in_form": True,
    },
    {
        "name": "source_import",
        "display": "Import źródeł",
        "class": SourceImporter,
        "disable_key": "disable_zrodla",
        "form_field": "zrodla",
        "icon": "fi-book",
        "required": False,
        "show_in_form": True,
    },
    {
        "name": "source_scoring_import",
        "display": "Synchronizacja punktów i dyscyplin źródeł",
        "class": SourceScoringImporter,
        "disable_key": "disable_punktacja_zrodel",
        "form_field": "punktacja_zrodel",
        "icon": "fi-graph-bar",
        "required": False,
        "show_in_form": True,
    },
    {
        "name": "publisher_import",
        "display": "Import wydawców",
        "class": PublisherImporter,
        "disable_key": "disable_wydawcy",
        "form_field": "wydawcy",
        "icon": "fi-page-multiple",
        "required": False,
        "show_in_form": True,
    },
    {
        "name": "conference_import",
        "display": "Import konferencji",
        "class": ConferenceImporter,
        "disable_key": "disable_konferencje",
        "form_field": "konferencje",
        "icon": "fi-calendar",
        "required": False,
        "show_in_form": True,
    },
    {
        "name": "author_import",
        "display": "Import autorów",
        "class": AuthorImporter,
        "disable_key": "disable_autorzy",
        "form_field": "autorzy",
        "icon": "fi-torsos-all",
        "required": False,
        "show_in_form": True,
    },
    {
        "name": "publication_import",
        "display": "Import publikacji",
        "class": PublicationImporter,
        "disable_key": "disable_publikacje",
        "form_field": "publikacje",
        "icon": "fi-page-copy",
        "required": False,
        "show_in_form": True,
    },
    {
        "name": "statement_import",
        "display": "Import oświadczeń",
        "class": StatementImporter,
        "disable_key": "disable_oswiadczenia",
        "form_field": "oswiadczenia",
        "icon": "fi-clipboard-pencil",
        "required": False,
        "show_in_form": True,
    },
    {
        "name": "fee_import",
        "display": "Import opłat",
        "class": FeeImporter,
        "disable_key": "disable_oplaty",
        "form_field": "oplaty",
        "icon": "fi-dollar",
        "required": False,
        "show_in_form": True,
    },
]

# Legacy STEP_ICONS dict for backwards compatibility
STEP_ICONS = {step["name"]: step["icon"] for step in ALL_STEP_DEFINITIONS}


def get_form_steps():
    """Get import steps formatted for form display.

    Returns list of dicts with:
    - form_field: name for form checkbox
    - display: Polish label
    - icon: Foundation icon class
    - required: whether step is required
    """
    return [
        {
            "form_field": step["form_field"],
            "display": step["display"],
            "icon": step["icon"],
            "required": step["required"],
        }
        for step in ALL_STEP_DEFINITIONS
        if step.get("show_in_form", True)
    ]


def get_command_steps():
    """Get import steps formatted for management command.

    Returns list of tuples (form_field, display) for building CLI arguments.
    """
    return [
        (step["form_field"], step["display"])
        for step in ALL_STEP_DEFINITIONS
        if step.get("show_in_form", True)
    ]


def get_all_disable_keys():
    """Get all disable_key values from step definitions.

    Returns dict mapping form_field to disable_key.
    """
    return {step["form_field"]: step["disable_key"] for step in ALL_STEP_DEFINITIONS}


def _get_step_args(step_name, config):
    """Get dynamic args for a specific step based on config"""
    if step_name == "institution_setup":
        return {
            "wydzial_domyslny": config.get("wydzial_domyslny", "Wydział Domyślny"),
            "wydzial_domyslny_skrot": config.get("wydzial_domyslny_skrot"),
        }
    elif step_name == "publication_import":
        return {"delete_existing": config.get("delete_existing", False)}
    return {}


def get_step_definitions(config):
    """Get list of import step definitions based on config"""
    return [
        {
            "name": step_def["name"],
            "display": step_def["display"],
            "class": step_def["class"],
            "required": step_def["required"],
            "args": _get_step_args(step_def["name"], config),
        }
        for step_def in ALL_STEP_DEFINITIONS
        if not config.get(step_def["disable_key"])
    ]


def get_icon_for_step(step_name):
    """Get Foundation icon class for step"""
    return STEP_ICONS.get(step_name, "fi-download")
