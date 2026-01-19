import random

import pytest
from django.db import connection, transaction
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page

from bpp.models import Autor, Jednostka, Zrodlo
from bpp.models.system import (
    Charakter_Formalny,
    Jezyk,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
)
from django_bpp.playwright_util import (
    close_all_select2_dropdowns,
    select_select2_autocomplete,
)


def force_commit():
    """Force a commit to make data visible to other threads/processes."""
    # Close current connection to force commit
    connection.close()


def create_and_commit_fixtures():
    """Create required system lookup tables and commit to make visible to live server.

    Uses get_or_create and explicit commit to ensure data is visible to
    channels_live_server which runs in a separate thread.

    Note: Models inheriting from NazwaISkrot have unique constraint on 'skrot',
    so we use 'skrot' as the lookup field to avoid IntegrityError.
    """
    # Ensure autocommit is on for this operation
    old_autocommit = transaction.get_autocommit()
    transaction.set_autocommit(True)

    try:
        # Create status_korekty with the expected name (nazwa is the lookup field)
        status, _ = Status_Korekty.objects.get_or_create(nazwa="przed korektą")
        # Create charakter_formalny (skrot is unique, use it as lookup)
        charakter, _ = Charakter_Formalny.objects.get_or_create(
            skrot="BR", defaults={"nazwa": "Broszura", "rodzaj_pbn": None}
        )
        # Create jezyk (skrot is unique, use it as lookup)
        jezyk, _ = Jezyk.objects.get_or_create(
            skrot="pol.", defaults={"nazwa": "polski"}
        )
        # Create typ_kbn (skrot is unique, use it as lookup)
        typ_kbn, _ = Typ_KBN.objects.get_or_create(skrot="PO", defaults={"nazwa": "PO"})
        # Create typ_odpowiedzialnosci (skrot is unique, use it as lookup)
        typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
            skrot="aut.", defaults={"nazwa": "autor"}
        )
    finally:
        transaction.set_autocommit(old_autocommit)

    return status, charakter, jezyk, typ_kbn, typ_odp


def create_test_data_and_commit(base_name):
    """Create test data and commit to database for live server visibility.

    Uses unique suffix to avoid conflicts between test runs.
    """
    import uuid

    suffix = str(uuid.uuid4())[:8]

    # Ensure autocommit is on for this operation
    old_autocommit = transaction.get_autocommit()
    transaction.set_autocommit(True)

    try:
        autor = baker.make(Autor, nazwisko=f"Aut{suffix}", imiona="Jan")
        jednostka = baker.make(Jednostka, nazwa=f"Jedn{suffix}")
        zrodlo_obj = baker.make(Zrodlo, nazwa=f"Zr{suffix}")
    finally:
        transaction.set_autocommit(old_autocommit)

    return autor, jednostka, zrodlo_obj


def create_two_authors_and_commit(base_name):
    """Create two authors and related data, then commit for live server visibility.

    Uses unique suffix to avoid conflicts between test runs.
    """
    import uuid

    suffix = str(uuid.uuid4())[:8]

    # Ensure autocommit is on for this operation
    old_autocommit = transaction.get_autocommit()
    transaction.set_autocommit(True)

    try:
        autor1 = baker.make(Autor, nazwisko=f"Aut1{suffix}", imiona="Jan")
        autor2 = baker.make(Autor, nazwisko=f"Aut2{suffix}", imiona="Anna")
        jednostka = baker.make(Jednostka, nazwa=f"Jedn{suffix}")
        zrodlo_obj = baker.make(Zrodlo, nazwa=f"Zr{suffix}")
    finally:
        transaction.set_autocommit(old_autocommit)

    return autor1, autor2, jednostka, zrodlo_obj


def select_first_option(admin_page, selector):
    """Select first non-empty option from a select element."""
    options = admin_page.locator(f"{selector} option").all()
    for opt in options:
        val = opt.get_attribute("value")
        if val:
            admin_page.select_option(selector, value=val)
            return True
    return False


