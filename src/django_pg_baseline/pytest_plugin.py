"""Optional pytest plugin channel for installing the baseline patch.

In bpp we install the monkey patch via ``INSTALLED_APPS`` +
``AppConfig.ready()``. This plugin exists for downstream users of the
package who prefer not to add it to ``INSTALLED_APPS``.
"""

from __future__ import annotations


def pytest_configure(config):  # noqa: ARG001
    import django

    django.setup()
    from .conf import get_config
    from .patches import install_test_db_patch

    cfg = get_config()
    if cfg.auto_load_on_test_db and cfg.sql_path.exists():
        install_test_db_patch(cfg)
