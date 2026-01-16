"""Data integration utilities for synchronizing PBN publications and statements"""

import io
import sys

from bpp.models import Dyscyplina_Naukowa, Jednostka, Rodzaj_Zrodla
from pbn_integrator.importer import importuj_publikacje_po_pbn_uid_id
from pbn_integrator.utils import (
    integruj_oswiadczenia_z_instytucji,
    integruj_publikacje_instytucji,
)

from .base import ImportStepBase


class TeeWriter:
    """A writer that writes to both the original stream and a buffer"""

    def __init__(self, original_stream, buffer):
        self.original = original_stream
        self.buffer = buffer

    def write(self, data):
        # Write to both original and buffer
        self.original.write(data)
        self.buffer.write(data)

    def flush(self):
        self.original.flush()
        self.buffer.flush()

    def __getattr__(self, attr):
        # Delegate all other attributes to the original stream
        return getattr(self.original, attr)


class OutputCapture:
    """Capture stdout and stderr output during operations"""

    def __init__(self, tee_mode=False):
        """
        Initialize output capture.

        Args:
            tee_mode: If True, output is both captured AND displayed (tee mode).
                     If False, output is only captured (silent mode).
        """
        self.tee_mode = tee_mode
        self.stdout_buffer = io.StringIO()
        self.stderr_buffer = io.StringIO()
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

    def __enter__(self):
        if self.tee_mode:
            # In tee mode, write to both original and buffer
            sys.stdout = TeeWriter(self.original_stdout, self.stdout_buffer)
            sys.stderr = TeeWriter(self.original_stderr, self.stderr_buffer)
        else:
            # In silent mode, only write to buffer
            sys.stdout = self.stdout_buffer
            sys.stderr = self.stderr_buffer
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

    def get_output(self):
        """Get captured stdout output"""
        return self.stdout_buffer.getvalue()

    def get_error(self):
        """Get captured stderr output"""
        return self.stderr_buffer.getvalue()

    def get_combined(self):
        """Get combined stdout and stderr output"""
        output = []
        stdout_val = self.get_output()
        stderr_val = self.get_error()

        if stdout_val:
            output.append("=== STDOUT ===")
            output.append(stdout_val)

        if stderr_val:
            output.append("=== STDERR ===")
            output.append(stderr_val)

        return "\n".join(output)


class DataIntegrator(ImportStepBase):
    """Integrate new data from PBN - publications and statements"""

    step_name = "data_integration"
    step_description = "Integracja nowych danych"

    def __init__(self, session, client=None):
        super().__init__(session, client)
        self.default_jednostka = None
        self.captured_output = []
        # Show output in real-time while also capturing it for logs
        self.tee_mode = True  # Set to False to capture silently without displaying

    def _setup_default_jednostka(self):
        """Setup default unit for integration."""
        jednostka_id = self.session.config.get("default_jednostka_id")
        if jednostka_id:
            self.default_jednostka = Jednostka.objects.get(pk=jednostka_id)
        else:
            self.default_jednostka = Jednostka.objects.filter(
                nazwa="Jednostka Domyślna"
            ).first()

        if not self.default_jednostka:
            raise ValueError("Nie znaleziono domyślnej jednostki dla integracji danych")

    def _store_captured_output(self, capture, section_name, log_msg):
        """Store and log captured output from integration step."""
        captured_text = capture.get_combined()
        if captured_text:
            self.captured_output.append(f"=== {section_name} ===\n{captured_text}")
            self.log(
                "debug",
                log_msg,
                {"output": captured_text[:5000]},
            )  # Limit to 5000 chars in log

    def _integrate_publications(self):
        """Integrate publications from institution."""
        self.log("info", "Rozpoczęcie integracji publikacji instytucji")

        try:
            subtask_callback = self.create_subtask_progress("Integracja publikacji")

            with OutputCapture(tee_mode=self.tee_mode) as capture:
                integruj_publikacje_instytucji(
                    callback=subtask_callback,
                    use_threads=True,
                )

            self._store_captured_output(
                capture,
                "Integracja publikacji instytucji",
                "Captured output from publication integration",
            )

            self.log("success", "Publikacje instytucji zintegrowane pomyślnie")
        except Exception as e:
            self.handle_error(e, "Błąd podczas integracji publikacji instytucji")
        finally:
            self.clear_subtask_progress()

    def _integrate_statements(self):
        """Integrate statements with missing publication callback."""
        self.log("info", "Rozpoczęcie integracji oświadczeń")

        rodzaj_periodyk = Rodzaj_Zrodla.objects.get(nazwa="periodyk")
        dyscypliny_cache = {d.nazwa: d for d in Dyscyplina_Naukowa.objects.all()}

        def missing_publication_callback(pbn_uid_id):
            """Import missing publication when found during statement integration"""
            self.log("info", f"Importowanie brakującej publikacji: {pbn_uid_id}")
            return importuj_publikacje_po_pbn_uid_id(
                pbn_uid_id,
                client=self.client,
                default_jednostka=self.default_jednostka,
                rodzaj_periodyk=rodzaj_periodyk,
                dyscypliny_cache=dyscypliny_cache,
            )

        try:
            subtask_callback = self.create_subtask_progress("Integracja oświadczeń")

            with OutputCapture(tee_mode=self.tee_mode) as capture:
                integruj_oswiadczenia_z_instytucji(
                    missing_publication_callback=missing_publication_callback,
                    callback=subtask_callback,
                )

            self._store_captured_output(
                capture,
                "Integracja oświadczeń",
                "Captured output from statement integration",
            )

            if hasattr(self.session, "statistics"):
                stats = self.session.statistics
                stats.data_integrated = True
                stats.save()

            self.log("success", "Oświadczenia zintegrowane pomyślnie")

        except Exception as e:
            self.handle_error(e, "Błąd podczas integracji oświadczeń")
        finally:
            self.clear_subtask_progress()

    def _finalize_and_log_output(self):
        """Save complete captured output as a single log entry."""
        if self.captured_output:
            complete_output = "\n\n".join(self.captured_output)
            self.log(
                "info",
                "Complete captured output from data integration",
                {"full_output": complete_output},
            )

    def run(self):
        """Execute data integration"""
        self._setup_default_jednostka()

        total_steps = 2

        # Step 1: Integrate publications from institution
        self.update_progress(0, total_steps, "Integrowanie publikacji instytucji")
        self._integrate_publications()

        # Check cancellation before proceeding
        if self.check_cancelled():
            return {"cancelled": True}

        # Step 2: Integrate statements with missing publication callback
        self.update_progress(1, total_steps, "Integrowanie oświadczeń")
        self._integrate_statements()

        # Final progress update
        self.update_progress(2, total_steps, "Zakończono integrację danych")
        self._finalize_and_log_output()

        return {
            "data_integrated": True,
            "error_count": len(self.errors),
            "message": "Integracja danych zakończona",
            "captured_output_lines": (
                len("\n".join(self.captured_output).splitlines())
                if self.captured_output
                else 0
            ),
        }
