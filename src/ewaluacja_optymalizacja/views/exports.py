"""Widoki eksportu danych optymalizacji."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from ..models import OptimizationRun

logger = logging.getLogger(__name__)


def _generate_author_sedn_workbook(author_result, run):
    """Funkcja pomocnicza generująca workbook z pracami autora w formacie SEDN"""
    from openpyxl import Workbook

    from bpp.models.cache import Cache_Punktacja_Autora_Query
    from bpp.util import worksheet_columns_autosize, worksheet_create_table
    from ewaluacja_metryki.models import MetrykaAutora

    autor_pk = author_result.autor_id

    # Pobierz MetrykaAutora
    metryka = MetrykaAutora.objects.filter(
        autor_id=autor_pk, dyscyplina_naukowa=run.dyscyplina_naukowa
    ).first()

    if not metryka or not metryka.prace_wszystkie:
        return None

    # Pobierz wybrane prace (rekord_id) z OptimizationPublication
    selected_rekord_ids = set(
        tuple(pub.rekord_id) for pub in author_result.publications.all()
    )

    # Pobierz wszystkie prace z Cache_Punktacja_Autora_Query
    prace = (
        Cache_Punktacja_Autora_Query.objects.filter(
            rekord_id__in=metryka.prace_wszystkie,
            autor_id=autor_pk,
            dyscyplina_id=run.dyscyplina_naukowa_id,
        )
        .select_related("rekord", "rekord__charakter_formalny")
        .order_by("-pkdaut")
    )

    # Generuj XLSX
    wb = Workbook()
    ws = wb.active
    ws.title = "Prace autora"

    # Nagłówki
    headers = [
        "ID OSIĄGNIĘCIA",
        "TYTUŁ OSIĄGNIĘCIA",
        "RODZAJ",
        "ROK",
        "PUNKTACJA CAŁKOWITA",
        "WARTOŚĆ UDZIAŁÓW",
        "PUNKTACJA DO EWALUACJI",
        "STATUS",
    ]
    ws.append(headers)

    # Mapowanie rodzaj_pbn na wartości tekstowe
    rodzaj_map = {
        1: "artykuł",
        2: "rozdział",
        3: "książka",
        4: "postępowanie",
        None: "brak",
    }

    # Dane
    for praca in prace:
        rekord = praca.rekord
        rekord_id_tuple = tuple(rekord.pk)
        status = "Tak" if rekord_id_tuple in selected_rekord_ids else "Nie"

        # Pobierz PBN UID
        pbn_uid = ""
        try:
            original = rekord.original
            if hasattr(original, "pbn_uid_id") and original.pbn_uid_id:
                pbn_uid = original.pbn_uid_id
        except Exception:
            pass

        # Pobierz RODZAJ z charakter_formalny.rodzaj_pbn
        rodzaj = rodzaj_map.get(rekord.charakter_formalny.rodzaj_pbn, "brak")

        ws.append(
            [
                pbn_uid,
                rekord.tytul_oryginalny,
                rodzaj,
                rekord.rok,
                float(rekord.punkty_kbn) if rekord.punkty_kbn else 0,
                float(praca.slot),
                float(praca.pkdaut),
                status,
            ]
        )

    # Formatowanie
    worksheet_columns_autosize(ws)
    worksheet_create_table(ws, title="PraceAutora")

    return wb


@login_required
def export_author_sedn_xlsx(request, run_pk, autor_pk):
    """Eksport prac autora w formacie SEDN do XLSX"""
    from django.http import HttpResponse

    from ..models import OptimizationAuthorResult

    run = get_object_or_404(OptimizationRun, pk=run_pk)
    author_result = get_object_or_404(
        OptimizationAuthorResult, optimization_run=run, autor_id=autor_pk
    )

    wb = _generate_author_sedn_workbook(author_result, run)

    if wb is None:
        messages.warning(request, "Brak prac do eksportu dla tego autora")
        return redirect(run.get_absolute_url())

    # Response
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = f"prace_{author_result.autor.slug}_{run.dyscyplina_naukowa.kod}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
def export_all_authors_zip(request, run_pk):
    """Eksport prac wszystkich autorów w formacie SEDN jako archiwum ZIP"""
    import io
    import zipfile

    from django.http import HttpResponse

    from ..models import OptimizationAuthorResult

    run = get_object_or_404(OptimizationRun, pk=run_pk)

    # Pobierz wszystkie wyniki autorów dla tego uruchomienia
    author_results = OptimizationAuthorResult.objects.filter(
        optimization_run=run
    ).select_related("autor")

    if not author_results.exists():
        messages.warning(request, "Brak autorów do eksportu")
        return redirect(run.get_absolute_url())

    # Utwórz archiwum ZIP w pamięci
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for author_result in author_results:
            wb = _generate_author_sedn_workbook(author_result, run)

            if wb is None:
                # Pomiń autorów bez prac
                continue

            # Zapisz workbook do bufora w pamięci
            xlsx_buffer = io.BytesIO()
            wb.save(xlsx_buffer)
            xlsx_buffer.seek(0)

            # Dodaj plik do archiwum ZIP
            filename = (
                f"prace_{author_result.autor.slug}_{run.dyscyplina_naukowa.kod}.xlsx"
            )
            zip_file.writestr(filename, xlsx_buffer.read())

    # Przygotuj response
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.read(), content_type="application/zip")
    filename = f"prace_wszystkie_{run.dyscyplina_naukowa.kod}.zip"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response


def generate_all_disciplines_zip_file(status_bulk):
    """Generuje ZIP ze wszystkimi XLS i zapisuje do StatusOptymalizacjiBulk.

    Args:
        status_bulk: Instancja StatusOptymalizacjiBulk do której zapisany zostanie plik.
    """
    import io
    import zipfile

    from django.core.files.base import ContentFile
    from django.utils.text import slugify

    from ..models import OptimizationAuthorResult

    # Pobierz najnowsze ukończone uruchomienia dla każdej dyscypliny
    latest_runs = (
        OptimizationRun.objects.filter(status="completed")
        .order_by("dyscyplina_naukowa", "-started_at")
        .distinct("dyscyplina_naukowa")
    )

    if not latest_runs:
        logger.warning("Brak ukończonych optymalizacji do wygenerowania ZIP")
        return

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for run in latest_runs:
            # Nazwa folderu = slugifikowana nazwa dyscypliny (bez akcentów, _ zamiast spacji)
            folder_name = slugify(run.dyscyplina_naukowa.nazwa).replace("-", "_")

            author_results = OptimizationAuthorResult.objects.filter(
                optimization_run=run
            ).select_related("autor")

            for author_result in author_results:
                wb = _generate_author_sedn_workbook(author_result, run)
                if wb is None:
                    continue

                xlsx_buffer = io.BytesIO()
                wb.save(xlsx_buffer)
                xlsx_buffer.seek(0)

                filename = (
                    f"{folder_name}/prace_{author_result.autor.slug}_{folder_name}.xlsx"
                )
                zip_file.writestr(filename, xlsx_buffer.read())

    # Zapisz do modelu (nadpisuje stary plik)
    zip_buffer.seek(0)

    # Usuń stary plik jeśli istnieje
    if status_bulk.plik_zip_wszystkie_xls:
        status_bulk.plik_zip_wszystkie_xls.delete(save=False)

    status_bulk.plik_zip_wszystkie_xls.save(
        "prace_wszystkie_uczelnia.zip",
        ContentFile(zip_buffer.read()),
        save=True,
    )

    logger.info("Wygenerowano i zapisano plik ZIP ze wszystkimi XLS")


@login_required
def export_all_disciplines_zip(request):
    """Serwuje plik ZIP z cache (StatusOptymalizacjiBulk).

    Jeśli plik nie istnieje, zwraca błąd 404.
    """
    from django.http import Http404
    from django_sendfile import sendfile

    from ..models import StatusOptymalizacjiBulk

    status = StatusOptymalizacjiBulk.get_or_create()

    if not status.plik_zip_wszystkie_xls:
        raise Http404(
            "Plik ZIP nie został jeszcze wygenerowany. Uruchom 'Policz całą ewaluację'."
        )

    return sendfile(
        request,
        status.plik_zip_wszystkie_xls.path,
        attachment=True,
        attachment_filename="prace_wszystkie_uczelnia.zip",
    )
