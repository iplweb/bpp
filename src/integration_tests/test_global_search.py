import re
import time

import pytest
from model_bakery import baker
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from bpp.models import Rekord, Wydawnictwo_Ciagle
from django_bpp.playwright_util import select_select2_autocomplete, wait_for_page_load


def open_global_search(page: Page) -> None:
    """Press "/" once to open the global-search modal — after the shortcut
    is actually live.

    The "/" shortcut is a document-level ``keydown`` handler installed by
    the modal script's IIFE, which in the same run also defines
    ``window.openGlobalSearch``. ``wait_for_page_load`` only blocks for
    ``domcontentloaded``, so on a slow (CI) page jQuery + that inline
    script may not have finished when the test runs — the handler isn't
    bound yet and a single ``press("/")`` is silently dropped. This is the
    flakiness #254 exposed by deleting the fixed ``time.sleep`` that used
    to wait the script out.

    Waiting for ``window.openGlobalSearch`` to exist is the precise
    readiness signal: it is defined by the same IIFE that binds the
    keydown listener, so once it is a function the shortcut is live. Then
    press "/" exactly once, the way a user would — the test still verifies
    that a single keystroke opens the dialog.
    """
    page.wait_for_function("() => typeof window.openGlobalSearch === 'function'")
    page.keyboard.press("/")
    page.wait_for_selector("#globalSearchInput", state="visible", timeout=5000)


def test_global_search_user(
    channels_live_server,
    page: Page,
    transactional_db,
):
    rec = None
    try:
        rec = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test")
        Rekord.objects.full_refresh()

        assert Rekord.objects.count() >= 1
        assert Rekord.objects.filter(tytul_oryginalny__icontains="Test").exists()

        page.goto(channels_live_server.url)
        wait_for_page_load(page)

        # Accept cookies if needed (synchronous; banner gone once it returns).
        page.evaluate("if (typeof Cookielaw !== 'undefined') { Cookielaw.accept(); }")

        # Open the global search dialog via the "/" shortcut (resilient to
        # the keydown handler not yet being live on a cold CI page).
        open_global_search(page)

        # Type the search term directly into the input
        page.fill("#globalSearchInput", "Test")

        # Wait for "Rekord" to appear in the dropdown
        page.wait_for_function(
            "() => document.querySelector('#globalSearchResults').textContent.includes('Rekord')",
            timeout=5000,
        )

        # Press Enter to select
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        wait_for_page_load(page)

        try:
            page.wait_for_function(
                "() => document.body.textContent.includes('Charakter formalny')",
                timeout=10000,
            )
        except PlaywrightTimeoutError as e:
            html_content = page.content()
            raise PlaywrightTimeoutError(f"Page content dump: {html_content}") from e

    finally:
        if rec is not None:
            rec.delete()


@pytest.mark.serial
def test_global_search_logged_in(
    channels_live_server_per_test,
    admin_page_per_test: Page,
    transactional_db,
):
    admin_page = admin_page_per_test
    rec = None
    try:
        # Create a unique title to avoid conflicts with other tests
        import uuid

        unique_title = f"Test_{uuid.uuid4().hex[:8]}"

        rec = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=unique_title)

        # Ensure the Rekord cache is refreshed for this specific record
        Rekord.objects.full_refresh()

        # Verify the record was properly indexed
        assert Rekord.objects.filter(
            tytul_oryginalny__icontains=unique_title
        ).exists(), (
            f"Record with title '{unique_title}' not found in Rekord cache after refresh"
        )

        admin_page.goto(channels_live_server_per_test.url)
        wait_for_page_load(admin_page)

        # Accept cookies if needed (synchronous; banner gone once it returns).
        admin_page.evaluate(
            "if (typeof Cookielaw !== 'undefined') { Cookielaw.accept(); }"
        )

        # Open the global search dialog via the "/" shortcut (resilient to
        # the keydown handler not yet being live on a cold CI page).
        open_global_search(admin_page)

        # Type the search term directly into the input - use the unique title
        admin_page.fill("#globalSearchInput", unique_title)

        # Wait for "Rekord" to appear in the dropdown
        admin_page.wait_for_function(
            "() => document.querySelector('#globalSearchResults').textContent.includes('Rekord')",
            timeout=5000,
        )

        # Press Enter to select
        admin_page.keyboard.press("ArrowDown")
        admin_page.keyboard.press("Enter")
        wait_for_page_load(admin_page)

        try:
            admin_page.wait_for_function(
                "() => document.body.textContent.includes('Charakter formalny')",
                timeout=10000,
            )
        except PlaywrightTimeoutError as e:
            html_content = admin_page.content()
            raise PlaywrightTimeoutError(f"Page content dump: {html_content}") from e
    finally:
        if rec is not None:
            # Delete the record and ensure it's removed from cache
            rec.delete()


