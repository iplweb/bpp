import functools
import os
import ssl
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from celery import shared_task
from django.core.files.base import ContentFile
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from bpp.models import Autor_Dyscyplina, Autorzy, Uczelnia

try:
    from django_weasyprint.utils import django_url_fetcher
    from weasyprint import HTML
except ImportError:
    django_url_fetcher = None
    HTML = None


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

    queryset = queryset.order_by("rekord__rok", "autor__nazwisko", "autor__imiona")

    # Apply offset and limit for chunked exports
    if task.offset > 0 or task.limit > 0:
        queryset = queryset[task.offset : task.offset + task.limit]

    return queryset


def setup_pdf_url_fetcher():
    """Setup URL fetcher for PDF generation with SSL context."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return functools.partial(django_url_fetcher, ssl_context=ssl_context)


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
        body {{
            font-family: Arial, sans-serif;
            font-size: 12pt;
            line-height: 1.4;
            margin: 2cm;
        }}
        h1 {{ font-size: 16pt; text-align: center; }}
        h2 {{ font-size: 14pt; }}
        h3 {{ font-size: 12pt; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""


def generate_declaration_content(decl, uczelnia, export_format, url_fetcher):
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
        pdf_content = HTML(string=full_html, url_fetcher=url_fetcher).write_pdf()
        filename = f"{autor_name}/{rekord_id}_{tytul}_{dyscyplina_name}.pdf"
        return filename, pdf_content
    else:
        filename = f"{autor_name}/{rekord_id}_{tytul}_{dyscyplina_name}.html"
        return filename, full_html.encode("utf-8")


def write_declaration_to_zip(zf, decl, uczelnia, export_format, url_fetcher):
    """Write a single declaration to the ZIP file."""
    filename, content = generate_declaration_content(
        decl, uczelnia, export_format, url_fetcher
    )
    zf.writestr(filename, content)


def generate_pdfs_parallel(declarations, uczelnia, url_fetcher, task):
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
                url_fetcher,
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
        write_declaration_to_zip(zf, decl, uczelnia, "html", None)

        task.processed_items = idx
        task.current_item = f"{decl['autor']} - {decl['rekord'].tytul_oryginalny[:30]}"
        if idx % 10 == 0 or idx == len(declarations):
            task.save()


@shared_task(bind=True)
def generate_oswiadczenia_zip(self, task_id: int):
    """Generate ZIP file with declarations.

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

        # Setup PDF generation if needed
        url_fetcher = None
        if task.export_format == "pdf":
            if django_url_fetcher is None or HTML is None:
                task.status = "failed"
                task.error_message = "WeasyPrint nie jest zainstalowany."
                task.completed_at = timezone.now()
                task.save()
                return {"status": "error", "task_id": task_id}
            url_fetcher = setup_pdf_url_fetcher()

        # Generate ZIP with parallel processing for PDF format
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
            with zipfile.ZipFile(tmp_file, "w", zipfile.ZIP_DEFLATED) as zf:
                if task.export_format == "pdf":
                    results = generate_pdfs_parallel(
                        declarations, uczelnia, url_fetcher, task
                    )
                    for filename, content in results:
                        zf.writestr(filename, content)
                else:
                    generate_html_sequential(zf, declarations, uczelnia, task)

            tmp_path = tmp_file.name

        # Save result file
        with open(tmp_path, "rb") as f:
            filename = (
                f"oswiadczenia_{task.rok_od}_{task.rok_do}_{task.export_format}.zip"
            )
            task.result_file.save(filename, ContentFile(f.read()))

        os.unlink(tmp_path)

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
