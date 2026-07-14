import pytest

from pbn_client.exceptions import HttpException, ResourceLockedException
from pbn_client.mixins.institutions import InstitutionsProfileMixin


class _LockedTransport:
    def delete(self, url, body):
        content = (
            '{"message": "Locked", "description": "Publikacja zostało '
            "tymczasowo zablokowane z uwagi na równoległą operację. "
            'Prosimy spróbować ponownie."}'
        )
        raise HttpException(400, url, content)


def test_delete_all_statements_preserves_locked_response_context():
    client = InstitutionsProfileMixin()
    client.transport = _LockedTransport()

    with pytest.raises(ResourceLockedException) as exc_info:
        client.delete_all_publication_statements("publication-id")

    assert exc_info.value.status_code == 400
    assert exc_info.value.url.endswith("/publication-id")
    assert exc_info.value.json["message"] == "Locked"
