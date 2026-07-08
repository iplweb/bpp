"""Serializacja wyników Multiseek do plików eksportu (CSV / XLSX).

Wydzielone z bpp/views/mymultiseek.py — widok trzyma routing i stan sesji,
ten moduł zamienia queryset Rekordów na gotową odpowiedź HTTP z plikiem.
"""

import csv
import html
import io
import re

from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.http import content_disposition_header

from bpp import const
from bpp.models import Uczelnia

MULTISEEK_DEFAULT_REPORT_TITLE = "Rezultat wyszukiwania"
XLSX_WORKSHEET_TITLE_MAX_LENGTH = 31

MULTISEEK_EXPORT_HEADERS = (
    "tytul_oryginalny",
    "autorzy",
    "zrodlo",
    "rok",
    "impact_factor",
    "pk",
    "bpp_id",
    "typ_rekordu",
    "typ_mnisw_mein",
    "id_rekordu",
    "pbn_uid_id",
    "link_do_bpp_url",
    "link_do_bpp_admin_url",
    "link_do_pbn_url",
)

MULTISEEK_EXPORT_XLSX_HEADERS = (
    "Tytuł oryginalny",
    "Autorzy",
    "Źródło",
    "Rok",
    "Impact Factor",
    "PK",
    "BPP ID",
    "Typ rekordu",
    "Typ MNiSW/MEiN",
    "ID rekordu",
    "PBN UID",
    "Link do BPP",
    "Link do edycji w BPP",
    "Link do PBN",
)

MULTISEEK_EXPORT_DANE_FIELDS = (
    "id",
    "tytul_oryginalny",
    "opis_bibliograficzny_zapisani_autorzy_cache",
    "zrodlo__nazwa",
    "rok",
    "impact_factor",
    "punkty_kbn",
    "typ_kbn__nazwa",
    "pbn_uid_id",
)

EXPORT_FILENAME_INVALID_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MULTISEEK_REPORT_TITLE_HTML_BREAK_RE = re.compile(
    r"</?(?:br|hr|p|div|h[1-6])\b[^>]*>",
    re.IGNORECASE,
)
XLSX_WORKSHEET_TITLE_INVALID_CHARS_RE = re.compile(
    r"[\[\]:*?/\\\x00-\x08\x0b\x0c\x0e-\x1f]"
)
SPREADSHEET_FORMULA_INJECTION_LEAD = ("=", "+", "-", "@", "\t", "\r", "\n")


def _export_value(value):
    if value is None:
        return ""
    return str(value)


def _single_line_text(value):
    return re.sub(r"\s+", " ", value).strip()


def plain_multiseek_report_title(value):
    value = _export_value(value)
    value = MULTISEEK_REPORT_TITLE_HTML_BREAK_RE.sub(" ", value)
    value = html.unescape(strip_tags(value))
    return _single_line_text(value) or MULTISEEK_DEFAULT_REPORT_TITLE


def _export_filename(export_format, report_title):
    title = EXPORT_FILENAME_INVALID_CHARS_RE.sub(" ", report_title)
    title = _single_line_text(title).strip(". ")
    if not title:
        title = "multiseek"
    return f"eksport-{title}.{export_format}"


def _xlsx_worksheet_title(report_title):
    title = XLSX_WORKSHEET_TITLE_INVALID_CHARS_RE.sub(" ", report_title)
    title = _single_line_text(title).strip("'")
    if not title:
        title = "Multiseek"
    return title[:XLSX_WORKSHEET_TITLE_MAX_LENGTH]


def _sanitize_spreadsheet_cell(value):
    if isinstance(value, str) and value.startswith(SPREADSHEET_FORMULA_INJECTION_LEAD):
        return "'" + value
    return value


def _sanitize_spreadsheet_row(row):
    return tuple(_sanitize_spreadsheet_cell(value) for value in row)


def _pbn_publication_url(pbn_uid_id, pbn_api_root):
    if not pbn_uid_id or not pbn_api_root:
        return ""
    return const.LINK_PBN_DO_PUBLIKACJI.format(
        pbn_api_root=pbn_api_root,
        pbn_uid_id=pbn_uid_id,
    )


