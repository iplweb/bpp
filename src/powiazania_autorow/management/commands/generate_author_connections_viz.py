"""
Management command to generate author connections visualization using Sigma.js.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ...core import calculate_author_connections
from ...visualization import generate_sigma_visualization, generate_visualization_html


class Command(BaseCommand):
    help = "Generate Sigma.js visualization of author connections"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Output file path for the JavaScript file",
        )
        parser.add_argument(
            "--html",
            action="store_true",
            help="Generate standalone HTML file instead of just JavaScript",
        )
        parser.add_argument(
            "--min-connections",
            type=int,
            default=2,
            help="Minimum number of shared publications to include (default: 2)",
        )
        parser.add_argument(
            "--max-nodes",
            type=int,
            default=300,
            help="Maximum number of authors to include (default: 300)",
        )
        parser.add_argument(
            "--recalculate",
            action="store_true",
            help="Recalculate author connections before generating visualization",
        )
        parser.add_argument(
            "--static", action="store_true", help="Save to Django static directory"
        )
        parser.add_argument(
            "--layout",
            type=str,
            choices=["force", "circular", "random"],
            default="force",
            help="Graph layout algorithm (default: force)",
        )

    def handle(self, *args, **options):
        # Recalculate connections if requested
        if options["recalculate"]:
            self.stdout.write(self.style.WARNING("Recalculating author connections..."))
            total = calculate_author_connections()
            self.stdout.write(
                self.style.SUCCESS(f"Calculated {total} author connections")
            )

        # Determine output path
        output_path = options["output"]

        if options["static"]:
            # Save to static directory
            static_dir = (
                Path(settings.BASE_DIR)
                / "bpp"
                / "static"
                / "bpp"
                / "js"
                / "visualizations"
            )
            static_dir.mkdir(parents=True, exist_ok=True)

            if options["html"]:
                output_path = static_dir / "author_connections.html"
            else:
                output_path = static_dir / "author_connections.js"

        # Generate visualization
        self.stdout.write("Generating Sigma.js visualization...")

        try:
            if options["html"]:
                result = generate_visualization_html(
                    output_path=output_path,
                    min_connections=options["min_connections"],
                    max_nodes=options["max_nodes"],
                    layout=options["layout"],
                )
            else:
                result = generate_sigma_visualization(
                    output_path=output_path,
                    min_connections=options["min_connections"],
                    max_nodes=options["max_nodes"],
                    layout=options["layout"],
                )

            if output_path:
                self.stdout.write(
                    self.style.SUCCESS(f"Visualization saved to: {output_path}")
                )

                # If saved to static, show the URL
                if options["static"]:
                    if options["html"]:
                        url = "/static/bpp/js/visualizations/author_connections.html"
                    else:
                        url = "/static/bpp/js/visualizations/author_connections.js"
                    self.stdout.write(self.style.SUCCESS(f"Available at: {url}"))
            else:
                # Output to stdout
                self.stdout.write(result)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error generating visualization: {str(e)}")
            )
            raise
