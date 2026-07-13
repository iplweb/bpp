"""Property ``ImportSession.status_badge_class`` — mapowanie statusu na klasę
koloru Foundation. Zielony (``success``) TYLKO dla „Zakończono"; błąd →
czerwony; aktywne przetwarzanie → pomarańcz; reszta (w toku) → szary."""

import pytest

from importer_publikacji.models import ImportSession

S = ImportSession.Status


@pytest.mark.parametrize(
    "status,expected",
    [
        (S.COMPLETED, "success"),
        (S.IMPORT_FAILED, "alert"),
        (S.FETCHING, "warning"),
        (S.CREATING, "warning"),
        (S.FETCHED, "secondary"),
        (S.VERIFIED, "secondary"),
        (S.SOURCE_MATCHED, "secondary"),
        (S.AUTHORS_MATCHED, "secondary"),
        (S.PUNKTACJA, "secondary"),
        (S.PBN_CHECK, "secondary"),
        (S.REVIEW, "secondary"),
    ],
)
def test_status_badge_class(status, expected):
    # Property czysto obliczeniowa — instancja bez zapisu do bazy wystarcza.
    assert ImportSession(status=status).status_badge_class == expected
