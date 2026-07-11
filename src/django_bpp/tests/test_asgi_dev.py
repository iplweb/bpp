from pathlib import Path

from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from run_site.config import load_config

from django_bpp.asgi import application as asgi_application
from django_bpp.asgi_dev import application


def test_development_application_serves_static_files():
    assert isinstance(application, ASGIStaticFilesHandler)
    assert application.application is asgi_application


def test_run_site_uses_bounded_uvicorn_reload():
    project_root = Path(__file__).resolve().parents[3]
    config = load_config(
        config_path=project_root / "runsite.toml",
        project_root=project_root,
    )
    command = config.django.web_command

    assert command is not None
    assert command[:4] == (
        "{python}",
        "-m",
        "uvicorn",
        "django_bpp.asgi_dev:application",
    )
    assert "--reload" in command
    timeout_option = command.index("--timeout-graceful-shutdown")
    assert command[timeout_option + 1] == "1"
