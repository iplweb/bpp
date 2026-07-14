"""Walidatory identyfikatorów PBN.

``check_mongoId`` to publiczna nazwa używana przez BPP (m.in. autocomplete
wydawnictwa nadrzędnego) — implementację dostarcza pakiet ``pbn_client``.
"""

from pbn_client import is_valid_object_id

#: Sprawdza, czy to prawidłowy mongoId (objectId) z PBNu.
check_mongoId = is_valid_object_id
