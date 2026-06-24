"""Testy asynchronicznego (Celery) eksportu publikacji autora (§3.3).

Eksport BibTeX/RIS jest budowany w tle przez zadanie Celery
``generuj_eksport_autora`` i pobierany dopiero gdy gotowy. Strony są
PUBLICZNE (anonimowe, bez logowania), a autoryzacja statusu/pobrania
odbywa się wyłącznie przez nieodgadywalny UUID ``AutorEksportTask.pk``.
"""

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from bpp.export.bibtex import export_to_bibtex
from bpp.models import Autor, AutorEksportTask, Rekord

pytestmark = pytest.mark.django_db


def _zbuduj_autora_z_pracami(
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    denorms,
):
    """Podpina jeden artykuł i jedno zwarte pod autora i odświeża cache."""
    wydawnictwo_ciagle.tytul_oryginalny = "Artykuł testowy o eksporcie"
    wydawnictwo_ciagle.doi = "10.1234/test.doi"
    wydawnictwo_ciagle.tom = "12"
    wydawnictwo_ciagle.nr_zeszytu = "3"
    wydawnictwo_ciagle.strony = "100-110"
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)

    wydawnictwo_zwarte.tytul_oryginalny = "Książka testowa o eksporcie"
    wydawnictwo_zwarte.save()
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)

    denorms.flush()


def test_generuj_eksport_autora_bibtex(
    transactional_db,
    standard_data,
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    denorms,
):
    from bpp.tasks import generuj_eksport_autora

    _zbuduj_autora_z_pracami(
        wydawnictwo_ciagle, wydawnictwo_zwarte, autor_jan_nowak, jednostka, denorms
    )

    task = AutorEksportTask.objects.create(autor=autor_jan_nowak, format="bib")
    generuj_eksport_autora(str(task.pk))

    task.refresh_from_db()
    assert task.status == "completed"
    assert task.result_file
    assert task.completed_at is not None

    body = task.result_file.read().decode("utf-8")
    assert "@article" in body
    assert "Nowak" in body

    # Parytet z wyjściem synchronicznym (ten sam slice/formater).
    qs = Rekord.objects.prace_autora(autor_jan_nowak)
    oryginaly = [r.original for r in qs[:5000]]
    assert body == export_to_bibtex(oryginaly)


def test_generuj_eksport_autora_ris(
    transactional_db,
    standard_data,
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    denorms,
):
    from bpp.tasks import generuj_eksport_autora

    _zbuduj_autora_z_pracami(
        wydawnictwo_ciagle, wydawnictwo_zwarte, autor_jan_nowak, jednostka, denorms
    )

    task = AutorEksportTask.objects.create(autor=autor_jan_nowak, format="ris")
    generuj_eksport_autora(str(task.pk))

    task.refresh_from_db()
    assert task.status == "completed"
    assert task.result_file

    body = task.result_file.read().decode("utf-8")
    assert "TY  - JOUR" in body
    assert "ER  -" in body


def test_start_view_tworzy_task_i_przekierowuje(
    client,
    transactional_db,
    standard_data,
    autor_jan_nowak,
    mocker,
):
    delay = mocker.patch("bpp.tasks.generuj_eksport_autora.delay")

    url = reverse("bpp:autor_eksport_start", args=(autor_jan_nowak.pk, "bib"))
    resp = client.get(url)

    assert resp.status_code == 302
    task = AutorEksportTask.objects.get()
    assert task.autor == autor_jan_nowak
    assert task.format == "bib"
    assert reverse("bpp:autor_eksport_status", args=(task.pk,)) in resp["Location"]
    delay.assert_called_once_with(str(task.pk))


def test_start_view_dedupes(
    client,
    transactional_db,
    standard_data,
    autor_jan_nowak,
    mocker,
):
    delay = mocker.patch("bpp.tasks.generuj_eksport_autora.delay")

    url = reverse("bpp:autor_eksport_start", args=(autor_jan_nowak.pk, "bib"))
    resp1 = client.get(url)
    resp2 = client.get(url)

    assert AutorEksportTask.objects.count() == 1
    assert resp1["Location"] == resp2["Location"]
    delay.assert_called_once()


