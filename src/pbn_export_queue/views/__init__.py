"""PBN export queue views package.

This package provides backward compatibility - all views that were previously
in views.py are re-exported here.
"""

# Action views
from .action_views import (
    PBNExportQueueCountsView,
    delete_from_queue,
    prepare_for_resend,
    resend_all_errors,
    resend_all_waiting,
    resend_filtered,
    resend_to_pbn,
    try_send_to_pbn,
    wake_up_queue,
)

# Constants
from .constants import AI_PROMPT_TEMPLATE, HELPDESK_EMAIL_TEMPLATE

# Detail view
from .detail_views import PBNExportQueueDetailView

# List views
from .list_views import (
    BasePBNExportQueueListView,
    PBNExportQueueListView,
    PBNExportQueueTableView,
)

# Mixins
from .mixins import PBNExportQueuePermissionMixin

# Utilities
from .utils import (
    extract_pbn_error_from_komunikat,
    format_submission_date,
    get_filename_from_record,
    get_record_title,
    get_user_info,
    parse_error_details,
    parse_pbn_api_error,
    sanitize_filename,
)

# Backward compatibility aliases for internal functions with underscore prefix
_get_record_title = get_record_title
_parse_error_details = parse_error_details
_format_submission_date = format_submission_date
_get_user_info = get_user_info

__all__ = [
    # Constants
    "HELPDESK_EMAIL_TEMPLATE",
    "AI_PROMPT_TEMPLATE",
    # Utilities
    "sanitize_filename",
    "get_filename_from_record",
    "parse_pbn_api_error",
    "extract_pbn_error_from_komunikat",
    "get_record_title",
    "parse_error_details",
    "format_submission_date",
    "get_user_info",
    # Backward compatibility aliases
    "_get_record_title",
    "_parse_error_details",
    "_format_submission_date",
    "_get_user_info",
    # Mixins
    "PBNExportQueuePermissionMixin",
    # List views
    "BasePBNExportQueueListView",
    "PBNExportQueueListView",
    "PBNExportQueueTableView",
    # Detail view
    "PBNExportQueueDetailView",
    # Action views
    "delete_from_queue",
    "resend_to_pbn",
    "prepare_for_resend",
    "try_send_to_pbn",
    "resend_all_waiting",
    "resend_all_errors",
    "resend_filtered",
    "wake_up_queue",
    "PBNExportQueueCountsView",
]
