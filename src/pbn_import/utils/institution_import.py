"""Institution import utilities"""

from .base import ImportStepBase

from bpp.models import Jednostka, Uczelnia, Wydzial


def zrob_skrot(s: str) -> str:
    """Create abbreviation from string - extract uppercase and non-alphanumeric"""
    res = ""
    for elem in s:
        if elem.isspace():
            continue
        if not elem.isalnum():
            res += elem
            continue
        if elem.isupper():
            res += elem
    return res


class InstitutionImporter(ImportStepBase):
    """Setup default institutions and departments"""

    step_name = "institution_setup"
    step_description = "Konfiguracja jednostek i wydziałów"

    def __init__(
        self,
        session,
        client=None,
        wydzial_domyslny="Wydział Domyślny",
        wydzial_domyslny_skrot=None,
    ):
        super().__init__(session, client)
        self.wydzial_domyslny = wydzial_domyslny
        self.wydzial_domyslny_skrot = wydzial_domyslny_skrot or zrob_skrot(
            wydzial_domyslny
        )

    def run(self):
        """Setup default institutions"""
        uczelnia = Uczelnia.objects.get_default()

        if not uczelnia:
            raise ValueError(
                "Nie znaleziono domyślnej Uczelni. Nie można kontynuować konfiguracji instytucji."
            )

        # Create default department
        self.update_progress(0, 3, "Tworzenie domyślnego wydziału")
        wydzial, created = Wydzial.objects.get_or_create(
            nazwa=self.wydzial_domyslny,
            skrot=self.wydzial_domyslny_skrot,
            uczelnia=uczelnia,
        )

        if created:
            self.log("info", f"Created default department: {wydzial.nazwa}")
        else:
            self.log("info", f"Using existing department: {wydzial.nazwa}")

        # Create default unit
        self.update_progress(1, 3, "Tworzenie jednostki domyślnej")
        jednostka, created = Jednostka.objects.get_or_create(
            nazwa="Jednostka Domyślna",
            skrot="JD",
            uczelnia=uczelnia,
        )

        if created:
            self.log("info", "Created default unit: Jednostka Domyślna")

        # Link unit to department
        if not jednostka.jednostka_wydzial_set.filter(wydzial=wydzial).exists():
            jednostka.jednostka_wydzial_set.create(wydzial=wydzial)
            self.log(
                "info", f"Linked unit {jednostka.nazwa} to department {wydzial.nazwa}"
            )

        # Create foreign unit
        self.update_progress(2, 3, "Tworzenie obcej jednostki")
        obca_jednostka, created = Jednostka.objects.get_or_create(
            nazwa="Obca jednostka",
            skrot="O",
            uczelnia=uczelnia,
            skupia_pracownikow=False,
        )

        if created:
            self.log("info", "Created foreign unit: Obca jednostka")

        # Link foreign unit to department
        if not obca_jednostka.jednostka_wydzial_set.filter(wydzial=wydzial).exists():
            obca_jednostka.jednostka_wydzial_set.create(wydzial=wydzial)
            self.log("info", f"Linked foreign unit to department {wydzial.nazwa}")

        # Set foreign unit on Uczelnia
        if uczelnia.obca_jednostka != obca_jednostka:
            uczelnia.obca_jednostka = obca_jednostka
            uczelnia.save()
            self.log("info", "Set foreign unit on Uczelnia")

        self.update_progress(3, 3, "Zakończono konfigurację jednostek")

        # Store in session config
        self.session.config.update(
            {
                "default_jednostka_id": jednostka.id,
                "obca_jednostka_id": obca_jednostka.id,
                "wydzial_id": wydzial.id,
            }
        )
        self.session.save()

        return {
            "wydzial": wydzial,
            "jednostka": jednostka,
            "obca_jednostka": obca_jednostka,
        }
