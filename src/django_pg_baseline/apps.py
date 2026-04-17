from django.apps import AppConfig


class DjangoPgBaselineConfig(AppConfig):
    name = "django_pg_baseline"
    verbose_name = "PostgreSQL baseline dump"

    def ready(self):
        from .conf import get_config
        from .patches import install_test_db_patch

        try:
            config = get_config()
        except RuntimeError:
            return
        if config.auto_load_on_test_db and config.sql_path.exists():
            install_test_db_patch(config)
