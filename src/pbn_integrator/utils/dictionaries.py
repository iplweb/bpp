"""Integration of dictionary data: languages, countries, disciplines."""

from __future__ import annotations

import warnings

from django.db.models import Q

from bpp.models import Jezyk
from pbn_api.models import Country, Discipline, DisciplineGroup, Language


def _sync_remote_languages(client):
    """Create/update local ``Language`` records from the PBN payload."""
    for remote_lang in client.get_languages():
        lang, created = Language.objects.get_or_create(
            code=remote_lang["code"],
            defaults={"language": remote_lang["language"]},
        )
        if not created and remote_lang["language"] != lang.language:
            lang.language = remote_lang["language"]
            lang.save()


def _jezyk_query(elem):
    """Build the ``Q`` lookup matching a BPP ``Jezyk`` to a PBN language."""
    qry = Q(skrot__istartswith=elem.language.get("639-2")) | Q(skrot__iexact=elem.code)
    if elem.language.get("639-1"):
        qry |= Q(skrot__iexact=elem.language["639-1"])
    return qry


def _resolve_missing_jezyk(elem, create_if_not_exists):
    """Handle a PBN language with no skrot/code match.

    Returns a ``Jezyk`` still needing ``pbn_uid`` mapping (matched by name),
    or ``None`` when the element was fully handled (created or warned).
    """
    pl = elem.language.get("pl")
    if pl is not None:
        try:
            return Jezyk.objects.get(nazwa__iexact=pl)
        except Jezyk.DoesNotExist:
            nazwa = pl
    else:
        nazwa = elem.language.get("en")

    if create_if_not_exists:
        Jezyk.objects.create(
            nazwa=nazwa, skrot=elem.language.get("639-2"), pbn_uid=elem
        )
    else:
        warnings.warn(f"Brak jezyka po stronie BPP: {elem}", stacklevel=2)
    return None


def _map_language_to_jezyk(elem, create_if_not_exists):
    """Establish the ``Jezyk.pbn_uid`` mapping for a single PBN language."""
    try:
        jezyk = Jezyk.objects.get(_jezyk_query(elem))
    except Jezyk.DoesNotExist:
        jezyk = _resolve_missing_jezyk(elem, create_if_not_exists)
        if jezyk is None:
            return

    if jezyk.pbn_uid_id is None:
        jezyk.pbn_uid = elem
        jezyk.save()


def integruj_jezyki(client, create_if_not_exists=False):
    """Integrate languages from PBN.

    Args:
        client: PBN client.
        create_if_not_exists: Whether to create missing languages in BPP.
    """
    _sync_remote_languages(client)

    # Ustaw odpowiedniki w PBN dla jęyzków z bazy danych:
    for elem in Language.objects.all():
        _map_language_to_jezyk(elem, create_if_not_exists)


def integruj_kraje(client):
    """Integrate countries from PBN.

    Args:
        client: PBN client.
    """
    for remote_country in client.get_countries():
        try:
            c = Country.objects.get(code=remote_country["code"])
        except Country.DoesNotExist:
            Country.objects.create(
                code=remote_country["code"], description=remote_country["description"]
            )
            continue

        if remote_country["description"] != c.description:
            c.description = remote_country["description"]
            c.save()


def _ensure_discipline_groups(client):
    """Create any missing discipline groups (dict payloads only)."""
    for remote_group in client.get_discipline_groups():
        is_dict = isinstance(remote_group, dict)
        group_id = remote_group.get("id") if is_dict else remote_group.pk
        if DisciplineGroup.objects.filter(pk=group_id).exists():
            continue
        if is_dict:
            DisciplineGroup.objects.create(
                pk=group_id,
                **{k: v for k, v in remote_group.items() if k != "id"},
            )
        # else: remote_group is a DisciplineGroup model object missing from
        # the DB -- skip, as the original code did.


def _parent_group_id_from_dict(remote_discipline):
    """Resolve ``parent_group_id`` for a dict discipline payload."""
    parent_group = remote_discipline.get("parent_group")
    if isinstance(parent_group, dict):
        return parent_group.get("id")
    if hasattr(parent_group, "pk"):
        return parent_group.pk
    return remote_discipline.get("parent_group_id")


def _discipline_fields(remote_discipline):
    """Normalize a dict-or-model discipline payload into a field mapping."""
    if isinstance(remote_discipline, dict):
        return {
            "code": remote_discipline.get("code"),
            "disc_id": remote_discipline.get("id"),
            "name": remote_discipline.get("name"),
            "uuid": remote_discipline.get("uuid"),
            "parent_group_id": _parent_group_id_from_dict(remote_discipline),
        }

    parent_group = getattr(remote_discipline, "parent_group", None)
    return {
        "code": remote_discipline.code,
        "disc_id": remote_discipline.pk,
        "name": remote_discipline.name,
        "uuid": getattr(remote_discipline, "uuid", None),
        "parent_group_id": parent_group.pk if parent_group else None,
    }


def _upsert_discipline(fields):
    """Create a missing discipline or update its name in place."""
    try:
        d = Discipline.objects.get(code=fields["code"])
    except Discipline.DoesNotExist:
        create_kwargs = {
            "code": fields["code"],
            "name": fields["name"],
            "parent_group_id": fields["parent_group_id"],
            "uuid": fields["uuid"],
        }
        if fields["disc_id"]:
            create_kwargs["pk"] = fields["disc_id"]
        Discipline.objects.create(**create_kwargs)
        return

    if fields["name"] != d.name:
        d.name = fields["name"]
        d.save()


def integruj_dyscypliny(client):
    """Import discipline groups and disciplines from PBN.

    Args:
        client: PBN client.
    """
    _ensure_discipline_groups(client)
    for remote_discipline in client.get_disciplines():
        _upsert_discipline(_discipline_fields(remote_discipline))
