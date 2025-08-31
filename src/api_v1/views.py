from rest_framework.routers import APIRootView

from django.utils.safestring import mark_safe


class CustomAPIRootView(APIRootView):
    """
    System BPP - Bibliografia Publikacji Pracowników
    BPP System - Academic Staff Publications Bibliography
    """

    def get_view_name(self):
        return "BPP API"

    def get_view_description(self, html=False):
        if html:
            return mark_safe(
                """
            <div class="description">
                <h3>System BPP - Bibliografia Publikacji Pracowników</h3>
                <h4>BPP System - Academic Staff Publications Bibliography</h4>

                <pre>
Data flows through code,
AI bridges minds and texts —
Knowledge finds its home.
</pre>

                <div style="margin-top: 20px;">
                    <p><strong>PL:</strong> To jest interfejs programistyczny (API) systemu BPP, który umożliwia dostęp
                    do danych bibliograficznych publikacji naukowych.</p>

                    <p><strong>EN:</strong> This is the BPP system API that provides access
                    to bibliographic data of academic publications.</p>
                </div>

                <div style="margin-top: 25px; padding: 15px; background-color: #f8f9fa; border-radius: 5px;">
                    <h5 style="margin-top: 0;"><span class="fi-info"></span> Informacje / Information</h5>

                    <p><strong>PL:</strong> BPP jest wolnym oprogramowaniem o otwartym kodzie źródłowym.</p>
                    <p><strong>EN:</strong> BPP is free and open source software.</p>

                    <div style="margin-top: 15px;">
                        <p><strong>Przydatne linki / Useful links:</strong></p>
                        <ul style="list-style: none; padding-left: 0;">
                            <li><span class="fi-book"></span> <strong>Dokumentacja / Documentation:</strong>
                                <a href="https://bpp.readthedocs.io" target="_blank">bpp.readthedocs.io</a>
                            </li>
                            <li><span class="fi-social-github"></span> <strong>Kod źródłowy / Source code:</strong>
                                <a href="https://github.com/iplweb/bpp/" target="_blank">github.com/iplweb/bpp</a>
                            </li>
                            <li><span class="fi-web"></span> <strong>Strona projektu / Project page:</strong>
                                <a href="https://bpp.iplweb.pl/" target="_blank">bpp.iplweb.pl</a>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
            """
            )
        return self.__doc__

    def get(self, request, *args, **kwargs):
        # Get the standard API root response
        response = super().get(request, *args, **kwargs)

        # Reorganize the endpoints into categories for better readability
        if hasattr(response, "data"):
            endpoints = response.data.copy()

            # Track which endpoints we've categorized
            categorized_endpoints = set()

            # Define what goes into each category
            categories_mapping = {
                "publications": [
                    "wydawnictwo_zwarte",
                    "wydawnictwo_zwarte_autor",
                    "wydawnictwo_zwarte_streszczenie",
                    "wydawnictwo_ciagle",
                    "wydawnictwo_ciagle_autor",
                    "wydawnictwo_ciagle_streszczenie",
                    "wydawnictwo_ciagle_zewnetrzna_baza_danych",
                    "patent",
                    "patent_autor",
                    "praca_doktorska",
                    "praca_habilitacyjna",
                ],
                "authors_and_units": [
                    "autor",
                    "autor_jednostka",
                    "funkcja_autora",
                    "tytul",
                    "recent_author_publications",
                    "jednostka",
                    "wydzial",
                    "uczelnia",
                ],
                "sources_and_publishers": [
                    "zrodlo",
                    "rodzaj_zrodla",
                    "wydawca",
                    "poziom_wydawcy",
                ],
                "metadata": [
                    "charakter_formalny",
                    "typ_kbn",
                    "jezyk",
                    "dyscyplina_naukowa",
                    "konferencja",
                    "seria_wydawnicza",
                    "czas_udostepnienia_openaccess",
                    "nagroda",
                ],
                "reports": ["raport_slotow_uczelnia", "raport_slotow_uczelnia_wiersz"],
            }

            organized_data = {
                "info": {
                    "name_pl": "System BPP - Bibliografia Publikacji Pracowników",
                    "name_en": "BPP System - Academic Staff Publications Bibliography",
                    "description_pl": (
                        "To jest interfejs programistyczny (API) systemu BPP, który umożliwia dostęp "
                        "do danych bibliograficznych publikacji naukowych. "
                        "Kliknij na dowolny z poniższych adresów URL, aby przeglądać dostępne zasoby."
                    ),
                    "description_en": (
                        "This is the BPP system API that provides access "
                        "to bibliographic data of academic publications. "
                        "Click on any of the URLs below to browse available resources."
                    ),
                    "usage_pl": "Kliknij na adresy poniżej, aby eksplorować dostępne dane.",
                    "usage_en": "Click on the addresses below to explore available data.",
                }
            }

            # Initialize all categories
            for category in categories_mapping:
                organized_data[category] = {}

            # Categorize known endpoints
            for category, endpoint_names in categories_mapping.items():
                for endpoint_name in endpoint_names:
                    if endpoint_name in endpoints:
                        organized_data[category][endpoint_name] = endpoints[
                            endpoint_name
                        ]
                        categorized_endpoints.add(endpoint_name)

            # Collect any uncategorized endpoints
            organized_data["other"] = {}
            for endpoint_name, endpoint_url in endpoints.items():
                if endpoint_name not in categorized_endpoints:
                    organized_data["other"][endpoint_name] = endpoint_url

            # Remove empty categories (except info)
            final_data = {"info": organized_data["info"]}
            for category, content in organized_data.items():
                if category != "info" and content:
                    final_data[category] = content

            response.data = final_data

        return response
