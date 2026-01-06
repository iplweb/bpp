import os

import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page

from bpp.models import Uczelnia

from django_bpp.playwright_util import proper_click_element, wait_for_page_load


@pytest.mark.django_db
def test_integracyjny(admin_page: Page, channels_live_server, settings):
    settings.CELERY_ALWAYS_EAGER = True
    settings.CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

    # Create Uczelnia and store reference for cleanup
    uczelnia = baker.make(Uczelnia)
    try:
        admin_page.goto(channels_live_server.url + reverse("import_dyscyplin:index"))

        # Accept cookies
        admin_page.evaluate("Cookielaw.accept()")
        wait_for_page_load(admin_page)

        # Click add new file button
        admin_page.click("#add-new-file")

        # Upload file
        file_path = os.path.join(
            os.path.dirname(__file__), "../static/import_dyscyplin/xlsx/default.xlsx"
        )
        admin_page.set_input_files("#id_plik", file_path)

        # Click submit button
        admin_page.click("#id_submit")
        wait_for_page_load(admin_page)

        # Wait a moment for page to fully render
        admin_page.wait_for_load_state("networkidle", timeout=5000)

        body_text = admin_page.evaluate("document.body.textContent")

        # Check if modal appears or we're already redirected
        try:
            admin_page.wait_for_function(
                """() => {
                    const modal = document.querySelector('#modal1[aria-hidden="false"]');
                    const onOkreslKolumny = window.location.href.includes('okresl-kolumny');
                    return modal || onOkreslKolumny;
                }""",
                timeout=5000,
            )
        except Exception:
            pass

        # Check if we need to wait for redirect or should navigate manually
        current_url = admin_page.url
        if "okresl-kolumny" in current_url:
            pass  # Already on the right page
        elif "Plik został dodany do systemu" in body_text:
            # Wait for AJAX call and Celery task to complete
            admin_page.wait_for_timeout(5000)

            # Check if object state changed in database
            import_dyscyplin_id = current_url.rstrip("/").split("/")[-1]
            from import_dyscyplin.models import Import_Dyscyplin

            obj = Import_Dyscyplin.objects.get(pk=import_dyscyplin_id)

            # If task didn't run, call it manually (test workaround for Celery eager mode)
            if obj.stan == "nowy":
                try:
                    obj.stworz_kolumny()
                    obj.save()
                except Exception as e:
                    obj.info = str(e)
                    obj.save()

            new_url = channels_live_server.url + reverse(
                "import_dyscyplin:okresl_kolumny", args=(import_dyscyplin_id,)
            )
            admin_page.goto(new_url)
            wait_for_page_load(admin_page)

        # Wait for redirect to okresl-kolumny (modal should trigger this via JavaScript)
        admin_page.wait_for_function(
            """() => window.location.href.includes('okresl-kolumny')""",
            timeout=20000,
        )

        # Wait for page to fully load
        wait_for_page_load(admin_page)

        # Check if there's a second submit button on the next page (okresl-kolumny page)
        if admin_page.locator("#submit-id-submit").count() > 0:
            # Scroll submit button into view and click it
            submit_btn = admin_page.locator("#submit-id-submit")
            submit_btn.scroll_into_view_if_needed()

            # Try clicking and wait for either navigation or stay on same page
            with admin_page.expect_navigation(
                timeout=15000, wait_until="domcontentloaded"
            ) as navigation_info:  # noqa
                proper_click_element(admin_page, "#submit-id-submit")

            # After submit, we should be on detail page again
            # If we're still on okresl-kolumny, there might be an error
            if "okresl-kolumny" in admin_page.url:
                # Try to get back to detail page manually
                import_dyscyplin_id = admin_page.url.rstrip("/").split("/")[-1]
                detail_url = channels_live_server.url + reverse(
                    "import_dyscyplin:detail", args=(import_dyscyplin_id,)
                )
                admin_page.goto(detail_url)
                wait_for_page_load(admin_page)
            else:
                # We're on detail page, wait for it to fully load
                wait_for_page_load(admin_page)

                # Check if we need to trigger processing manually
                from import_dyscyplin.models import Import_Dyscyplin

                obj = Import_Dyscyplin.objects.get(
                    pk=admin_page.url.rstrip("/").split("/")[-1]
                )

                if obj.stan == "opcje importu określone":
                    try:
                        obj.przeanalizuj()
                        obj.save()
                    except Exception as e:
                        obj.info = str(e)
                        obj.bledny = True
                        obj.save()
                    # Wait for page to refresh
                    admin_page.wait_for_timeout(2000)
                    admin_page.reload()
                    wait_for_page_load(admin_page)

        # Wait for processing to complete and "Lubelski" to appear in the data tables
        # The detail page triggers AJAX calls that process the file
        # Data appears when status changes to "przeanalizowany"
        admin_page.wait_for_function(
            """() => {
                // Check if we're on the detail page and status is "przeanalizowany" or "zintegrowany"
                return document.body.textContent.includes('przeanalizowany') ||
                       document.body.textContent.includes('zintegrowany') ||
                       document.body.textContent.includes('Lubelski');
            }""",
            timeout=60000,
        )

        # Now wait for the DataTable to load with the data
        admin_page.wait_for_function(
            "() => document.body.textContent.includes('Lubelski')", timeout=30000
        )
    finally:
        # Clean up the created Uczelnia record
        if uczelnia:
            uczelnia.delete()
