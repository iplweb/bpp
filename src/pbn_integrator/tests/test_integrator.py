"""PBN Integrator Tests - Module Index.

This file previously contained all tests for the pbn_integrator module.
The tests have been split into smaller, logically organized modules for better
maintainability and readability.

Test Modules
------------

test_integrator_sync.py
    Publication synchronization tests including:
    - test_wydawnictwa_zwarte_do_synchronizacji
    - test_wydawnictwa_ciagle_do_synchronizacji
    - TestPublicationSynchronization class

test_integrator_helpers.py
    Helper function tests including:
    - TestAssertDictionaryEmpty class
    - TestPbnKeywordsToSlowaKluczowe class

test_integrator_import.py
    Import function tests including:
    - TestDopiszzJednoZrodlo class (journal import)
    - TestImportujJednegoWydawce class (publisher import)

test_integrator_edge_cases.py
    Edge cases and performance tests including:
    - TestEdgeCases class
    - TestPerformanceCharacteristics class

Running Tests
-------------

To run all integrator tests::

    uv run pytest src/pbn_integrator/tests/ -v

To run a specific test module::

    uv run pytest src/pbn_integrator/tests/test_integrator_sync.py -v

To run a specific test class::

    uv run pytest src/pbn_integrator/tests/test_integrator_helpers.py::TestAssertDictionaryEmpty -v
"""
