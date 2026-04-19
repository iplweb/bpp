"""django_pg_baseline — fast bootstrap of test databases from pg_dump.

Reusable Django app: installs a monkey patch on Django's test database
creation so a baseline pg_dump is loaded immediately after CREATE
DATABASE, turning hundreds of migrations into a few-second psql import.
"""
