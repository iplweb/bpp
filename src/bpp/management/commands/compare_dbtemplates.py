"""
Django management command to compare dbtemplates.models.Template instances with filesystem templates.

This command compares database-stored templates with their corresponding filesystem counterparts,
showing differences using a unified diff format similar to the Unix diff(1) command.
"""

import difflib
import logging
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

from bpp.util import zaloguj_polkniety_wyjatek

try:
    from dbtemplates.models import Template
except ImportError:
    Template = None

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Compare dbtemplates.models.Template instances with filesystem templates"

    def add_arguments(self, parser):
        parser.add_argument(
            "template_names",
            nargs="*",
            help="Specific template names to compare. If not provided, compares all database templates.",
        )

        parser.add_argument(
            "--list",
            "-l",
            action="store_true",
            help="List all available database templates without comparison",
        )

        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file path. If not specified, output goes to stdout.",
        )

        parser.add_argument(
            "--context-lines",
            "-c",
            type=int,
            default=3,
            help="Number of context lines to show in diff (default: 3)",
        )

        parser.add_argument(
            "--unified",
            "-u",
            action="store_true",
            default=True,
            help="Use unified diff format (default)",
        )

        parser.add_argument(
            "--side-by-side",
            "-s",
            action="store_true",
            help="Use side-by-side diff format",
        )

        parser.add_argument(
            "--ignore-whitespace",
            "-w",
            action="store_true",
            help="Ignore whitespace differences",
        )

        parser.add_argument(
            "--only-display-changed",
            action="store_true",
            help="Only display names of changed templates (no diff output)",
        )

    def handle(self, *args, **options):
        if Template is None:
            raise CommandError(
                "dbtemplates is not installed or not properly configured. "
                "Please install django-dbtemplates."
            )

        # List templates if requested
        if options["list"]:
            self.list_templates()
            return

        templates = self._get_templates_to_compare(options)
        if not templates:
            raise CommandError("No templates to compare")

        output_lines, changed_templates, compared_count, differences_found = (
            self._collect_differences(templates, options)
        )

        self._emit_output(output_lines, changed_templates, options)
        self._emit_summary(compared_count, differences_found)

    def _get_templates_to_compare(self, options):
        """Resolve the set of templates to compare.

        Without explicit ``template_names`` this is every database template;
        otherwise each named template is looked up individually and a warning
        is written to stderr for any that do not exist.
        """
        if not options["template_names"]:
            return Template.objects.all()

        templates = []
        for name in options["template_names"]:
            try:
                templates.append(Template.objects.get(name=name))
            except Template.DoesNotExist:
                self.stderr.write(
                    self.style.WARNING(f"Template '{name}' not found in database")
                )
        return templates

    def _collect_differences(self, templates, options):
        """Walk the templates and gather diff output / changed names.

        Returns ``(output_lines, changed_templates, compared_count,
        differences_found)``.
        """
        output_lines = []
        changed_templates = []
        compared_count = 0
        differences_found = 0

        for template in templates:
            if options["only_display_changed"]:
                # Only check if template has differences, skip full diff.
                if self.template_has_changes(template, options):
                    changed_templates.append(template.name)
                    differences_found += 1
            else:
                # Generate full diff output.
                diff_output = self.compare_template(template, options)
                if diff_output:
                    output_lines.extend(diff_output)
                    differences_found += 1
            compared_count += 1

        return output_lines, changed_templates, compared_count, differences_found

    def _emit_output(self, output_lines, changed_templates, options):
        """Write the collected output to a file or stdout."""
        if options["only_display_changed"]:
            if changed_templates:
                self._write_or_print(
                    "\n".join(changed_templates),
                    options["output"],
                    "Changed template names written to",
                )
        elif output_lines:
            self._write_or_print(
                "\n".join(output_lines),
                options["output"],
                "Differences written to",
            )

    def _write_or_print(self, content, output_path, success_prefix):
        """Print ``content`` to stdout, or write it to ``output_path``.

        On a successful file write, emit ``"{success_prefix} {output_path}"``
        as a SUCCESS message — mirroring the original per-branch wording.
        """
        if not output_path:
            self.stdout.write(content)
            return

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content + "\n")
        except OSError as e:
            raise CommandError(f"Error writing to file: {e}") from e

        self.stdout.write(self.style.SUCCESS(f"{success_prefix} {output_path}"))

    def _emit_summary(self, compared_count, differences_found):
        """Print the final match/difference summary line."""
        if differences_found == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"All {compared_count} templates match their filesystem counterparts"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Found differences in {differences_found} out of {compared_count} templates"
                )
            )

    def list_templates(self):
        """List all database templates"""
        templates = Template.objects.all().order_by("name")

        if not templates:
            self.stdout.write("No templates found in database")
            return

        self.stdout.write(f"Found {templates.count()} templates in database:\n")

        for template in templates:
            # Try to check if filesystem version exists
            fs_exists = (
                "✓"
                if self.get_filesystem_template_content(template.name) is not None
                else "✗"
            )

            self.stdout.write(f"  {fs_exists} {template.name}")

    @staticmethod
    def _normalize_lines(content, options):
        """Split ``content`` into lines, optionally stripping whitespace."""
        if options["ignore_whitespace"]:
            return [line.strip() for line in content.splitlines()]
        return content.splitlines()

    def template_has_changes(self, db_template, options):
        """Check if a template has changes without generating full diff output"""
        fs_content = self.get_filesystem_template_content(db_template.name)

        if fs_content is None:
            # Filesystem template not found - consider this as a change
            return True

        db_lines = self._normalize_lines(db_template.content, options)
        fs_lines = self._normalize_lines(fs_content, options)

        # Check if templates are identical
        return db_lines != fs_lines

    def compare_template(self, db_template, options):
        """Compare a single template and return diff output"""
        fs_content = self.get_filesystem_template_content(db_template.name)

        if fs_content is None:
            return [
                f"--- Template: {db_template.name}",
                "!!! Filesystem template not found",
                "",
            ]

        db_lines = self._normalize_lines(db_template.content, options)
        fs_lines = self._normalize_lines(fs_content, options)

        # Check if templates are identical
        if db_lines == fs_lines:
            return None

        # Generate diff. The ``side_by_side`` flag historically produced the
        # same unified diff as the default, so a single call covers both.
        diff_lines = list(
            difflib.unified_diff(
                fs_lines,
                db_lines,
                fromfile=f"filesystem/{db_template.name}",
                tofile=f"database/{db_template.name}",
                lineterm="",
                n=options["context_lines"],
            )
        )

        if not diff_lines:
            return None

        # Add header and styling
        result = [
            f"{'=' * 60}",
            f"Template: {db_template.name}",
            f"{'=' * 60}",
        ]

        # Apply coloring if not disabled
        if not options["no_color"] and sys.stdout.isatty():
            result.extend(self._colorize_diff(diff_lines))
        else:
            result.extend(diff_lines)

        result.append("")  # Empty line separator
        return result

    def _colorize_diff(self, diff_lines):
        """Apply diff styling to ``diff_lines``.

        Prefixes are checked longest-first so the multi-character markers
        (``+++``/``---``/``@@``) win over the single-character ``+``/``-``,
        matching the original if/elif chain exactly.
        """
        prefix_styles = (
            ("+++", self.style.SUCCESS),
            ("---", self.style.ERROR),
            ("@@", self.style.WARNING),
            ("+", self.style.SUCCESS),
            ("-", self.style.ERROR),
        )

        colored_lines = []
        for line in diff_lines:
            for prefix, style in prefix_styles:
                if line.startswith(prefix):
                    colored_lines.append(style(line))
                    break
            else:
                colored_lines.append(line)
        return colored_lines

    def get_filesystem_template_content(self, template_name):
        """Get template content from filesystem"""
        try:
            # Get the template object to access its origin
            django_template = get_template(template_name)

            # Try to get the template source
            if hasattr(django_template, "template") and hasattr(
                django_template.template, "source"
            ):
                return django_template.template.source

            # Alternative approach: try to find and read the template file directly
            from django.template.loader import find_template

            try:
                template_obj, origin = find_template(template_name)
                if hasattr(origin, "name") and origin.name:
                    # Try to read the file directly
                    template_path = Path(origin.name)
                    if template_path.exists():
                        return template_path.read_text(encoding="utf-8")
            except (TemplateDoesNotExist, AttributeError):
                pass

            # Fallback: render template to get content (might not be exact source)
            # This won't work for templates with context variables, but it's a fallback
            try:
                from django.template import Context

                rendered = django_template.render(Context({}))
                return rendered
            except Exception:
                zaloguj_polkniety_wyjatek(
                    f"Renderowanie szablonu jako fallback do odczytu źródła "
                    f"(template_name={template_name})",
                    logger=logger,
                    do_rollbar=False,
                )

        except TemplateDoesNotExist:
            pass
        except Exception as e:
            zaloguj_polkniety_wyjatek(
                f"Wczytywanie źródła szablonu do porównania "
                f"(template_name={template_name})",
                logger=logger,
                do_rollbar=False,
            )
            # Log the error but continue
            if hasattr(self, "stderr"):
                self.stderr.write(
                    f"Warning: Could not load template {template_name}: {e}"
                )

        return None
