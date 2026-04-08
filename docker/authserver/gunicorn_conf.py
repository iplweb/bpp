"""Gunicorn configuration for the auth server.

Filters healthcheck requests from access logs to reduce noise.
"""

import logging


class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        return "/health/" not in record.getMessage()


logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "health_check": {
            "()": HealthCheckFilter,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "filters": ["health_check"],
        },
        "error_console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "gunicorn.access": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "gunicorn.error": {
            "handlers": ["error_console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
