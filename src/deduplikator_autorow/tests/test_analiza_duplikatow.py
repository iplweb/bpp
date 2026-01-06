"""
Tests for analiza_duplikatow function.

This module has been split into smaller, logically organized files:

- test_analiza_duplikatow_basic.py
    Basic duplicate analysis tests: exact match, initials scoring,
    surname variations, empty names, similar names, multiple matches

- test_analiza_duplikatow_scoring.py
    Scoring tests: publication count, academic title, ORCID scoring

- test_analiza_duplikatow_temporal.py
    Temporal analysis tests: common years, close years, medium distance,
    large distance, no publications, scoring impact

- test_analiza_duplikatow_swap.py
    Name/surname swap tests: full swap detection, compound surname handling,
    comparison with regular matching
"""
