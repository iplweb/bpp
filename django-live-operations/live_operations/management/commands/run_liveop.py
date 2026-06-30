"""
run_liveop — run a LiveOperation subclass synchronously in text mode.

Usage:
    manage.py run_liveop app.ModelName [--owner=username] [--<field>=value ...]

- Uses TextProgress (tqdm if installed, else plain print).
- Requires RUNNER=eager in settings (or set RUNNER env var).
- Owner defaults to the first superuser; use --owner to override.
- Remaining --key=value arguments are passed as kwargs to model constructor.

Typical use: zero-infra smoke test / CI dry-run that does not need Redis or ASGI.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run a LiveOperation subclass synchronously in text mode (no Redis/ASGI)."

    def add_arguments(self, parser):
        parser.add_argument(
            "model",
            help=(
                "Dotted app.ModelName, e.g. demo.DemoImport "
                "or demo.DemoImport (app_label.ModelClass)"
            ),
        )
        parser.add_argument(
            "--owner",
            default=None,
            help="Username of the owner. Defaults to the first superuser.",
        )

    def handle(self, *args, **options):
        from django.apps import apps

        from live_operations.progress import TextProgress
        from live_operations.runner import task_run

        model_path: str = options["model"]
        owner_username: str | None = options["owner"]

        # Resolve model class
        parts = model_path.split(".")
        if len(parts) != 2:
            raise CommandError(
                f"Expected 'app_label.ModelName', got {model_path!r}."
            )
        app_label, model_name = parts
        try:
            model_cls = apps.get_model(app_label, model_name)
        except LookupError as exc:
            raise CommandError(str(exc)) from exc

        from live_operations.models import LiveOperation

        if not issubclass(model_cls, LiveOperation):
            raise CommandError(
                f"{model_path} does not subclass LiveOperation."
            )

        # Resolve owner
        from django.contrib.auth import get_user_model

        User = get_user_model()
        if owner_username:
            try:
                owner = User.objects.get(**{User.USERNAME_FIELD: owner_username})
            except User.DoesNotExist:
                raise CommandError(f"No user with username {owner_username!r}.")
        else:
            owner = User.objects.filter(is_superuser=True).first()
            if owner is None:
                # Create a minimal superuser so the command works in a fresh DB.
                owner = User.objects.create_superuser(
                    username="admin",
                    email="admin@example.com",
                    password="admin",
                )
                self.stdout.write(
                    self.style.WARNING(
                        "No superuser found — created admin/admin."
                    )
                )

        # Instantiate and run
        op = model_cls.objects.create(owner=owner)
        p = TextProgress(op, stream=self.stdout)

        self.stdout.write(
            self.style.NOTICE(
                f"Running {model_path} (pk={op.pk}) as {owner}…"
            )
        )

        task_run(op, p)

        state = op.get_state()
        if state == "FINISHED_OK":
            self.stdout.write(self.style.SUCCESS(f"Done — {state}"))
        elif state == "CANCELLED":
            self.stdout.write(self.style.WARNING(f"Cancelled — {state}"))
        else:
            self.stdout.write(self.style.ERROR(f"Finished with error — {state}"))
            if op.traceback:
                self.stdout.write(op.traceback)
