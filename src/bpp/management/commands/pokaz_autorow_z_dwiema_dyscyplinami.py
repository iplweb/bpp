from django.core.management import BaseCommand

from ewaluacja_dwudyscyplinowcy.core import (
    pobierz_autorow_z_dwiema_dyscyplinami,
    pobierz_publikacje_autora,
)


class Command(BaseCommand):
    help = """
    Pokazuje autorów z dokładnie dwiema dyscyplinami (2022-2025) i ich prace,
    gdzie subdyscyplina autora jest zgodna z dyscyplinami źródła publikacji.
    """

    def handle(self, *args, **options):
        """Główna logika polecenia."""
        lata = range(2022, 2026)  # 2022-2025

        # Pobierz wszystkich autorów z dwiema dyscyplinami
        autorzy_dict = pobierz_autorow_z_dwiema_dyscyplinami(lata)

        for rok in lata:
            self.stdout.write(f"\n{'=' * 80}")
            self.stdout.write(f"ROK {rok}")
            self.stdout.write(f"{'=' * 80}\n")

            # Filtruj autorów którzy mają dwie dyscypliny w tym roku
            autorzy_w_roku = [
                (autor_id, data)
                for autor_id, data in autorzy_dict.items()
                if rok in data["lata"]
            ]

            if not autorzy_w_roku:
                self.stdout.write(
                    f"  Brak autorów z dwiema dyscyplinami w roku {rok}\n"
                )
                continue

            self.stdout.write(
                f"  Znaleziono {len(autorzy_w_roku)} autorów z dwiema dyscyplinami\n"
            )

            # Dla każdego autora z dwiema dyscyplinami
            for autor_id, autor_data in autorzy_w_roku:
                autor = autor_data["autor"]
                dane_roku = autor_data["lata"][rok]
                dyscyplina_glowna = dane_roku["dyscyplina_glowna"]
                subdyscyplina = dane_roku["subdyscyplina"]

                self.stdout.write(f"\n  Autor: {autor} (ID: {autor.pk})")
                self.stdout.write(
                    f"    Dyscyplina główna: {dyscyplina_glowna.nazwa} ({dyscyplina_glowna.kod})"
                )
                self.stdout.write(
                    f"    Subdyscyplina: {subdyscyplina.nazwa} ({subdyscyplina.kod})"
                )

                # Pobierz publikacje dla tego autora i roku
                publikacje = pobierz_publikacje_autora(autor, subdyscyplina, rok)

                # Filtruj tylko te zgodne
                pasujace_publikacje = [p for p in publikacje if p["zgodna"]]

                if pasujace_publikacje:
                    self.stdout.write(
                        f"\n    Znaleziono {len(pasujace_publikacje)} publikacji, "
                        f"gdzie subdyscyplina jest zgodna z dyscyplinami źródła:"
                    )
                    for pub_data in pasujace_publikacje:
                        pub = pub_data["rekord"]
                        self.stdout.write(
                            f"      - {pub.tytul_oryginalny}, rok: {pub.rok}"
                        )
                else:
                    self.stdout.write(
                        "\n    Brak publikacji zgodnych z subdyscypliną w źródłach."
                    )

        self.stdout.write(f"\n{'=' * 80}")
        self.stdout.write("Zakończono przeglądanie.\n")