def select_charakter_formalny(admin_page):
    """Select charakter formalny, preferring 'Broszura' if available."""
    if not admin_page.query_selector("#id_charakter_formalny"):
        return
    available_options = admin_page.locator("#id_charakter_formalny option").all()
    if len(available_options) <= 1:
        return
    for option in available_options:
        text_content = option.text_content()
        if "Broszura" in text_content:
            admin_page.select_option(
                "#id_charakter_formalny", value=option.get_attribute("value")
            )
            return
    # Fallback to first non-empty option
    for option in available_options:
        val = option.get_attribute("value")
        if val:
            admin_page.select_option("#id_charakter_formalny", value=val)
            return


@pytest.mark.serial
@pytest.mark.django_db
@pytest.mark.parametrize(
    "klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"]
)
def test_procent_odpowiedzialnosci_baseModel_AutorFormset_jeden_autor(  # noqa: C901
    channels_live_server,
    admin_page: Page,
    transactional_db,
    klass,
):
    """Test single author with 100% responsibility validates correctly.

    Uses explicit COMMIT to make data visible to live server.
    """
    # Create system fixtures and commit
    create_and_commit_fixtures()

    # Create test data and commit (unique names per run)
    autor, jednostka, zrodlo_obj = create_test_data_and_commit("test1")

    url = channels_live_server.url + reverse(f"admin:bpp_{klass}_add")

    # Navigate to page
    admin_page.goto(url)
    admin_page.wait_for_load_state("domcontentloaded")

    # Fill admin form
    admin_page.fill("#id_tytul_oryginalny", "tytul oryginalny")

    if admin_page.query_selector("#id_zrodlo"):
        select_select2_autocomplete(
            admin_page, "id_zrodlo", zrodlo_obj.nazwa, timeout=4000
        )

    if admin_page.query_selector("#id_jezyk"):
        select_first_option(admin_page, "#id_jezyk")

    select_charakter_formalny(admin_page)

    if admin_page.query_selector("#id_typ_kbn"):
        select_first_option(admin_page, "#id_typ_kbn")

    admin_page.select_option("#id_status_korekty", label="przed korektą")
    admin_page.fill("#id_rok", str(random.randint(1, 2100)))

    # Add autor inline
    admin_page.wait_for_selector(".grp-add-handler", state="visible", timeout=10000)
    add_buttons = admin_page.locator(".grp-add-handler").all()
    for button in add_buttons:
        if button.is_visible() and "powiązanie autora" in button.text_content():
            button.click()
            break

    admin_page.wait_for_selector(
        "#id_autorzy_set-0-autor", state="visible", timeout=10000
    )

    # Fill admin inline
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-autor", autor.nazwisko, timeout=4000
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-jednostka", jednostka.nazwa, timeout=4000
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-zapisany_jako", "Kopara", timeout=4000
    )
    # Select typ_odpowiedzialnosci (responsibility type)
    if admin_page.query_selector("#id_autorzy_set-0-typ_odpowiedzialnosci"):
        admin_page.select_option(
            "#id_autorzy_set-0-typ_odpowiedzialnosci", label="autor"
        )
    admin_page.fill("#id_autorzy_set-0-procent", "100.00")

    # Submit form
    admin_page.evaluate('django.jQuery("input[type=submit].grp-default").click()')
    admin_page.wait_for_load_state("domcontentloaded", timeout=10000)

    # Check success
    admin_page.wait_for_function(
        "() => document.body && document.body.textContent.includes("
        "'został(a)(-ło) dodany(-na)(-ne) pomyślnie')",
        timeout=10000,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"]
)
def test_procent_odpowiedzialnosci_baseModel_AutorFormset_problem_jeden_autor(  # noqa: C901
    channels_live_server,
    admin_page: Page,
    transactional_db,
    klass,
):
    """Test single author with invalid percentage (100.01%) fails validation."""
    # Create system fixtures and commit
    create_and_commit_fixtures()

    # Create test data and commit (unique names per run)
    autor, jednostka, zrodlo_obj = create_test_data_and_commit("test2")

    url = channels_live_server.url + reverse(f"admin:bpp_{klass}_add")

    # Navigate to page
    admin_page.goto(url)
    admin_page.wait_for_load_state("domcontentloaded")

    # Fill admin form
    admin_page.fill("#id_tytul_oryginalny", "tytul oryginalny")

    if admin_page.query_selector("#id_zrodlo"):
        select_select2_autocomplete(
            admin_page, "id_zrodlo", zrodlo_obj.nazwa, timeout=4000
        )

    if admin_page.query_selector("#id_jezyk"):
        select_first_option(admin_page, "#id_jezyk")

    select_charakter_formalny(admin_page)

    if admin_page.query_selector("#id_typ_kbn"):
        select_first_option(admin_page, "#id_typ_kbn")

    admin_page.select_option("#id_status_korekty", label="przed korektą")
    admin_page.fill("#id_rok", str(random.randint(1, 2100)))

    # Add autor inline
    admin_page.wait_for_selector(".grp-add-handler", state="visible", timeout=10000)
    add_buttons = admin_page.locator(".grp-add-handler").all()
    for button in add_buttons:
        if button.is_visible() and "powiązanie autora" in button.text_content():
            button.click()
            break

    admin_page.wait_for_selector(
        "#id_autorzy_set-0-autor", state="visible", timeout=10000
    )

    # Fill admin inline with INVALID percentage (100.01 instead of 100.00)
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-autor", autor.nazwisko, timeout=4000
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-jednostka", jednostka.nazwa, timeout=4000
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-zapisany_jako", "Kopara", timeout=4000
    )
    # Select typ_odpowiedzialnosci (responsibility type)
    if admin_page.query_selector("#id_autorzy_set-0-typ_odpowiedzialnosci"):
        admin_page.select_option(
            "#id_autorzy_set-0-typ_odpowiedzialnosci", label="autor"
        )
    admin_page.fill("#id_autorzy_set-0-procent", "100.01")

    # Submit form
    admin_page.evaluate('django.jQuery("input[type=submit].grp-default").click()')
    admin_page.wait_for_load_state("domcontentloaded", timeout=10000)

    # Check failure
    admin_page.wait_for_function(
        "() => document.body && document.body.textContent.includes('Prosimy poprawić')",
        timeout=10000,
    )


