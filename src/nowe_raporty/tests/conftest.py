import pytest
from flexible_reports.models import Column, Datasource, Report, ReportElement, Table
from model_bakery import baker

from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType

from bpp.const import GR_RAPORTY_WYSWIETLANIE
from bpp.models import Wydawnictwo_Zwarte


@pytest.fixture
def generuj_raporty_app(app, normal_django_user):
    # To samo co ``app`` czyli aplikacja WebTest z zalogowanym ``normal_django_user``
    # ale użytkownik ma grupę "generuj raporty":
    normal_django_user.groups.add(
        Group.objects.get_or_create(name=GR_RAPORTY_WYSWIETLANIE)[0]
    )
    return app


@pytest.fixture
def raport_autorow(db):
    table = baker.make(Table)

    baker.make(Column, parent=table)

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
