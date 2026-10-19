// Zakladka "Pomoc" w prawym dolnym rogu ekranu.
//
// Wspolna dla admina (admin/base_site.html) i strony publicznej (base.html).
// Celowo bez jQuery - admin ma grp.jQuery, strona publiczna globalne $.
//
// - Widget Freshworks ladowany LENIWIE: skrypt z data-widget-src wstrzykujemy
//   dopiero, gdy uzytkownik najedzie na zakladke (albo wejdzie na nia
//   klawiatura) - zanim kliknie, widget zwykle jest juz gotowy. Stub
//   FreshworksWidget (inline w szablonie) kolejkuje wywolania w .q, a skrypt
//   Freshworks po wyrenderowaniu widgetu odtwarza kolejke i podmienia
//   window.FreshworksWidget.
// - Okno widgetu wyskakuje Z zakladki i do niej sie chowa: polozenie i punkt
//   skalowania okna przekazujemy do CSS (_support_widget.scss) w zmiennych
//   --bpp-support-widget-*.
// - Zakladka wystaje znad dolnej krawedzi okna, a w adminie - znad stalej
//   belki z przyciskami (Zapisz/Usun), jesli strona ja ma. Jest odsunieta od
//   prawej krawedzi, zeby klikniecie nie trafialo w pasek przewijania.
// - Zakladke mozna przeciagnac w lewo/prawo wzdluz dolnej krawedzi; pozycja
//   (jako ulamek szerokosci okna) trafia do localStorage. Przeciagniecie nie
//   otwiera widgetu.
// - Skrot "?" otwiera widget, ale tylko gdy fokus NIE jest w polu do pisania.
(function () {
    "use strict";

    // Inny klucz niz we wczesniejszej wersji (pionowa zakladka na prawej
    // krawedzi zapisywala tam pozycje w pionie).
    var STORAGE_KEY = "bppSupportTabRight";
    var LOAD_TIMEOUT_MS = 20000;
    var DRAG_THRESHOLD_PX = 5;
    // Odstep od bocznych krawedzi - z prawej m.in. po to, zeby klikniecie
    // w zakladke nie trafialo w (nakladkowy) pasek przewijania.
    var MARGIN_SIDE_PX = 24;
    // Stala dolna belka Grappelli z przyciskami (Zapisz/Usun) w adminie.
    var BUTTON_BAR_SELECTOR = "footer#submit, footer.grp-fixed-footer";
    // Okno widgetu Freshworks: szerokosc z ich CSS i odstep od zakladki.
    var WIDGET_WRAPPER_ID = "freshworks-frame-wrapper";
    var WIDGET_CONTAINER_ID = "freshworks-container";
    var WIDGET_WIDTH_PX = 384;
    var WIDGET_GAP_PX = 8;
    // Klasa animacji chowania okna do zakladki (_support_widget.scss).
    var WIDGET_CLOSING_CLASS = "bpp-support-widget-closing";
    var WIDGET_CLOSE_ANIMATION_MS = 200;

    function readStoredPosition() {
        try {
            var value = parseFloat(window.localStorage.getItem(STORAGE_KEY));
            return isNaN(value) ? null : value;
        } catch (e) {
            // localStorage niedostepny (tryb prywatny, zablokowane dane)
            return null;
        }
    }

    function storePosition(fraction) {
        try {
            window.localStorage.setItem(STORAGE_KEY, String(fraction));
        } catch (e) {
            // localStorage niedostepny - pozycja nie przetrwa przeladowania
            return;
        }
    }

    function isTypingTarget(el) {
        if (!el || el === document.body) {
            return false;
        }
        if (el.isContentEditable) {
            return true;
        }
        var tag = el.tagName;
        return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
    }

    function init(button) {
        var label = button.querySelector(".support-text");
        var defaultLabel = label.textContent;
        var stub = window.FreshworksWidget;

        // 'idle' -> 'loading' -> 'ready' | 'error'
        var state = "idle";
        // Freshworks nie udostepnia zdarzen zamkniecia widgetu (brak metody
        // 'on' w API bootstrapu), wiec stan sledzimy sami.
        var widgetOpen = false;

        function showLoading() {
            button.classList.add("is-loading");
            button.setAttribute("aria-busy", "true");
            label.textContent = "Ładowanie...";
        }

        function setReady() {
            state = "ready";
            button.classList.remove("is-loading");
            button.removeAttribute("aria-busy");
            label.textContent = defaultLabel;
        }

        function setError() {
            state = "error";
            widgetOpen = false;
            button.classList.remove("is-loading");
            button.removeAttribute("aria-busy");
            button.classList.add("is-error");
            button.setAttribute(
                "title",
                "Nie udało się załadować widgetu wsparcia. "
                    + "Kliknij, aby przejść do support.iplweb.pl"
            );
            label.textContent = "support.iplweb.pl";
        }

        // Wstrzyknij skrypt widgetu (bez otwierania). Wywolania trafiaja do
        // kolejki stuba i zostana wykonane w tej kolejnosci po zaladowaniu.
        function startLoading() {
            state = "loading";
            window.FreshworksWidget("hide", "launcher");
            window.FreshworksWidget("prefill", "ticketForm", {
                custom_fields: { cf_adres_url: window.location.href }
            });
            window.FreshworksWidget("identify", "ticketForm", {
                name: button.dataset.userName || "",
                email: button.dataset.userEmail || ""
            });

            var script = document.createElement("script");
            script.type = "text/javascript";
            script.async = true;
            script.src = button.dataset.widgetSrc;
            script.onerror = setError;
            document.body.appendChild(script);

            // Widget gotowy = skrypt Freshworks podmienil stuba.
            var started = Date.now();
            var timer = setInterval(function () {
                if (state !== "loading") {
                    clearInterval(timer);
                } else if (window.FreshworksWidget !== stub) {
                    clearInterval(timer);
                    setReady();
                } else if (Date.now() - started > LOAD_TIMEOUT_MS) {
                    clearInterval(timer);
                    setError();
                }
            }, 200);
        }

        function preload() {
            if (state === "idle") {
                startLoading();
            }
        }

        function openWidget() {
            updateWidgetAnchor();
            // Przed zaladowaniem skryptu "open" czeka w kolejce stuba.
            window.FreshworksWidget("open");
            widgetOpen = true;
        }

        // Schowaj okno do zakladki, a dopiero potem zamknij widget -
        // Freshworks przy "close" od razu usuwa okno z DOM, wiec bez tego
        // nie byloby animacji.
        function closeWidget() {
            widgetOpen = false;
            var wrapper = document.getElementById(WIDGET_WRAPPER_ID);
            var reducedMotion = window.matchMedia
                && window.matchMedia("(prefers-reduced-motion: reduce)")
                    .matches;
            if (!wrapper || reducedMotion) {
                window.FreshworksWidget("close");
                return;
            }
            var done = false;
            function finish() {
                if (done) {
                    return;
                }
                done = true;
                window.FreshworksWidget("close");
                wrapper.classList.remove(WIDGET_CLOSING_CLASS);
            }
            wrapper.classList.add(WIDGET_CLOSING_CLASS);
            wrapper.addEventListener("animationend", finish, { once: true });
            // Gdyby animationend nie przyszlo (np. okno ukryte media query).
            setTimeout(finish, WIDGET_CLOSE_ANIMATION_MS + 100);
        }

        // Czy okno jest otwarte. Prawdziwy widget zostawia w DOM kontener,
        // a okno istnieje tylko, gdy jest otwarte - to lapie tez zamkniecie
        // krzyzykiem w oknie (iframe, zdarzen nie dostajemy). Bez kontenera
        // (stub w testach) zostaje nasz wlasny stan.
        function isWidgetOpen() {
            if (document.getElementById(WIDGET_CONTAINER_ID)) {
                return Boolean(document.getElementById(WIDGET_WRAPPER_ID));
            }
            return widgetOpen;
        }

        function toggleWidget() {
            if (state === "error") {
                window.open(button.dataset.fallbackUrl, "_blank", "noopener");
                return;
            }
            if (state === "idle") {
                startLoading();
            }
            if (state === "loading") {
                // Skrypt juz sie laduje - "open" poczeka w kolejce stuba.
                if (!widgetOpen) {
                    showLoading();
                    openWidget();
                }
            } else if (isWidgetOpen()) {
                closeWidget();
            } else {
                openWidget();
            }
        }

        button.addEventListener("pointerenter", preload);
        button.addEventListener("focus", preload);

        // --- Pozycja przy dolnej krawedzi ---------------------------------

        // Wysokosc nad dolna krawedzia okna, od ktorej zakladka wystaje:
        // gorna krawedz belki z przyciskami albo 0, gdy belki nie ma
        // (lub jest poza ekranem).
        function bottomOffset() {
            var bar = document.querySelector(BUTTON_BAR_SELECTOR);
            if (!bar || bar.offsetHeight === 0) {
                return 0;
            }
            var barTop = bar.getBoundingClientRect().top;
            return Math.max(0, window.innerHeight - barTop);
        }

        function updateBottom() {
            button.style.bottom = bottomOffset() + "px";
            updateWidgetAnchor();
        }

        // Okno widgetu stoi tuz nad zakladka, prawym brzegiem rowno z nia
        // (o ile miesci sie w oknie), a skaluje sie od srodka zakladki.
        function updateWidgetAnchor() {
            var rect = button.getBoundingClientRect();
            var width = document.documentElement.clientWidth;
            var right = Math.min(
                width - rect.right,
                Math.max(WIDGET_GAP_PX, width - WIDGET_WIDTH_PX - WIDGET_GAP_PX)
            );
            var bottom = window.innerHeight - rect.top + WIDGET_GAP_PX;
            // Srodek zakladki wzgledem prawego dolnego rogu okna widgetu.
            var originX = width - right - (rect.left + rect.width / 2);
            var originY = WIDGET_GAP_PX + rect.height / 2;
            var style = document.documentElement.style;
            style.setProperty("--bpp-support-widget-right", right + "px");
            style.setProperty("--bpp-support-widget-bottom", bottom + "px");
            style.setProperty(
                "--bpp-support-widget-origin",
                "calc(100% - " + originX + "px) calc(100% + " + originY + "px)"
            );
        }

        // Ustaw odleglosc prawej krawedzi zakladki od prawej krawedzi okna
        // (px), w granicach okna.
        function placeAt(rightPx) {
            var max = document.documentElement.clientWidth
                - button.offsetWidth - MARGIN_SIDE_PX;
            var clamped = Math.min(
                Math.max(rightPx, MARGIN_SIDE_PX),
                Math.max(MARGIN_SIDE_PX, max)
            );
            button.style.right = clamped + "px";
            updateWidgetAnchor();
        }

        var position = readStoredPosition();
        function reposition() {
            placeAt(position === null
                ? MARGIN_SIDE_PX
                : position * document.documentElement.clientWidth);
            updateBottom();
        }

        reposition();
        window.addEventListener("resize", reposition);
        // Belka z przyciskami nie musi byc stala - wtedy zakladka jedzie nad
        // nia razem z przewijaniem.
        var scrollPending = false;
        window.addEventListener("scroll", function () {
            if (scrollPending) {
                return;
            }
            scrollPending = true;
            window.requestAnimationFrame(function () {
                scrollPending = false;
                updateBottom();
            });
        }, { passive: true });
        // W adminie arkusze CSS sa dolaczane PO zakladce (blok footer), wiec
        // przy starcie skryptu ani zakladka, ani belka z przyciskami nie maja
        // jeszcze stylow. Po zaladowaniu strony przelicz pozycje.
        if (document.readyState !== "complete") {
            window.addEventListener("load", reposition);
        }

        // --- Przeciaganie --------------------------------------------------

        var drag = null;
        var suppressClick = false;

        button.addEventListener("pointerdown", function (e) {
            if (e.button !== 0) {
                return;
            }
            drag = {
                pointerId: e.pointerId,
                startX: e.clientX,
                startRight: document.documentElement.clientWidth
                    - button.getBoundingClientRect().right,
                moved: false
            };
        });

        button.addEventListener("pointermove", function (e) {
            if (!drag || e.pointerId !== drag.pointerId) {
                return;
            }
            var dx = e.clientX - drag.startX;
            if (!drag.moved && Math.abs(dx) < DRAG_THRESHOLD_PX) {
                return;
            }
            if (!drag.moved) {
                drag.moved = true;
                button.setPointerCapture(e.pointerId);
                button.classList.add("is-dragging");
            }
            placeAt(drag.startRight - dx);
            e.preventDefault();
        });

        function endDrag(e) {
            if (!drag || e.pointerId !== drag.pointerId) {
                return;
            }
            if (drag.moved) {
                button.classList.remove("is-dragging");
                var width = document.documentElement.clientWidth;
                position = (width - button.getBoundingClientRect().right)
                    / width;
                storePosition(position);
                // Po przeciagnieciu przegladarka wysle jeszcze click (w tym
                // samym tasku co pointerup) - polknij go. Timeout zdejmuje
                // flage, gdyby click nie przyszedl, zeby nie polknac
                // nastepnego, prawdziwego klikniecia.
                suppressClick = true;
                setTimeout(function () {
                    suppressClick = false;
                }, 0);
            }
            drag = null;
        }

        button.addEventListener("pointerup", endDrag);
        button.addEventListener("pointercancel", endDrag);

        button.addEventListener("click", function (e) {
            e.preventDefault();
            if (suppressClick) {
                suppressClick = false;
                return;
            }
            toggleWidget();
        });

        // --- Skrot klawiszowy "?" -------------------------------------------

        document.addEventListener("keydown", function (e) {
            if (e.key !== "?" || e.ctrlKey || e.metaKey || e.altKey) {
                return;
            }
            if (e.defaultPrevented || isTypingTarget(document.activeElement)) {
                return;
            }
            e.preventDefault();
            toggleWidget();
        });
    }

    function boot() {
        var button = document.getElementById("bppSupportButton");
        if (button) {
            init(button);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})();