@pytest.mark.serial
@pytest.mark.django_db
@pytest.mark.parametrize(
    "klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"]
)
def test_procent_odpowiedzialnosci_baseModel_AutorFormset_dwoch_autorow(  # noqa: C901
    channels_live_server,
    admin_page: Page,
    transactional_db,
    klass,
):
    """Test two authors with 50%+50% responsibility validates correctly."""
    # Create system fixtures and commit
    create_and_commit_fixtures()

    # Create test data and commit (unique names per run)
    autor1, autor2, jednostka, zrodlo_obj = create_two_authors_and_commit("test3")

    url = channels_live_server.url + reverse(f"admin:bpp_{klass}_add")

    # Navigate to page
    admin_page.goto(url)
    admin_page.wait_for_load_state("domcontentloaded")

    # Clean up any lingering Select2 dropdowns from previous tests
    close_all_select2_dropdowns(admin_page)

    # Fill admin form
    admin_page.fill("#id_tytul_oryginalny", "tytul oryginalny")

    if admin_page.query_selector("#id_zrodlo"):
        select_select2_autocomplete(
            admin_page, "id_zrodlo", zrodlo_obj.nazwa, timeout=4000
        )

    if admin_page.query_selector("#id_jezyk"):
        select_first_option(admin_page, "#id_jezyk")

    select_charakter_formalny(admin_page)

    if admin_page.query_selector("#id_typ_kbn"):
        select_first_option(admin_page, "#id_typ_kbn")

    admin_page.select_option("#id_status_korekty", label="przed korektą")
    admin_page.fill("#id_rok", str(random.randint(1, 2100)))

    # Add first author inline (50%)
    admin_page.wait_for_selector(".grp-add-handler", state="visible", timeout=10000)
    add_buttons = admin_page.locator(".grp-add-handler").all()
    for button in add_buttons:
        if button.is_visible() and "powiązanie autora" in button.text_content():
            button.click()
            break

    admin_page.wait_for_selector(
        "#id_autorzy_set-0-autor", state="visible", timeout=10000
    )

    # Fill first author (50%)
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-autor", autor1.nazwisko, timeout=4000
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-jednostka", jednostka.nazwa, timeout=4000
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-zapisany_jako", "Kopara1", timeout=4000
    )
    # Select typ_odpowiedzialnosci (responsibility type)
    if admin_page.query_selector("#id_autorzy_set-0-typ_odpowiedzialnosci"):
        admin_page.select_option(
            "#id_autorzy_set-0-typ_odpowiedzialnosci", label="autor"
        )
    admin_page.fill("#id_autorzy_set-0-procent", "50.00")

    # Stabilization wait before adding second author to let DOM fully settle
    admin_page.wait_for_timeout(500)

    # Add second author inline (50%)
    add_buttons = admin_page.locator(".grp-add-handler").all()
    for button in add_buttons:
        if button.is_visible() and "powiązanie autora" in button.text_content():
            button.click()
            break

    admin_page.wait_for_selector(
        "#id_autorzy_set-1-autor", state="visible", timeout=10000
    )

    # Fill second author (50%)
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-1-autor", autor2.nazwisko, timeout=4000
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-1-jednostka", jednostka.nazwa, timeout=4000
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-1-zapisany_jako", "Kopara2", timeout=4000
    )
    # Select typ_odpowiedzialnosci (responsibility type)
    if admin_page.query_selector("#id_autorzy_set-1-typ_odpowiedzialnosci"):
        admin_page.select_option(
            "#id_autorzy_set-1-typ_odpowiedzialnosci", label="autor"
        )
    admin_page.fill("#id_autorzy_set-1-procent", "50.00")

    # Submit form
    admin_page.evaluate('django.jQuery("input[type=submit].grp-default").click()')
    admin_page.wait_for_load_state("domcontentloaded", timeout=10000)

    # Check success
    admin_page.wait_for_function(
        "() => document.body && document.body.textContent.includes("
        "'został(a)(-ło) dodany(-na)(-ne) pomyślnie')",
        timeout=10000,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"]
)
def test_procent_odpowiedzialnosci_baseModel_AutorFormset_problem_dwoch_autorow(  # noqa: C901
    channels_live_server,
    admin_page: Page,
    transactional_db,
    klass,
):
    """Test two authors with invalid percentage (50%+50.01%=100.01%) fails validation."""
    # Create system fixtures and commit
    create_and_commit_fixtures()

    # Create test data and commit (unique names per run)
    autor1, autor2, jednostka, zrodlo_obj = create_two_authors_and_commit("test5")

    url = channels_live_server.url + reverse(f"admin:bpp_{klass}_add")

    # Navigate to page
    admin_page.goto(url)
    admin_page.wait_for_load_state("domcontentloaded")

    # Clean up any lingering Select2 dropdowns from previous tests
    close_all_select2_dropdowns(admin_page)

    # Fill admin form
    admin_page.fill("#id_tytul_oryginalny", "tytul oryginalny")

    if admin_page.query_selector("#id_zrodlo"):
        select_select2_autocomplete(
            admin_page, "id_zrodlo", zrodlo_obj.nazwa, timeout=4000
        )

    if admin_page.query_selector("#id_jezyk"):
        select_first_option(admin_page, "#id_jezyk")

    select_charakter_formalny(admin_page)

    if admin_page.query_selector("#id_typ_kbn"):
        select_first_option(admin_page, "#id_typ_kbn")

    admin_page.select_option("#id_status_korekty", label="przed korektą")
    admin_page.fill("#id_rok", str(random.randint(1, 2100)))

    # Add first author inline (50%)
    admin_page.wait_for_selector(".grp-add-handler", state="visible", timeout=10000)
    add_buttons = admin_page.locator(".grp-add-handler").all()
    for button in add_buttons:
        if button.is_visible() and "powiązanie autora" in button.text_content():
            button.click()
            break

    admin_page.wait_for_selector(
        "#id_autorzy_set-0-autor", state="visible", timeout=10000
    )

    # Fill first author (50%)
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-autor", autor1.nazwisko, timeout=4000
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-jednostka", jednostka.nazwa, timeout=4000
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-0-zapisany_jako", "Kopara1", timeout=4000
    )
    # Select typ_odpowiedzialnosci (responsibility type)
    if admin_page.query_selector("#id_autorzy_set-0-typ_odpowiedzialnosci"):
        admin_page.select_option(
            "#id_autorzy_set-0-typ_odpowiedzialnosci", label="autor"
        )
    admin_page.fill("#id_autorzy_set-0-procent", "50.00")

    # Stabilization wait before adding second author to let DOM fully settle
    admin_page.wait_for_timeout(500)

    # Add second author inline (50.01% - INVALID, total exceeds 100%)
    add_buttons = admin_page.locator(".grp-add-handler").all()
    for button in add_buttons:
        if button.is_visible() and "powiązanie autora" in button.text_content():
            button.click()
            break

    admin_page.wait_for_selector(
        "#id_autorzy_set-1-autor", state="visible", timeout=10000
    )

    # Fill second author (50.01% - INVALID)
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-1-autor", autor2.nazwisko, timeout=4000
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-1-jednostka", jednostka.nazwa, timeout=4000
    )
    select_select2_autocomplete(
        admin_page, "id_autorzy_set-1-zapisany_jako", "Kopara2", timeout=4000
    )
    # Select typ_odpowiedzialnosci (responsibility type)
    if admin_page.query_selector("#id_autorzy_set-1-typ_odpowiedzialnosci"):
        admin_page.select_option(
            "#id_autorzy_set-1-typ_odpowiedzialnosci", label="autor"
        )
    admin_page.fill("#id_autorzy_set-1-procent", "50.01")

    # Submit form
    admin_page.evaluate('django.jQuery("input[type=submit].grp-default").click()')
    admin_page.wait_for_load_state("domcontentloaded", timeout=10000)

    # Check failure - form should not validate with 100.01% total
    admin_page.wait_for_function(
        "() => document.body && document.body.textContent.includes('Prosimy poprawić')",
        timeout=10000,
    )


