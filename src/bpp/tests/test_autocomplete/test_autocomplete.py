"""
Autocomplete tests - module index.

This file previously contained all autocomplete tests. The tests have been
reorganized into smaller, logically grouped modules for better maintainability:

- test_autocomplete_security.py
    Security tests including SQL injection prevention, input sanitization,
    and query truncation behavior.

- test_autocomplete_authors.py
    Author-related autocomplete tests including discipline assignment,
    author creation, and status korekty autocomplete.

- test_autocomplete_organizations.py
    Organization and unit-related tests including jednostka, wydawca,
    and wydawnictwo nadrzedne autocomplete.

- test_autocomplete_publications.py
    Publication and navigation autocomplete tests including PBN Publication
    and Journal autocomplete, navigation autocomplete, and konferencja tests.

To run all autocomplete tests:
    pytest src/bpp/tests/test_autocomplete/

To run a specific module:
    pytest src/bpp/tests/test_autocomplete/test_autocomplete_security.py
"""