def test_status_view_pending_pokazuje_postep(
    client,
    transactional_db,
    standard_data,
    autor_jan_nowak,
):
    task = AutorEksportTask.objects.create(
        autor=autor_jan_nowak, format="bib", status="pending"
    )
    url = reverse("bpp:autor_eksport_status", args=(task.pk,))
    resp = client.get(url)

    assert resp.status_code == 200
    assert b"progress-container" in resp.content


def test_status_view_completed_pokazuje_link_pobierania(
    client,
    transactional_db,
    standard_data,
    autor_jan_nowak,
):
    task = AutorEksportTask.objects.create(
        autor=autor_jan_nowak, format="bib", status="completed"
    )
    task.result_file.save("test.bib", ContentFile(b"@article{x}"))
    url = reverse("bpp:autor_eksport_status", args=(task.pk,))
    resp = client.get(url)

    assert resp.status_code == 200
    download_url = reverse("bpp:autor_eksport_pobierz", args=(task.pk,))
    assert download_url.encode() in resp.content


def test_status_view_hx_request_zwraca_partial(
    client,
    transactional_db,
    standard_data,
    autor_jan_nowak,
):
    task = AutorEksportTask.objects.create(
        autor=autor_jan_nowak, format="bib", status="pending"
    )
    url = reverse("bpp:autor_eksport_status", args=(task.pk,))
    resp = client.get(url, HTTP_HX_REQUEST="true")

    assert resp.status_code == 200
    # Partial nie zawiera szkieletu strony (brak kontenera pollingowego).
    assert b"progress-container" not in resp.content


def test_download_view_completed(
    client,
    transactional_db,
    standard_data,
    autor_jan_nowak,
):
    task = AutorEksportTask.objects.create(
        autor=autor_jan_nowak, format="bib", status="completed"
    )
    task.result_file.save("test.bib", ContentFile(b"@article{x}"))
    url = reverse("bpp:autor_eksport_pobierz", args=(task.pk,))
    resp = client.get(url)

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/x-bibtex")
    disp = resp["Content-Disposition"]
    assert "attachment" in disp
    assert f"{autor_jan_nowak.slug}.bib" in disp


def test_download_view_niezakonczony_404(
    client,
    transactional_db,
    standard_data,
    autor_jan_nowak,
):
    task = AutorEksportTask.objects.create(
        autor=autor_jan_nowak, format="bib", status="pending"
    )
    url = reverse("bpp:autor_eksport_pobierz", args=(task.pk,))
    resp = client.get(url)
    assert resp.status_code == 404


def test_download_view_nieznany_pk_404(
    client,
    transactional_db,
    standard_data,
):
    import uuid

    url = reverse("bpp:autor_eksport_pobierz", args=(uuid.uuid4(),))
    resp = client.get(url)
    assert resp.status_code == 404


def test_widoki_dzialaja_dla_anonima(
    client,
    transactional_db,
    standard_data,
    autor_jan_nowak,
    mocker,
):
    """Wszystkie trzy widoki działają bez logowania (brak redirectu na login)."""
    mocker.patch("bpp.tasks.generuj_eksport_autora.delay")

    start = client.get(
        reverse("bpp:autor_eksport_start", args=(autor_jan_nowak.pk, "bib"))
    )
    assert start.status_code == 302
    assert "/login" not in start["Location"]

    task = AutorEksportTask.objects.get()
    status = client.get(reverse("bpp:autor_eksport_status", args=(task.pk,)))
    assert status.status_code == 200

    task.status = "completed"
    task.result_file.save("test.bib", ContentFile(b"@article{x}"))
    task.save()
    download = client.get(reverse("bpp:autor_eksport_pobierz", args=(task.pk,)))
    assert download.status_code == 200
