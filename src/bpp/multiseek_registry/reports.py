from .fields import PunktacjaWewnetrznaReportType, ReportType, multiseek_fields  # noqa

multiseek_report_types = [
    ReportType("list", "lista"),
    ReportType("table", "tabela"),
    PunktacjaWewnetrznaReportType(
        "pkt_wewn", "punktacja sumaryczna z punktacją wewnętrzna"
    ),
    ReportType("pkt_wewn_bez", "punktacja sumaryczna"),
    ReportType("numer_list", "numerowana lista z uwagami", public=False),
    ReportType("table_cytowania", "tabela z liczbą cytowań", public=False),
    PunktacjaWewnetrznaReportType(
        "pkt_wewn_cytowania",
        "punktacja sumaryczna z punktacją wewnętrzna z liczbą cytowań",
        public=False,
    ),
    ReportType(
        "pkt_wewn_bez_cytowania", "punktacja sumaryczna z liczbą cytowań", public=False
    ),
]