@pytest.mark.serial
@pytest.mark.django_db
@pytest.mark.parametrize(
    "klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"]
)
def test_procent_odpowiedzialnosci_baseModel_AutorFormset_dobrze_potem_zle_dwoch_autorow(  # noqa: C901, E501
    channels_live_server,
    admin_page: Page,
    transactional_db,
    klass,
):
    """Test valid submission followed by invalid edit (good then bad)."""
    from django.apps import apps

    # Create system fixtures and commit
    create_and_commit_fixtures()

    # Create test data and commit (unique names per run)
    autor1, autor2, jednostka, zrodlo_obj = create_two_authors_and_commit("test4")

    # Track created objects for cleanup
    created_objects = [autor1, autor2, jednostka, zrodlo_obj]
    created_publication = None

    try:
        url = channels_live_server.url + reverse(f"admin:bpp_{klass}_add")

        # Navigate to page
        admin_page.goto(url)
        admin_page.wait_for_load_state("domcontentloaded")

        # Clean up any lingering Select2 dropdowns
        close_all_select2_dropdowns(admin_page)

        # Fill admin form
        admin_page.fill("#id_tytul_oryginalny", "tytul oryginalny")

        if admin_page.query_selector("#id_zrodlo"):
            select_select2_autocomplete(
                admin_page, "id_zrodlo", zrodlo_obj.nazwa, timeout=4000
            )

        if admin_page.query_selector("#id_jezyk"):
            select_first_option(admin_page, "#id_jezyk")

        select_charakter_formalny(admin_page)

        if admin_page.query_selector("#id_typ_kbn"):
            select_first_option(admin_page, "#id_typ_kbn")

        admin_page.select_option("#id_status_korekty", label="przed korektą")
        admin_page.fill("#id_rok", str(random.randint(1, 2100)))

        # Add first author with 50% responsibility
        admin_page.wait_for_selector(".grp-add-handler", state="visible", timeout=10000)
        add_buttons = admin_page.locator(".grp-add-handler").all()
        for button in add_buttons:
            if button.is_visible() and "powiązanie autora" in button.text_content():
                button.click()
                break

        admin_page.wait_for_selector(
            "#id_autorzy_set-0-autor", state="visible", timeout=10000
        )

        select_select2_autocomplete(
            admin_page, "id_autorzy_set-0-autor", autor1.nazwisko, timeout=4000
        )
        select_select2_autocomplete(
            admin_page, "id_autorzy_set-0-jednostka", jednostka.nazwa, timeout=4000
        )
        select_select2_autocomplete(
            admin_page, "id_autorzy_set-0-zapisany_jako", "Kopara1", timeout=4000
        )
        # Select typ_odpowiedzialnosci (responsibility type)
        if admin_page.query_selector("#id_autorzy_set-0-typ_odpowiedzialnosci"):
            admin_page.select_option(
                "#id_autorzy_set-0-typ_odpowiedzialnosci", label="autor"
            )
        admin_page.fill("#id_autorzy_set-0-procent", "50.00")

        # Stabilization wait
        admin_page.wait_for_timeout(500)

        # Add second author with 50% responsibility
        add_buttons = admin_page.locator(".grp-add-handler").all()
        for button in add_buttons:
            if button.is_visible() and "powiązanie autora" in button.text_content():
                button.click()
                break

        admin_page.wait_for_selector(
            "#id_autorzy_set-1-autor", state="visible", timeout=10000
        )

        select_select2_autocomplete(
            admin_page, "id_autorzy_set-1-autor", autor2.nazwisko, timeout=4000
        )
        select_select2_autocomplete(
            admin_page, "id_autorzy_set-1-jednostka", jednostka.nazwa, timeout=4000
        )
        select_select2_autocomplete(
            admin_page, "id_autorzy_set-1-zapisany_jako", "Kopara2", timeout=4000
        )
        # Select typ_odpowiedzialnosci (responsibility type)
        if admin_page.query_selector("#id_autorzy_set-1-typ_odpowiedzialnosci"):
            admin_page.select_option(
                "#id_autorzy_set-1-typ_odpowiedzialnosci", label="autor"
            )
        admin_page.fill("#id_autorzy_set-1-procent", "50.00")

        # Submit form - should succeed
        admin_page.evaluate('django.jQuery("input[type=submit].grp-default").click()')
        admin_page.wait_for_load_state("domcontentloaded", timeout=10000)

        # Check success
        admin_page.wait_for_function(
            "() => document.body && document.body.textContent.includes("
            "'został(a)(-ło) dodany(-na)(-ne) pomyślnie')",
            timeout=10000,
        )

        # Get the saved record and navigate to edit page
        model = apps.get_app_config("bpp").get_model(klass)
        created_publication = model.objects.first()
        url = channels_live_server.url + reverse(
            f"admin:bpp_{klass}_change", args=(created_publication.pk,)
        )

        admin_page.goto(url)
        admin_page.wait_for_load_state("domcontentloaded")

        # Change first author's percentage to 50.01% (making total 100.01%)
        admin_page.fill("#id_autorzy_set-0-procent", "50.01")

        # Submit form - should fail
        admin_page.evaluate('django.jQuery("input[type=submit].grp-default").click()')
        admin_page.wait_for_load_state("domcontentloaded", timeout=10000)

        # Check failure
        admin_page.wait_for_function(
            "() => document.body && document.body.textContent.includes("
            "'Prosimy poprawić')",
            timeout=10000,
        )

    finally:
        # Cleanup: delete created objects in reverse order (publications first,
        # then related objects) to handle foreign key constraints
        old_autocommit = transaction.get_autocommit()
        transaction.set_autocommit(True)
        try:
            # Delete created publication first (has foreign keys to other objects)
            if created_publication is not None:
                try:
                    created_publication.delete()
                except Exception:
                    pass  # May already be deleted or not exist

            # Delete test data objects
            for obj in reversed(created_objects):
                try:
                    obj.delete()
                except Exception:
                    pass  # May already be deleted or have FK constraints
        finally:
            transaction.set_autocommit(old_autocommit)