def test_global_search_in_admin(
    channels_live_server, admin_page: Page, transactional_db
):
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test")

    admin_page.goto(channels_live_server.url + "/admin/")
    wait_for_page_load(admin_page)

    # Accept cookies if needed
    admin_page.evaluate("if (typeof Cookielaw !== 'undefined') { Cookielaw.accept(); }")

    select_select2_autocomplete(
        admin_page,
        "id_global_nav_value",
        "Test",
        value_before_enter="ydawnictwo",
        wait_for_new_value=False,  # False, bo zmiana wartosci powoduje wczytanie strony
    )
    wait_for_page_load(admin_page)

    admin_page.wait_for_function(
        "() => document.body.textContent.includes('Zmień wydawnictwo ciągłe')",
        timeout=10000,
    )


# Samples the page on every animation frame. Each sample holds the viewport
# rects of the sticky top bar and the sticky breadcrumbs, window.scrollY and
# the effective backdrop opacity (0 while the modal is display:none or
# visibility:hidden). The test switches ``phase`` between the steps.
_START_FRAME_PROBE_JS = """
() => {
    const rect = (selector) => {
        const r = document.querySelector(selector).getBoundingClientRect();
        return [r.top, r.left, r.width, r.height];
    };
    const modal = document.getElementById('globalSearchModal');
    const probe = {phase: 'before', stop: false, samples: []};
    window.__layoutProbe = probe;
    const tick = () => {
        const style = getComputedStyle(modal);
        const hidden = style.display === 'none' || style.visibility === 'hidden';
        probe.samples.push({
            phase: probe.phase,
            nav: rect('nav.sticky-header'),
            breadcrumbs: rect('#breadcrumbs-wrapper'),
            scrollY: window.scrollY,
            opacity: hidden ? 0 : parseFloat(style.opacity),
        });
        if (!probe.stop) {
            requestAnimationFrame(tick);
        }
    };
    requestAnimationFrame(tick);
}
"""

_MODAL_FULLY_SHOWN_JS = """
() => {
    const modal = document.getElementById('globalSearchModal');
    return parseFloat(getComputedStyle(modal).opacity) === 1;
}
"""

_MODAL_HIDDEN_JS = """
() => {
    const style = getComputedStyle(document.getElementById('globalSearchModal'));
    return style.display === 'none' || style.visibility === 'hidden';
}
"""

_MODAL_ANIMATIONS_SETTLED_JS = """
() => document.getElementById('globalSearchModal')
    .getAnimations({subtree: true})
    .every((animation) => animation.playState !== 'running')
"""


def _wait_frames(page: Page, count: int) -> None:
    n = page.evaluate("() => window.__layoutProbe.samples.length")
    page.wait_for_function(f"() => window.__layoutProbe.samples.length >= {n + count}")


def _set_phase(page: Page, phase: str) -> None:
    page.evaluate(f"() => {{ window.__layoutProbe.phase = '{phase}'; }}")


