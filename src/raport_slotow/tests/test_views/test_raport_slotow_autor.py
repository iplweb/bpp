from django.urls import reverse


def test_RaportSlotow_get_pdf(admin_app, autor_jan_kowalski):
    url = reverse("raport_slotow:index")

    form_page = admin_app.get(url)

    # Find the correct form (not the logout form)
    autor_form = None
    for form in form_page.forms.values():
        if "obiekt" in form.fields:
            autor_form = form
            break

    assert autor_form is not None, "Form with 'obiekt' field not found"
    autor_form["obiekt"].force_value(autor_jan_kowalski.pk)

    raport_page = autor_form.submit().maybe_follow()

    pdf_page = raport_page.click("pobierz PDF")

    assert pdf_page.status_code == 200
    assert pdf_page.content[:8] == b"%PDF-1.7"
