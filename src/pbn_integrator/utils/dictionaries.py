"""Integration of dictionary data: languages, countries, disciplines."""

from __future__ import annotations

import warnings

from django.db.models import Q

from bpp.models import Jezyk
from pbn_api.models import Country, Discipline, DisciplineGroup, Language


def integruj_jezyki(client, create_if_not_exists=False):  # noqa: C901
    """Integrate languages from PBN.

    Args:
        client: PBN client.
        create_if_not_exists: Whether to create missing languages in BPP.
    """
    for remote_lang in client.get_languages():
        try:
            lang = Language.objects.get(code=remote_lang["code"])
        except Language.DoesNotExist:
            lang = Language.objects.create(
                code=remote_lang["code"], language=remote_lang["language"]
            )

        if remote_lang["language"] != lang.language:
            lang.language = remote_lang["language"]
            lang.save()

    # Ustaw odpowiedniki w PBN dla jęyzków z bazy danych:
    for elem in Language.objects.all():
        try:
            qry = Q(skrot__istartswith=elem.language.get("639-2")) | Q(
                skrot__iexact=elem.code
            )
            if elem.language.get("639-1"):
                qry |= Q(skrot__iexact=elem.language["639-1"])

            jezyk = Jezyk.objects.get(qry)
        except Jezyk.DoesNotExist:
            if elem.language.get("pl") is not None:
                try:
                    jezyk = Jezyk.objects.get(nazwa__iexact=elem.language.get("pl"))
                except Jezyk.DoesNotExist:
                    if create_if_not_exists:
                        Jezyk.objects.create(
                            nazwa=elem.language.get("pl"),
                            skrot=elem.language.get("639-2"),
                            pbn_uid=elem,
                        )
                    else:
                        warnings.warn(
                            f"Brak jezyka po stronie BPP: {elem}", stacklevel=2
                        )
                    continue
            else:
                if create_if_not_exists:
                    Jezyk.objects.create(
                        nazwa=elem.language.get("en"),
                        skrot=elem.language.get("639-2"),
                        pbn_uid=elem,
                    )
                else:
                    warnings.warn(f"Brak jezyka po stronie BPP: {elem}", stacklevel=2)
                continue

        if jezyk.pbn_uid_id is None:
            jezyk.pbn_uid = elem
            jezyk.save()


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


def integruj_dyscypliny(client):  # noqa: C901
    """Import discipline groups and disciplines from PBN.

    Args:
        client: PBN client.
    """
    # First, ensure all discipline groups exist
    for remote_group in client.get_discipline_groups():
        # Handle both dict and DisciplineGroup model object
        group_id = (
            remote_group.get("id")
            if isinstance(remote_group, dict)
            else remote_group.pk
        )
        try:
            DisciplineGroup.objects.get(pk=group_id)
        except DisciplineGroup.DoesNotExist:
            if isinstance(remote_group, dict):
                DisciplineGroup.objects.create(
                    pk=group_id, **{k: v for k, v in remote_group.items() if k != "id"}
                )
            # else: remote_group is already a DisciplineGroup model object, skip

    # Now create/update disciplines
    for remote_discipline in client.get_disciplines():
        # Handle both dict and Discipline model object
        if isinstance(remote_discipline, dict):
            code = remote_discipline.get("code")
            disc_id = remote_discipline.get("id")
            name = remote_discipline.get("name")
            uuid = remote_discipline.get("uuid")
            # Handle parent_group which could be dict or model object
            parent_group = remote_discipline.get("parent_group")
            if isinstance(parent_group, dict):
                parent_group_id = parent_group.get("id")
            elif hasattr(parent_group, "pk"):
                parent_group_id = parent_group.pk
            else:
                parent_group_id = remote_discipline.get("parent_group_id")
        else:
            code = remote_discipline.code
            disc_id = remote_discipline.pk
            name = remote_discipline.name
            uuid = (
                remote_discipline.uuid if hasattr(remote_discipline, "uuid") else None
            )
            parent_group_id = (
                remote_discipline.parent_group.pk
                if hasattr(remote_discipline, "parent_group")
                and remote_discipline.parent_group
                else None
            )

        try:
            d = Discipline.objects.get(code=code)
        except Discipline.DoesNotExist:
            create_kwargs = {
                "code": code,
                "name": name,
                "parent_group_id": parent_group_id,
                "uuid": uuid,
            }
            if disc_id:
                create_kwargs["pk"] = disc_id
            Discipline.objects.create(**create_kwargs)
            continue

        # Update existing discipline if needed
        if name != d.name:
            d.name = name
            d.save()