def _record_open_close_cycle(page: Page, url: str) -> list[dict]:
    """Open and close the global search on a scrolled page, sampling every
    animation frame. Samples are tagged: before / opening / open / closing /
    closed."""
    # Consent cookie up front: Cookielaw.accept() reloads the page, which
    # would destroy the frame probe mid-test.
    page.context.add_cookies([{"name": "cookielaw_accepted", "value": "1", "url": url}])
    page.goto(url)
    wait_for_page_load(page)
    assert page.query_selector("#breadcrumbs-wrapper"), (
        "the test page must render the sticky breadcrumbs"
    )

    # Scroll so that both sticky bars are actually stuck: at scrollY == 0 a
    # scroll lock that re-positions <body> moves nothing and hides the bug.
    page.evaluate(
        """() => {
            const spacer = document.createElement('div');
            spacer.style.height = '3000px';
            document.body.appendChild(spacer);
            window.scrollTo(0, 400);
        }"""
    )
    page.wait_for_function("() => window.scrollY === 400")

    page.evaluate(_START_FRAME_PROBE_JS)
    _wait_frames(page, 2)

    _set_phase(page, "opening")
    open_global_search(page)
    page.wait_for_function(_MODAL_FULLY_SHOWN_JS)
    page.wait_for_function(_MODAL_ANIMATIONS_SETTLED_JS)

    # Neither a wheel over the backdrop (corner outside the dialog box) nor
    # keyboard scrolling with focus outside the input may scroll the page
    # underneath. The wheel is also blocked by a JS handler; PageDown is
    # stopped only by the scroll lock itself.
    _set_phase(page, "open")
    page.mouse.move(5, page.viewport_size["height"] - 5)
    page.mouse.wheel(0, 600)
    page.evaluate("() => document.activeElement.blur()")
    page.keyboard.press("PageDown")
    _wait_frames(page, 5)

    _set_phase(page, "closing")
    page.keyboard.press("Escape")
    page.wait_for_function(_MODAL_HIDDEN_JS)
    page.wait_for_function(_MODAL_ANIMATIONS_SETTLED_JS)

    _set_phase(page, "closed")
    _wait_frames(page, 5)
    return page.evaluate(
        "() => { window.__layoutProbe.stop = true; "
        "return window.__layoutProbe.samples; }"
    )


def _same_position(expected, actual, tolerance=0.5) -> bool:
    if isinstance(expected, list):
        return all(
            abs(e - a) <= tolerance for e, a in zip(expected, actual, strict=True)
        )
    return abs(expected - actual) <= tolerance


def test_global_search_does_not_move_page_layout(
    channels_live_server, page: Page, transactional_db
):
    """Nothing under the backdrop moves while the global search opens,
    stays open and closes: the sticky top bar, the sticky breadcrumbs and
    the scroll position are identical in every animation frame. Catches a
    scroll lock that re-positions <body> (it breaks position: sticky) and
    any hide/slide choreography of the bar that shifts the layout."""
    samples = _record_open_close_cycle(page, channels_live_server.url)

    baseline = samples[0]
    moved = [
        (sample["phase"], key, baseline[key], sample[key])
        for sample in samples
        for key in ("nav", "breadcrumbs", "scrollY")
        if not _same_position(baseline[key], sample[key])
    ]
    assert not moved, (
        f"page layout moved: {len(moved)} deviations in {len(samples)} frames, "
        f"first ones (phase, element, expected, actual): {moved[:5]}"
    )


def test_global_search_backdrop_fades_gradually(
    channels_live_server, page: Page, transactional_db
):
    """The blurred backdrop passes through intermediate opacity both while
    opening and while closing, instead of popping in or out in one frame.
    Catches a backdrop that is switched from display:none (a CSS transition
    never starts from display:none)."""
    samples = _record_open_close_cycle(page, channels_live_server.url)

    for phase in ("opening", "closing"):
        opacities = [s["opacity"] for s in samples if s["phase"] == phase]
        partial = [o for o in opacities if 0.05 < o < 0.95]
        assert partial, (
            f"backdrop has no intermediate opacity while {phase}; "
            f"sampled opacities: {opacities}"
        )


_AUTOCOMPLETE_URL = re.compile(r"/bpp/navigation-autocomplete/")

# Samples the global-search dialog height on every animation frame.
_START_HEIGHT_PROBE_JS = """
() => {
    const box = document.querySelector('.global-search-container');
    const probe = {stop: false, heights: []};
    window.__heightProbe = probe;
    const tick = () => {
        probe.heights.push(box.getBoundingClientRect().height);
        if (!probe.stop) {
            requestAnimationFrame(tick);
        }
    };
    requestAnimationFrame(tick);
}
"""

_DIALOG_HEIGHT_JS = (
    "() => document.querySelector('.global-search-container')"
    ".getBoundingClientRect().height"
)


