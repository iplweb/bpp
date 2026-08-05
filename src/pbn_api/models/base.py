"""Backward-compatible imports for abstract PBN Django models."""

from django_pbn_client.models import (
    MAX_TEXT_FIELD_LENGTH,
    BasePBNModel,
    BasePBNMongoDBModel,
)

__all__ = [
    "MAX_TEXT_FIELD_LENGTH",
    "BasePBNModel",
    "BasePBNMongoDBModel",
]
