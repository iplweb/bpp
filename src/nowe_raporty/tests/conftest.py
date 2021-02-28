import pytest
from django.contrib.contenttypes.models import ContentType
from flexible_reports.models import Column, Datasource, Report, ReportElement, Table
from model_mommy import mommy

from bpp.models import Wydawnictwo_Zwarte


@pytest.fixture
def raport_autorow(db):
    table = mommy.make(Table)

    mommy.make(Column, parent=table)

    ds = Datasource.objects.create(
        base_model=ContentType.objects.get_for_model(Wydawnictwo_Zwarte),
        dsl_query='tytul_oryginalny = "Wydawnictwo Zwarte"',
    )

    raport = Report.objects.create(
        slug="raport-autorow",
        title="Raport autorów",
        template="""
        "<h1>Raport autora - {{ object }} za
        {% if od_roku == do_roku %}
            rok {{ od_roku }}
        {% else %}
            lata {{ od_roku }} - {{ do_roku }}
        {% endif %}

        </h1>

        {% load django_tables2 %}

        <h2>1. Publikacje w czasopismach naukowych</h2>

        <h3>{{ elements.tabela_1_1.title }}</h3>
        {% render_table elements.tabela_1_1.table %}

        """,
    )

    ReportElement.objects.create(
        datasource=ds,
        table=table,
        slug="tabela_1_1",
        parent=raport,
        title="pani/jadzia",
    )

    return raport