def _admin_change_url(rekord, request):
    content_type = rekord.content_type
    url = reverse(
        f"admin:{content_type.app_label}_{content_type.model}_change",
        args=(rekord.object_id,),
    )
    return request.build_absolute_uri(url)


def _iter_export_rows(queryset, request):
    uczelnia = Uczelnia.objects.get_for_request(request)
    pbn_api_root = uczelnia.pbn_api_root if uczelnia is not None else ""

    for rekord in queryset.iterator(chunk_size=1000):
        zrodlo = rekord.zrodlo
        typ_kbn = rekord.typ_kbn
        yield (
            rekord.tytul_oryginalny,
            rekord.opis_bibliograficzny_zapisani_autorzy_cache,
            zrodlo.nazwa if zrodlo is not None else "",
            rekord.rok,
            rekord.impact_factor,
            rekord.punkty_kbn,
            str(tuple(rekord.pk)),
            str(rekord.describe_content_type),
            typ_kbn.nazwa if typ_kbn is not None else "",
            rekord.object_id,
            _export_value(rekord.pbn_uid_id),
            request.build_absolute_uri(rekord.get_absolute_url()),
            _admin_change_url(rekord, request),
            _pbn_publication_url(rekord.pbn_uid_id, pbn_api_root),
        )


def _xlsx_columns_where(headers, predicate):
    """1-based indeksy kolumn XLSX, których nagłówek spełnia predykat."""
    return [i for i, h in enumerate(headers, start=1) if predicate(h)]


def _apply_xlsx_number_format(worksheet, columns, number_format):
    for col in columns:
        for row in worksheet.iter_rows(min_row=2, min_col=col, max_col=col):
            row[0].number_format = number_format


def _apply_xlsx_hyperlinks(worksheet, url_cols):
    for row_idx in range(2, worksheet.max_row + 1):
        for col_idx in url_cols:
            cell = worksheet.cell(row=row_idx, column=col_idx)
            if cell.value:
                cell.value = f'=HYPERLINK("{cell.value}", "[link]")'


def csv_export_response(queryset, request, report_title):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(MULTISEEK_EXPORT_HEADERS)
    writer.writerows(
        _sanitize_spreadsheet_row(row) for row in _iter_export_rows(queryset, request)
    )

    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = content_disposition_header(
        as_attachment=True,
        filename=_export_filename("csv", report_title),
    )
    return response


def xlsx_export_response(queryset, request, report_title):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    from bpp.util import (
        sanitize_xlsx_row,
        worksheet_columns_autosize,
        worksheet_create_table,
    )

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = _xlsx_worksheet_title(report_title)
    worksheet.append(MULTISEEK_EXPORT_XLSX_HEADERS)
    for row in _iter_export_rows(queryset, request):
        worksheet.append(sanitize_xlsx_row(row))

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in worksheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    headers = MULTISEEK_EXPORT_XLSX_HEADERS
    url_cols = _xlsx_columns_where(headers, lambda h: h.startswith("Link"))
    if_cols = _xlsx_columns_where(headers, lambda h: h == "Impact Factor")
    pk_cols = _xlsx_columns_where(headers, lambda h: h == "PK")

    for row in worksheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    _apply_xlsx_number_format(worksheet, if_cols, "0.000")
    _apply_xlsx_number_format(worksheet, pk_cols, "0.00")
    _apply_xlsx_hyperlinks(worksheet, url_cols)

    worksheet.freeze_panes = "B1"
    worksheet_columns_autosize(worksheet)
    if worksheet.max_row > 1:
        worksheet_create_table(worksheet, title="MultiseekExport")

    output = io.BytesIO()
    workbook.save(output)
    response = HttpResponse(
        output.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
    response["Content-Disposition"] = content_disposition_header(
        as_attachment=True,
        filename=_export_filename("xlsx", report_title),
    )
    return response
