import os
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from typing import Any

import rollbar
from celery import shared_task
from django.core.files.base import ContentFile
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from bpp.models import Autor_Dyscyplina, Autorzy, Uczelnia

try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None

# Font paths for DejaVuSans (supports Polish characters)
DEJAVU_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def check_fonts_available():
    """Check if DejaVuSans fonts are available, report to Rollbar if not."""
    missing_fonts = []
    if not os.path.exists(DEJAVU_FONT_PATH):
        missing_fonts.append(DEJAVU_FONT_PATH)
    if not os.path.exists(DEJAVU_BOLD_FONT_PATH):
        missing_fonts.append(DEJAVU_BOLD_FONT_PATH)

    if missing_fonts:
        rollbar.report_message(
            "DejaVuSans fonts not found - Polish characters in PDFs will not render correctly",
            level="warning",
            extra_data={"missing_fonts": missing_fonts},
        )
        return False
    return True


def sanitize_filename(name: str, max_length: int = 30) -> str:
    """Sanitize string for use in filename."""
    for char in ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]:
        name = name.replace(char, "_")
    return name[:max_length].strip()


def get_autor_dyscyplina_info(autor, rok) -> dict[str, Any]:
    """Check if author has alternative discipline for given year."""
    try:
        ad = Autor_Dyscyplina.objects.get(autor=autor, rok=rok)
        return {
            "ma_dwie_dyscypliny": ad.dwie_dyscypliny(),
            "dyscyplina_naukowa": ad.dyscyplina_naukowa,
            "subdyscyplina_naukowa": ad.subdyscyplina_naukowa,
        }
    except Autor_Dyscyplina.DoesNotExist:
        return {
            "ma_dwie_dyscypliny": False,
            "dyscyplina_naukowa": None,
            "subdyscyplina_naukowa": None,
        }


def build_declarations_list(queryset, uczelnia):
    """Build list of declaration data from queryset."""
    declarations = []
    autor_dyscypliny_cache = {}

    for entry in queryset:
        cache_key = (entry.autor_id, entry.rekord.rok)
        if cache_key not in autor_dyscypliny_cache:
            autor_dyscypliny_cache[cache_key] = get_autor_dyscyplina_info(
                entry.autor, entry.rekord.rok
            )
        ad_info = autor_dyscypliny_cache[cache_key]

        # Main discipline declaration
        declarations.append(
            {
                "autor": entry.autor,
                "rekord": entry.rekord,
                "dyscyplina_pracy": entry.dyscyplina_naukowa,
                "dyscyplina_naukowa": ad_info["dyscyplina_naukowa"],
                "subdyscyplina_naukowa": ad_info["subdyscyplina_naukowa"],
                "data_oswiadczenia": entry.data_oswiadczenia,
                "przypieta": entry.przypieta,
            }
        )

        # Alternative discipline declaration if author has two disciplines
        if ad_info["ma_dwie_dyscypliny"]:
            alt_dyscyplina = (
                ad_info["subdyscyplina_naukowa"]
                if entry.dyscyplina_naukowa == ad_info["dyscyplina_naukowa"]
                else ad_info["dyscyplina_naukowa"]
            )
            declarations.append(
                {
                    "autor": entry.autor,
                    "rekord": entry.rekord,
                    "dyscyplina_pracy": alt_dyscyplina,
                    "dyscyplina_naukowa": ad_info["dyscyplina_naukowa"],
                    "subdyscyplina_naukowa": ad_info["subdyscyplina_naukowa"],
                    "data_oswiadczenia": entry.data_oswiadczenia,
                    "przypieta": entry.przypieta,
                }
            )

    return declarations


def build_queryset_for_task(task):
    """Build filtered queryset for declarations export task."""
    queryset = (
        Autorzy.objects.exclude(dyscyplina_naukowa=None)
        .filter(
            rekord__rok__gte=task.rok_od,
            rekord__rok__lte=task.rok_do,
        )
        .select_related("autor", "rekord", "dyscyplina_naukowa")
    )

    if task.szukaj_autor:
        queryset = queryset.filter(
            Q(autor__nazwisko__icontains=task.szukaj_autor)
            | Q(autor__imiona__icontains=task.szukaj_autor)
        )

    if task.szukaj_tytul:
        queryset = queryset.filter(
            rekord__tytul_oryginalny__icontains=task.szukaj_tytul
        )

    if task.dyscyplina_id:
        queryset = queryset.filter(dyscyplina_naukowa_id=task.dyscyplina_id)

    if task.przypieta == "tak":
        queryset = queryset.filter(przypieta=True)
    elif task.przypieta == "nie":
        queryset = queryset.filter(przypieta=False)

    queryset = queryset.order_by("rekord__rok", "autor__nazwisko", "autor__imiona")

    # Apply offset and limit for chunked exports
    if task.offset > 0 or task.limit > 0:
        queryset = queryset[task.offset : task.offset + task.limit]

    return queryset


