"""BPP-side override of ``dynamic_admin_columns`` migrations.

Settings register this module via ``MIGRATION_MODULES`` so Django
loads our state-only ``0001_initial`` instead of the package's
DDL-emitting one — every BPP database (legacy or freshly bootstrapped
from baseline.sql) already has the ``dynamic_columns_*`` tables, so
running ``CREATE TABLE`` again would always conflict.

A companion BPP migration (``bpp.0416_rename_dynamic_columns_to_admin``)
applies the per-user schema delta (adds ``user_id`` + conditional
unique indexes) on databases that still hold the pre-0.2 schema.
"""
