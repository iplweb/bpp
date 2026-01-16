"""PBN import step definitions and configuration"""

from .author_import import AuthorImporter
from .conference_import import ConferenceImporter
from .data_integration import DataIntegrator
from .fee_import import FeeImporter
from .initial_setup import InitialSetup
from .institution_import import InstitutionImporter
from .publication_import import PublicationImporter
from .publisher_import import PublisherImporter
from .source_import import SourceImporter
from .statement_import import StatementImporter

STEP_ICONS = {
    "initial_setup": "fi-wrench",
    "institution_setup": "fi-home",
    "source_import": "fi-book",
    "publisher_import": "fi-page-multiple",
    "conference_import": "fi-calendar",
    "author_import": "fi-torsos-all",
    "publication_import": "fi-page-copy",
    "data_integration": "fi-link",
    "statement_import": "fi-clipboard-pencil",
    "fee_import": "fi-dollar",
}

# All possible import steps with their configuration
ALL_STEP_DEFINITIONS = [
    {
        "name": "initial_setup",
        "display": "Konfiguracja początkowa",
        "class": InitialSetup,
        "disable_key": "disable_initial",
        "required": True,
    },
    {
        "name": "institution_setup",
        "display": "Konfiguracja jednostek",
        "class": InstitutionImporter,
        "disable_key": "disable_institutions",
        "required": True,
    },
    {
        "name": "source_import",
        "display": "Import źródeł",
        "class": SourceImporter,
        "disable_key": "disable_zrodla",
        "required": False,
    },
    {
        "name": "publisher_import",
        "display": "Import wydawców",
        "class": PublisherImporter,
        "disable_key": "disable_wydawcy",
        "required": False,
    },
    {
        "name": "conference_import",
        "display": "Import konferencji",
        "class": ConferenceImporter,
        "disable_key": "disable_konferencje",
        "required": False,
    },
    {
        "name": "author_import",
        "display": "Import autorów",
        "class": AuthorImporter,
        "disable_key": "disable_autorzy",
        "required": False,
    },
    {
        "name": "publication_import",
        "display": "Import publikacji",
        "class": PublicationImporter,
        "disable_key": "disable_publikacje",
        "required": False,
    },
    {
        "name": "data_integration",
        "display": "Integruj nowe dane",
        "class": DataIntegrator,
        "disable_key": "disable_integracja",
        "required": False,
    },
    {
        "name": "statement_import",
        "display": "Import oświadczeń",
        "class": StatementImporter,
        "disable_key": "disable_oswiadczenia",
        "required": False,
    },
    {
        "name": "fee_import",
        "display": "Import opłat",
        "class": FeeImporter,
        "disable_key": "disable_oplaty",
        "required": False,
    },
]


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
