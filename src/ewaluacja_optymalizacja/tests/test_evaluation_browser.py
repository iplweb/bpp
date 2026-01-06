"""Testy dla przeglądarki ewaluacji.

UWAGA: Ten plik został podzielony na mniejsze moduły testowe.
Testy znajdują się teraz w następujących plikach:

- test_evaluation_browser_helpers.py
    Testy funkcji pomocniczych:
    - _get_reported_disciplines
    - _snapshot_discipline_points
    - _get_discipline_summary
    - _get_filter_options
    - _author_has_two_disciplines
    - _get_filtered_publications

    Zawiera również wspólne fixtures:
    - uczelnia
    - dyscyplina_raportowana
    - dyscyplina_druga
    - autor_z_dyscyplina
    - autor_dwudyscyplinowy
    - publikacja_ciagle
    - publikacja_zwarta

- test_evaluation_browser_views.py
    Testy widoków HTTP:
    - test_evaluation_browser_requires_login
    - test_evaluation_browser_renders
    - test_browser_summary_htmx
    - test_browser_table_htmx
    - test_browser_table_with_filters
    - test_browser_toggle_pin_requires_post
    - test_browser_toggle_pin_invalid_model_type
    - test_browser_toggle_pin_record_not_found
    - test_browser_swap_discipline_requires_two_disciplines
    - test_browser_recalc_status

- test_evaluation_browser_models.py
    Testy modeli:
    - test_status_przegladarka_recalc_singleton
    - test_status_przegladarka_recalc_rozpocznij
    - test_status_przegladarka_recalc_zakoncz
"""
