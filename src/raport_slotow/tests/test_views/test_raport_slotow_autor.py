from django.urls import reverse


def test_RaportSlotow_get_pdf(admin_app, autor_jan_kowalski):
    url = reverse("raport_slotow:index")

    form_page = admin_app.get(url)
    form_page.forms[0]["obiekt"].force_value(autor_jan_kowalski.pk)

    raport_page = form_page.forms[0].submit().maybe_follow()

    pdf_page = raport_page.click("pobierz PDF")

    assert pdf_page.status_code == 200
    assert pdf_page.content[:8] == b"%PDF-1.7"
