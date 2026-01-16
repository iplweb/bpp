"""Initial setup for PBN import - languages, countries, disciplines"""

from bpp.models import Uczelnia
from import_common.core import matchuj_uczelnie
from pbn_integrator.utils import (
    integruj_jezyki,
    integruj_kraje,
    pobierz_instytucje_polon,
)

from .base import ImportStepBase


class InitialSetup(ImportStepBase):
    """Handle initial setup: languages, countries, disciplines, and institution matching"""

    step_name = "initial_setup"
    step_description = "Konfiguracja początkowa"

    def run(self):
        """Execute initial setup"""
        # Check if we have a PBN client
        if self.client is None:
            self.log("warning", "Brak klienta PBN - próba utworzenia")
            # Try to get or create PBN client
            uczelnia = Uczelnia.objects.get_default()
            if uczelnia:
                try:
                    self.client = uczelnia.pbn_client()
                    self.log("info", "Klient PBN utworzony pomyślnie")
                except Exception as e:
                    self.log("warning", f"Nie można utworzyć klienta PBN: {e}")
                    # For initial import, we might not have PBN credentials yet
                    # Create minimal setup without PBN API calls
                    self.log(
                        "info",
                        "Uruchamianie minimalnej konfiguracji początkowej bez API PBN",
                    )
                    return self._run_minimal_setup(uczelnia)

        # Step 1: Languages
        self.update_progress(0, 4, "Importowanie języków")
        self.log("info", "Integracja języków")
        try:
            integruj_jezyki(self.client, create_if_not_exists=True)
        except Exception as e:
            error_msg = str(e)
            # Check if it's an authorization error - this is critical and should stop the import
            if self.is_authorization_error(e):
                self.log("critical", f"Brak autoryzacji PBN: {error_msg}")
                raise Exception(f"Brak autoryzacji PBN: {error_msg}") from e

            # For other errors, we can try minimal setup
            self.log("warning", f"Nie można zintegrować języków z PBN: {error_msg}")
            self.log("info", "Próba uruchomienia minimalnej konfiguracji")
            return self._run_minimal_setup(Uczelnia.objects.get_default())

        # Step 2: Countries
        self.update_progress(1, 4, "Importowanie krajów")
        self.log("info", "Integracja krajów")
        try:
            integruj_kraje(self.client)
        except Exception as e:
            self.handle_pbn_error(e, "Nie udało się zintegrować krajów")

        # Step 3: Disciplines
        self.update_progress(2, 4, "Pobieranie dyscyplin")
        self.log("info", "Pobieranie i synchronizacja dyscyplin")
        try:
            self.client.download_disciplines()
            self.client.sync_disciplines()
        except Exception as e:
            self.handle_pbn_error(e, "Nie udało się pobrać dyscyplin")

        # Step 4: Institutions and auto-match Uczelnia
        self.update_progress(3, 4, "Pobieranie instytucji i dopasowywanie uczelni")
        self.log("info", "Pobieranie instytucji z POLON")

        # Create progress callback for sub-task tracking
        subtask_callback = self.create_subtask_progress("Pobieranie instytucji")

        try:
            pobierz_instytucje_polon(self.client, callback=subtask_callback)
        except Exception as e:
            self.handle_pbn_error(e, "Nie udało się pobrać instytucji")
        finally:
            self.clear_subtask_progress()

        # Auto-match Uczelnia and enable PBN integration
        uczelnia = Uczelnia.objects.get_default()
        self._finalize_uczelnia_setup(uczelnia)

        self.update_progress(4, 4, "Zakończono konfigurację początkową")

        return {
            "languages_integrated": True,
            "countries_integrated": True,
            "disciplines_synced": True,
            "institutions_fetched": True,
            "uczelnia_matched": uczelnia.pbn_uid_id is not None if uczelnia else False,
        }

    def _finalize_uczelnia_setup(self, uczelnia):
        """Finalize uczelnia setup: auto-match and enable PBN integration"""
        if uczelnia is None:
            return

        # Auto-match if PBN UID not set
        if uczelnia.pbn_uid_id is None:
            self._auto_match_uczelnia(uczelnia)

        # Enable PBN integration
        if not uczelnia.pbn_integracja:
            uczelnia.pbn_integracja = True
            uczelnia.save(update_fields=["pbn_integracja"])
            self.log("info", "Włączono integrację PBN dla uczelni")

    def _auto_match_uczelnia(self, uczelnia):
        """Try to automatically match uczelnia to PBN Institution"""
        self.log("info", f"Próba automatycznego dopasowania uczelni: {uczelnia.nazwa}")
        matched = matchuj_uczelnie(uczelnia.nazwa)

        if matched:
            uczelnia.pbn_uid = matched
            uczelnia.save()
            self.log(
                "success",
                f"Pomyślnie dopasowano uczelnię do PBN UID: {uczelnia.pbn_uid_id}",
            )

            # Store in session config for later reference
            self.session.config["uczelnia_pbn_uid"] = uczelnia.pbn_uid_id
            self.session.config["uczelnia_auto_matched"] = True
            self.session.save()
        else:
            self.log(
                "warning",
                f"Nie można automatycznie dopasować uczelni '{uczelnia.nazwa}'. "
                "Wymagany ręczny wybór.",
                {"uczelnia_nazwa": uczelnia.nazwa},
            )

            # Store warning in session
            self.session.config["uczelnia_match_required"] = True
            self.session.config["uczelnia_nazwa"] = uczelnia.nazwa
            self.session.save()

            # Don't fail the import, just warn
            self.errors.append(
                f"Uczelnia '{uczelnia.nazwa}' wymaga ręcznego wyboru PBN UID"
            )

    def _run_minimal_setup(self, uczelnia):
        """Run minimal setup without PBN API calls - just configure the basics"""
        # Enable PBN integration flag
        if uczelnia and not uczelnia.pbn_integracja:
            uczelnia.pbn_integracja = True
            uczelnia.save(update_fields=["pbn_integracja"])
            self.log("info", "Włączono flagę integracji PBN dla uczelni")

        # Create basic languages if they don't exist
        from bpp.models import Jezyk

        basic_languages = [
            {"nazwa": "polski", "skrot": "pl"},
            {"nazwa": "angielski", "skrot": "en"},
            {"nazwa": "niemiecki", "skrot": "de"},
            {"nazwa": "francuski", "skrot": "fr"},
        ]

        for lang_data in basic_languages:
            # Try to get by nazwa first (unique field), then by skrot
            try:
                Jezyk.objects.get(nazwa=lang_data["nazwa"])
            except Jezyk.DoesNotExist:
                try:
                    Jezyk.objects.get(skrot=lang_data["skrot"])
                except Jezyk.DoesNotExist:
                    Jezyk.objects.create(
                        nazwa=lang_data["nazwa"], skrot=lang_data["skrot"]
                    )

        self.log("info", "Utworzono podstawowe wpisy języków")

        # Create basic disciplines if they don't exist
        from bpp.models import Dyscyplina_Naukowa

        basic_disciplines = [
            {"nazwa": "informatyka", "kod": "2.3"},
            {"nazwa": "informatyka techniczna i telekomunikacja", "kod": "2.3"},
            {"nazwa": "nauki medyczne", "kod": "3.1"},
            {"nazwa": "nauki farmaceutyczne", "kod": "3.2"},
        ]

        created_count = 0
        for disc_data in basic_disciplines:
            _, created = Dyscyplina_Naukowa.objects.get_or_create(
                kod=disc_data["kod"], defaults={"nazwa": disc_data["nazwa"]}
            )
            if created:
                created_count += 1

        if created_count > 0:
            self.log("info", f"Utworzono {created_count} podstawowych wpisów dyscyplin")
        else:
            self.log("info", "Podstawowe dyscypliny już istnieją")

        self.update_progress(4, 4, "Zakończono minimalną konfigurację początkową")

        return {
            "languages_integrated": False,
            "countries_integrated": False,
            "disciplines_synced": False,
            "institutions_fetched": False,
            "uczelnia_matched": False,
            "minimal_setup": True,
            "message": "Minimalna konfiguracja zakończona - wymagane dane uwierzytelniające PBN do pełnego importu",
        }