def render_declaration_html(decl, uczelnia):
    """Render a single declaration to full HTML document."""
    html_content = render_to_string(
        "oswiadczenia/tresc_jednego_oswiadczenia.html",
        {
            "autor": decl["autor"],
            "object": decl["rekord"],
            "dyscyplina_pracy": decl["dyscyplina_pracy"],
            "dyscyplina_naukowa": decl["dyscyplina_naukowa"],
            "subdyscyplina_naukowa": decl["subdyscyplina_naukowa"],
            "uczelnia": uczelnia,
            "data_oswiadczenia": decl["data_oswiadczenia"],
            "przypieta": decl["przypieta"],
        },
    )

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Oswiadczenie</title>
    <style>
        @font-face {{
            font-family: "DejaVuSans";
            src: url("{DEJAVU_FONT_PATH}");
        }}
        @font-face {{
            font-family: "DejaVuSans";
            src: url("{DEJAVU_BOLD_FONT_PATH}");
            font-weight: bold;
        }}
        body {{
            font-family: "DejaVuSans", sans-serif;
            font-size: 10pt;
            line-height: 1.4;
            margin: 2.5cm;
        }}
        h1 {{ font-size: 14pt; text-align: center; margin: 0.5em 0; }}
        h2 {{ font-size: 12pt; margin: 0.5em 0; }}
        h3 {{ font-size: 10pt; margin: 0.5em 0; }}
        p {{ margin: 0.3em 0; }}
        ul {{ margin: 0.3em 0; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""


def generate_declaration_content(decl, uczelnia, export_format):
    """Generate content for a single declaration.

    Returns:
        tuple: (filename, content_bytes)
    """
    autor_name = sanitize_filename(
        f"{decl['autor'].nazwisko}_{decl['autor'].imiona}", 50
    )
    rekord_id = decl["rekord"].pk[1]  # second element of tuple pk
    tytul = sanitize_filename(decl["rekord"].tytul_oryginalny, 30)
    dyscyplina_name = sanitize_filename(str(decl["dyscyplina_pracy"]), 20)

    full_html = render_declaration_html(decl, uczelnia)

    if export_format == "pdf":
        result = BytesIO()
        pisa_status = pisa.CreatePDF(full_html, dest=result, encoding="utf-8")
        if pisa_status.err:
            raise Exception(f"PDF generation failed for {decl['autor']}")
        pdf_content = result.getvalue()
        filename = f"{autor_name}/{rekord_id}_{tytul}_{dyscyplina_name}.pdf"
        return filename, pdf_content
    elif export_format == "docx":
        from nowe_raporty.docx_export import html_to_docx

        docx_content = html_to_docx(full_html)
        filename = f"{autor_name}/{rekord_id}_{tytul}_{dyscyplina_name}.docx"
        return filename, docx_content
    else:
        filename = f"{autor_name}/{rekord_id}_{tytul}_{dyscyplina_name}.html"
        return filename, full_html.encode("utf-8")


def write_declaration_to_zip(zf, decl, uczelnia, export_format):
    """Write a single declaration to the ZIP file."""
    filename, content = generate_declaration_content(decl, uczelnia, export_format)
    zf.writestr(filename, content)


def generate_pdfs_parallel(declarations, uczelnia, task):
    """Generate PDFs in parallel using ThreadPoolExecutor.

    Returns:
        list of (filename, content) tuples
    """
    max_workers = min(4, os.cpu_count() or 2)
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(
                generate_declaration_content,
                decl,
                uczelnia,
                "pdf",
            ): (idx, decl)
            for idx, decl in enumerate(declarations, 1)
        }

        for future in as_completed(future_to_idx):
            idx, decl = future_to_idx[future]
            filename, content = future.result()
            results.append((filename, content))

            task.processed_items = len(results)
            task.current_item = (
                f"{decl['autor']} - {decl['rekord'].tytul_oryginalny[:30]}"
            )
            if len(results) % 10 == 0 or len(results) == len(declarations):
                task.save()

    return results


def generate_html_sequential(zf, declarations, uczelnia, task):
    """Generate HTML files sequentially and write to ZIP."""
    for idx, decl in enumerate(declarations, 1):
        write_declaration_to_zip(zf, decl, uczelnia, "html")

        task.processed_items = idx
        task.current_item = f"{decl['autor']} - {decl['rekord'].tytul_oryginalny[:30]}"
        if idx % 10 == 0 or idx == len(declarations):
            task.save()


def generate_docx_sequential(zf, declarations, uczelnia, task):
    """Generate DOCX files sequentially and write to ZIP."""
    for idx, decl in enumerate(declarations, 1):
        write_declaration_to_zip(zf, decl, uczelnia, "docx")

        task.processed_items = idx
        task.current_item = f"{decl['autor']} - {decl['rekord'].tytul_oryginalny[:30]}"
        if idx % 10 == 0 or idx == len(declarations):
            task.save()


def render_declaration_content_only(decl, uczelnia):
    """Render a single declaration content (without full HTML wrapper)."""
    return render_to_string(
        "oswiadczenia/tresc_jednego_oswiadczenia.html",
        {
            "autor": decl["autor"],
            "object": decl["rekord"],
            "dyscyplina_pracy": decl["dyscyplina_pracy"],
            "dyscyplina_naukowa": decl["dyscyplina_naukowa"],
            "subdyscyplina_naukowa": decl["subdyscyplina_naukowa"],
            "uczelnia": uczelnia,
            "data_oswiadczenia": decl["data_oswiadczenia"],
            "przypieta": decl["przypieta"],
        },
    )


def generate_combined_html(declarations, uczelnia, task):
    """Generate a single HTML file with all declarations separated by page breaks.

    Returns:
        bytes: Combined HTML content as UTF-8 encoded bytes
    """
    html_parts = []

    for idx, decl in enumerate(declarations, 1):
        content = render_declaration_content_only(decl, uczelnia)
        html_parts.append(content)

        task.processed_items = idx
        task.current_item = f"{decl['autor']} - {decl['rekord'].tytul_oryginalny[:30]}"
        if idx % 10 == 0 or idx == len(declarations):
            task.save()

    # Join with page break dividers
    combined_content = '<div style="page-break-after: always;"></div>\n'.join(
        html_parts
    )

    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Oswiadczenia</title>
    <style>
        @font-face {{
            font-family: "DejaVuSans";
            src: url("{DEJAVU_FONT_PATH}");
        }}
        @font-face {{
            font-family: "DejaVuSans";
            src: url("{DEJAVU_BOLD_FONT_PATH}");
            font-weight: bold;
        }}
        body {{
            font-family: "DejaVuSans", sans-serif;
            font-size: 12pt;
            line-height: 1.4;
            margin: 2cm;
        }}
        h1 {{ font-size: 16pt; text-align: center; }}
        h2 {{ font-size: 14pt; }}
        h3 {{ font-size: 12pt; }}
        @media print {{
            .page-break {{
                page-break-after: always;
            }}
        }}
    </style>
</head>
<body>
{combined_content}
</body>
</html>"""

    return full_html.encode("utf-8")


def generate_combined_docx(declarations, uczelnia, task):
    """Generate a single DOCX file with all declarations.

    Returns:
        bytes: DOCX file content
    """
    from nowe_raporty.docx_export import html_to_docx

    html_parts = []

    for idx, decl in enumerate(declarations, 1):
        content = render_declaration_content_only(decl, uczelnia)
        html_parts.append(content)

        task.processed_items = idx
        task.current_item = f"{decl['autor']} - {decl['rekord'].tytul_oryginalny[:30]}"
        if idx % 10 == 0 or idx == len(declarations):
            task.save()

    # Join with page break markers - will be replaced with real page breaks by html_to_docx
    from nowe_raporty.docx_export import PAGEBREAK_MARKER

    combined_content = f"<p>{PAGEBREAK_MARKER}</p>\n".join(html_parts)

    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Oswiadczenia</title>
</head>
<body>
{combined_content}
</body>
</html>"""

    return html_to_docx(full_html)


def generate_combined_pdf(declarations, uczelnia, task):
    """Generate a single PDF file with all declarations.

    Returns:
        bytes: PDF file content
    """
    html_parts = []

    for idx, decl in enumerate(declarations, 1):
        content = render_declaration_content_only(decl, uczelnia)
        html_parts.append(content)

        task.processed_items = idx
        task.current_item = f"{decl['autor']} - {decl['rekord'].tytul_oryginalny[:30]}"
        if idx % 10 == 0 or idx == len(declarations):
            task.save()

    # Join with page break dividers
    combined_content = '<div style="page-break-after: always;"></div>\n'.join(
        html_parts
    )

    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Oswiadczenia</title>
    <style>
        @font-face {{
            font-family: "DejaVuSans";
            src: url("{DEJAVU_FONT_PATH}");
        }}
        @font-face {{
            font-family: "DejaVuSans";
            src: url("{DEJAVU_BOLD_FONT_PATH}");
            font-weight: bold;
        }}
        body {{
            font-family: "DejaVuSans", sans-serif;
            font-size: 10pt;
            line-height: 1.4;
            margin: 2.5cm;
        }}
        h1 {{ font-size: 14pt; text-align: center; margin: 0.5em 0; }}
        h2 {{ font-size: 12pt; margin: 0.5em 0; }}
        h3 {{ font-size: 10pt; margin: 0.5em 0; }}
        p {{ margin: 0.3em 0; }}
        ul {{ margin: 0.3em 0; }}
    </style>
</head>
<body>
{combined_content}
</body>
</html>"""

    result = BytesIO()
    pisa_status = pisa.CreatePDF(full_html, dest=result, encoding="utf-8")
    if pisa_status.err:
        raise Exception("PDF generation failed")
    return result.getvalue()


def _generate_single_file_output(task, declarations, uczelnia):
    """Generate a single file output (html_single, pdf_single, or docx_single).

    Returns:
        tuple: (filename, content) or None if format is not a single-file format.
    """
    format_handlers = {
        "html_single": (
            generate_combined_html,
            f"oswiadczenia_{task.rok_od}_{task.rok_do}.html",
        ),
        "pdf_single": (
            generate_combined_pdf,
            f"oswiadczenia_{task.rok_od}_{task.rok_do}.pdf",
        ),
        "docx_single": (
            generate_combined_docx,
            f"oswiadczenia_{task.rok_od}_{task.rok_do}.docx",
        ),
    }

    if task.export_format not in format_handlers:
        return None

    generator, filename = format_handlers[task.export_format]
    content = generator(declarations, uczelnia, task)
    return filename, content


def _generate_zip_output(task, declarations, uczelnia):
    """Generate a ZIP file with multiple declaration files.

    Returns:
        tuple: (filename, content) for the ZIP file.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
        with zipfile.ZipFile(tmp_file, "w", zipfile.ZIP_DEFLATED) as zf:
            if task.export_format == "pdf":
                results = generate_pdfs_parallel(declarations, uczelnia, task)
                for fname, file_content in results:
                    zf.writestr(fname, file_content)
            elif task.export_format == "docx":
                generate_docx_sequential(zf, declarations, uczelnia, task)
            else:
                generate_html_sequential(zf, declarations, uczelnia, task)

        tmp_path = tmp_file.name

    with open(tmp_path, "rb") as f:
        content = f.read()

    os.unlink(tmp_path)

    filename = f"oswiadczenia_{task.rok_od}_{task.rok_do}_{task.export_format}.zip"
    return filename, content


@shared_task(bind=True)
def generate_oswiadczenia_zip(self, task_id: int):
    """Generate ZIP or single file with declarations.

    Args:
        task_id: ID of OswiadczeniaExportTask record.

    Returns:
        dict with status and task_id.
    """
    from oswiadczenia.models import OswiadczeniaExportTask

    task = OswiadczeniaExportTask.objects.get(pk=task_id)
    task.status = "running"
    task.started_at = timezone.now()
    task.celery_task_id = self.request.id
    task.save()

    try:
        queryset = build_queryset_for_task(task)
        uczelnia = Uczelnia.objects.get_default()
        declarations = build_declarations_list(queryset, uczelnia)

        task.total_items = len(declarations)
        task.save()

        if task.total_items == 0:
            task.status = "completed"
            task.completed_at = timezone.now()
            task.error_message = (
                "Brak oswiadczen do wygenerowania dla podanych filtrow."
            )
            task.save()
            return {"status": "empty", "task_id": task_id}

        # Check PDF generation dependencies
        if task.export_format in ("pdf", "pdf_single"):
            if pisa is None:
                task.status = "failed"
                task.error_message = "xhtml2pdf nie jest zainstalowany."
                task.completed_at = timezone.now()
                task.save()
                return {"status": "error", "task_id": task_id}

            # Check if fonts are available for proper Polish character rendering
            check_fonts_available()

        # Handle single-file formats or ZIP
        single_file_result = _generate_single_file_output(task, declarations, uczelnia)
        if single_file_result:
            filename, content = single_file_result
            task.result_file.save(filename, ContentFile(content))
        else:
            # Generate ZIP
            filename, content = _generate_zip_output(task, declarations, uczelnia)
            task.result_file.save(filename, ContentFile(content))

        task.status = "completed"
        task.completed_at = timezone.now()
        task.save()

        return {"status": "success", "task_id": task_id}

    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        task.completed_at = timezone.now()
        task.save()
        raise


@shared_task
def remove_old_oswiadczenia_export_files():
    """Remove OswiadczeniaExportTask records and their files older than 7 days."""
    from bpp.util import remove_old_objects
    from oswiadczenia.models import OswiadczeniaExportTask

    return remove_old_objects(
        OswiadczeniaExportTask,
        file_field="result_file",
        field_name="created_at",
        days=7,
    )
