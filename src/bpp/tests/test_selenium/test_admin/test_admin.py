"""
Admin Selenium Tests - Index Module

This file previously contained all admin Selenium tests. The tests have been
split into smaller, logically organized modules for better maintainability:

- test_admin_forms.py
    Tests for admin form field population, auto-completion, and form behavior.
    Includes: field auto-population, character/sheet calculations, points auto-fill,
    author form completion/clearing, custom author names.

- test_admin_parsing.py
    Tests for admin metadata parsing functionality.
    Includes: year extraction from metadata fields, parent publication year lookup.

- test_admin_actions.py
    Tests for admin actions and default behaviors.
    Includes: user creation regression test, default affiliation settings.

All tests are Selenium-based integration tests marked with:
    pytest.mark.slow
    pytest.mark.selenium
"""
