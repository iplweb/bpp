"""Widoki aplikacji ewaluacja_optymalizacja."""

# Import all views from submodules for backward compatibility with urls.py
from .author_works import (
    author_works_detail,
)
from .author_works_exports import (
    export_all_works_xlsx,
    export_prace_nazbierane_xlsx,
    export_prace_nienazbierane_xlsx,
    export_prace_odpiete_xlsx,
)
from .bulk_optimization import (
    bulk_optimization_status,
    cancel_bulk_optimization,
    start_bulk_optimization,
)
from .discipline_swap_analysis import (
    analyze_discipline_swap_opportunities,
    discipline_swap_status,
)
from .discipline_swap_list import (
    cancel_discipline_swap_task,
    discipline_swap_opportunities_list,
    export_discipline_swap_xlsx,
)
from .evaluation_browser import (
    browser_recalc_status,
    browser_summary,
    browser_swap_discipline,
    browser_table,
    browser_toggle_pin,
    evaluation_browser,
)
from .exports import (
    export_all_authors_zip,
    export_all_disciplines_zip,
    export_author_sedn_xlsx,
    export_sedn_report_1,
    export_sedn_report_2,
    generate_all_disciplines_zip_file,
)
from .helpers import (
    _get_discipline_pin_stats,
)
from .index import (
    denorm_progress,
    index,
    trigger_denorm_flush,
)
from .optimization_runs import (
    discipline_comparison,
    run_detail,
    run_list,
)
from .optimize_unpin import (
    cancel_optimize_unpin_task,
    optimize_unpin_status,
    optimize_with_unpinning,
)
from .pins import (
    reset_all_pins,
    reset_all_pins_status,
    reset_discipline_pins,
)
from .unpin_sensible import (
    unpin_all_sensible,
    unpin_all_sensible_status,
)
from .unpinning_analysis import (
    analyze_unpinning_opportunities,
    unpinning_analysis_status,
    unpinning_combined_status,
)
from .unpinning_list import (
    cancel_unpinning_task,
    export_unpinning_opportunities_xlsx,
    unpinning_opportunities_list,
)
from .verification import (
    database_verification_view,
)

__all__ = [
    # index.py
    "index",
    "denorm_progress",
    "trigger_denorm_flush",
    # optimization_runs.py
    "run_list",
    "run_detail",
    "discipline_comparison",
    # bulk_optimization.py
    "start_bulk_optimization",
    "bulk_optimization_status",
    "cancel_bulk_optimization",
    # optimize_unpin.py
    "optimize_with_unpinning",
    "optimize_unpin_status",
    "cancel_optimize_unpin_task",
    # pins.py
    "reset_discipline_pins",
    "reset_all_pins",
    "reset_all_pins_status",
    # unpin_sensible.py
    "unpin_all_sensible",
    "unpin_all_sensible_status",
    # unpinning_analysis.py
    "analyze_unpinning_opportunities",
    "unpinning_combined_status",
    "unpinning_analysis_status",
    # unpinning_list.py
    "unpinning_opportunities_list",
    "export_unpinning_opportunities_xlsx",
    "cancel_unpinning_task",
    # exports.py
    "export_author_sedn_xlsx",
    "export_all_authors_zip",
    "export_all_disciplines_zip",
    "export_sedn_report_1",
    "export_sedn_report_2",
    "generate_all_disciplines_zip_file",
    # verification.py
    "database_verification_view",
    # helpers.py
    "_get_discipline_pin_stats",
    # author_works.py
    "author_works_detail",
    # author_works_exports.py
    "export_all_works_xlsx",
    "export_prace_nazbierane_xlsx",
    "export_prace_nienazbierane_xlsx",
    "export_prace_odpiete_xlsx",
    # discipline_swap_analysis.py
    "analyze_discipline_swap_opportunities",
    "discipline_swap_status",
    # discipline_swap_list.py
    "discipline_swap_opportunities_list",
    "export_discipline_swap_xlsx",
    "cancel_discipline_swap_task",
    # evaluation_browser.py
    "evaluation_browser",
    "browser_summary",
    "browser_table",
    "browser_toggle_pin",
    "browser_swap_discipline",
    "browser_recalc_status",
]
