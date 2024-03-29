# Generated by Django 3.0.14 on 2021-08-07 07:14

# Generated by Django 3.0.14 on 2021-08-05 21:06
import warnings

from django.db import migrations

from bpp.util import pbar


def value(elem, *path, return_none=False):
    v = None
    if elem.versions:
        for _elem in elem.versions:
            if _elem["current"]:
                v = _elem
                break

    # v = elem.current_version

    if v is None:
        warnings.warn(
            f"Model {elem.__class__} with id {elem.mongoId} has NO current_version!"
        )
        if return_none:
            return
        return "[brak current_version]"

    for elem in path:
        if elem in v:
            v = v[elem]
        else:
            if return_none:
                return None
            return f"[brak {elem}]"
    return v


def value_or_none(elem, *path):
    return value(elem, *path, return_none=True)


MAX_TEXT_FIELD_LENGTH = 512


def _pull_up_on_save(elem, pull_up_on_save):
    for attr in pull_up_on_save:
        v = value_or_none(elem, "object", attr)
        if v is not None:
            if isinstance(v, str):
                if len(v) >= MAX_TEXT_FIELD_LENGTH:
                    v = v[:MAX_TEXT_FIELD_LENGTH]
        setattr(elem, attr, v)


def rebuild_table(model, puos):
    for elem in pbar(model.objects.all(), label=f"{model}..."):
        _pull_up_on_save(elem, puos)
        elem.save(update_fields=puos)


def rebuild(apps, schema_editor):
    for model, puos in [
        (
            apps.get_model("pbn_api", "Institution"),
            [
                "name",
                "addressCity",
                "addressStreet",
                "addressStreetNumber",
                "addressPostalCode",
                "polonUid",
            ],
        ),
        (
            apps.get_model("pbn_api", "Journal"),
            ["title", "websiteLink", "issn", "eissn", "mniswId"],
        ),
        (
            apps.get_model("pbn_api", "Publisher"),
            ["publisherName", "mniswId"],
        ),
        (
            apps.get_model("pbn_api", "Scientist"),
            ["lastName", "name", "qualifications", "orcid", "polonUid"],
        ),
        (
            apps.get_model("pbn_api", "Publication"),
            ["title", "doi", "publicUri", "isbn", "year"],
        ),
    ]:
        rebuild_table(model, puos)


class Migration(migrations.Migration):

    dependencies = [
        ("pbn_api", "0019_auto_20210805_2306"),
    ]

    operations = [
        migrations.RunPython(rebuild, migrations.RunPython.noop),
    ]
