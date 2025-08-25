"""
Django management command to compare dbtemplates.models.Template instances with filesystem templates.

This command compares database-stored templates with their corresponding filesystem counterparts,
showing differences using a unified diff format similar to the Unix diff(1) command.
"""

import difflib
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

try:
    from dbtemplates.models import Template
except ImportError:
    Template = None


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

        # Get templates to compare
        if options["template_names"]:
            templates = []
            for name in options["template_names"]:
                try:
                    template = Template.objects.get(name=name)
                    templates.append(template)
                except Template.DoesNotExist:
                    self.stderr.write(
                        self.style.WARNING(f"Template '{name}' not found in database")
                    )
        else:
            templates = Template.objects.all()

        if not templates:
            raise CommandError("No templates to compare")

        # Prepare output
        output_lines = []
        changed_templates = []
        compared_count = 0
        differences_found = 0

        for template in templates:
            if options["only_display_changed"]:
                # Only check if template has differences, don't generate full diff
                has_changes = self.template_has_changes(template, options)
                if has_changes:
                    changed_templates.append(template.name)
                    differences_found += 1
            else:
                # Generate full diff output
                diff_output = self.compare_template(template, options)
                if diff_output:
                    output_lines.extend(diff_output)
                    differences_found += 1
            compared_count += 1

        # Write output
        if options["only_display_changed"]:
            if changed_templates:
                output_content = "\n".join(changed_templates)

                if options["output"]:
                    try:
                        with open(options["output"], "w", encoding="utf-8") as f:
                            f.write(output_content + "\n")
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Changed template names written to {options["output"]}'
                            )
                        )
                    except OSError as e:
                        raise CommandError(f"Error writing to file: {e}")
                else:
                    self.stdout.write(output_content)
        elif output_lines:
            output_content = "\n".join(output_lines)

            if options["output"]:
                try:
                    with open(options["output"], "w", encoding="utf-8") as f:
                        f.write(output_content + "\n")
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Differences written to {options["output"]}'
                        )
                    )
                except OSError as e:
                    raise CommandError(f"Error writing to file: {e}")
            else:
                self.stdout.write(output_content)

        # Summary
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

    def template_has_changes(self, db_template, options):
        """Check if a template has changes without generating full diff output"""
        fs_content = self.get_filesystem_template_content(db_template.name)

        if fs_content is None:
            # Filesystem template not found - consider this as a change
            return True

        db_content = db_template.content

        # Normalize content if ignoring whitespace
        if options["ignore_whitespace"]:
            db_lines = [line.strip() for line in db_content.splitlines()]
            fs_lines = [line.strip() for line in fs_content.splitlines()]
        else:
            db_lines = db_content.splitlines()
            fs_lines = fs_content.splitlines()

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

        db_content = db_template.content

        # Normalize content if ignoring whitespace
        if options["ignore_whitespace"]:
            db_lines = [line.strip() for line in db_content.splitlines()]
            fs_lines = [line.strip() for line in fs_content.splitlines()]
        else:
            db_lines = db_content.splitlines()
            fs_lines = fs_content.splitlines()

        # Check if templates are identical
        if db_lines == fs_lines:
            return None

        # Generate diff
        if options["side_by_side"]:
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
        else:
            # Unified diff (default)
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
            f"{'='*60}",
            f"Template: {db_template.name}",
            f"{'='*60}",
        ]

        # Apply coloring if not disabled
        if not options["no_color"] and sys.stdout.isatty():
            colored_lines = []
            for line in diff_lines:
                if line.startswith("+++"):
                    colored_lines.append(self.style.SUCCESS(line))
                elif line.startswith("---"):
                    colored_lines.append(self.style.ERROR(line))
                elif line.startswith("@@"):
                    colored_lines.append(self.style.WARNING(line))
                elif line.startswith("+"):
                    colored_lines.append(self.style.SUCCESS(line))
                elif line.startswith("-"):
                    colored_lines.append(self.style.ERROR(line))
                else:
                    colored_lines.append(line)
            result.extend(colored_lines)
        else:
            result.extend(diff_lines)

        result.append("")  # Empty line separator
        return result

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
                pass

        except TemplateDoesNotExist:
            pass
        except Exception as e:
            # Log the error but continue
            if hasattr(self, "stderr"):
                self.stderr.write(
                    f"Warning: Could not load template {template_name}: {e}"
                )

        return None
