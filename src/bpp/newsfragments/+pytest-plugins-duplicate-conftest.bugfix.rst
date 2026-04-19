Naprawiono ``ValueError: Plugin already registered under a different
name`` przy zbieraniu testów — ``fixtures.conftest`` został usunięty
z listy ``pytest_plugins`` w ``src/conftest.py``. Plik ``conftest.py``
jest auto-rejestrowany przez pytest pod pełną ścieżką, więc
równoległa rejestracja pod nazwą moduły powodowała kolizję.