def _autocomplete_payload(group_sizes: list[int]) -> dict:
    """JSON shaped like the GlobalNavigationAutocomplete response: one group
    per content type, children with ``<content type>-<pk>`` ids."""
    return {
        "results": [
            {
                "id": None,
                "text": f"Grupa {group}",
                "children": [
                    {"id": f"{group}-{item}", "text": f"Testowy wynik {group}.{item}"}
                    for item in range(size)
                ],
            }
            for group, size in enumerate(group_sizes)
        ],
        "pagination": {"more": False},
    }


def _wait_for_routes(page: Page, routes: list, count: int):
    """Wait until ``count`` autocomplete requests were intercepted; return the
    last one (still unanswered)."""
    deadline = time.monotonic() + 5
    while len(routes) < count:
        assert time.monotonic() < deadline, (
            f"expected {count} autocomplete requests, got {len(routes)}"
        )
        page.wait_for_timeout(50)
    return routes[count - 1]


def _wait_height_frames(page: Page, count: int) -> None:
    n = page.evaluate("() => window.__heightProbe.heights.length")
    page.wait_for_function(f"() => window.__heightProbe.heights.length >= {n + count}")


def test_global_search_dialog_does_not_collapse_while_next_search_loads(
    channels_live_server, page: Page, transactional_db
):
    """Editing the query while results are shown ("test" -> Backspace -> "t")
    must not collapse the dialog while the next response is pending: the
    previous results stay until the new ones replace them in one step.
    Catches a loading placeholder that replaces the result list."""
    routes = []
    # Requests are parked here and answered by the test at a chosen moment.
    page.route(_AUTOCOMPLETE_URL, lambda route: routes.append(route))
    url = channels_live_server.url
    page.context.add_cookies([{"name": "cookielaw_accepted", "value": "1", "url": url}])
    page.goto(url)
    wait_for_page_load(page)
    open_global_search(page)

    page.fill("#globalSearchInput", "test")
    _wait_for_routes(page, routes, 1).fulfill(json=_autocomplete_payload([4, 4]))
    page.wait_for_function(
        "() => document.querySelectorAll('.search-result-item').length === 8"
    )
    page.wait_for_function(_MODAL_ANIMATIONS_SETTLED_JS)
    page.evaluate(_START_HEIGHT_PROBE_JS)
    _wait_height_frames(page, 2)
    height_with_results = page.evaluate(_DIALOG_HEIGHT_JS)

    # Two follow-up requests ("tes", then "test"), both left unanswered.
    # Caret to the end first: openGlobalSearch() selects the input text on a
    # timer, and a Backspace over the selection would clear the whole query.
    # (No "End" key: on macOS Firefox/WebKit it does not move the caret.)
    page.evaluate(
        "() => { const input = document.querySelector('#globalSearchInput'); "
        "input.setSelectionRange(input.value.length, input.value.length); }"
    )
    page.keyboard.press("Backspace")
    assert page.input_value("#globalSearchInput") == "tes"
    _wait_for_routes(page, routes, 2)
    _wait_height_frames(page, 10)
    page.keyboard.type("t")
    assert page.input_value("#globalSearchInput") == "test"
    latest = _wait_for_routes(page, routes, 3)
    _wait_height_frames(page, 10)
    heights_while_loading = page.evaluate("() => window.__heightProbe.heights.slice()")

    latest.fulfill(json=_autocomplete_payload([2]))
    page.wait_for_function(
        "() => document.querySelectorAll('.search-result-item').length === 2"
    )
    page.wait_for_function(_MODAL_ANIMATIONS_SETTLED_JS)
    _wait_height_frames(page, 10)
    height_with_new_results = page.evaluate(_DIALOG_HEIGHT_JS)
    heights = page.evaluate(
        "() => { window.__heightProbe.stop = true; "
        "return window.__heightProbe.heights; }"
    )
    # The page aborted the "tes" request, so it was never answered; settle
    # its parked route so nothing is left pending when the page closes.
    routes[1].abort()

    assert min(heights_while_loading) >= height_with_results - 0.5, (
        f"dialog shrank while the next search was loading: "
        f"{height_with_results} -> {min(heights_while_loading)}"
    )
    floor = min(height_with_results, height_with_new_results)
    assert min(heights) >= floor - 0.5, (
        f"dialog dipped below both the old ({height_with_results}) and the "
        f"new ({height_with_new_results}) height: {min(heights)}"
    )
