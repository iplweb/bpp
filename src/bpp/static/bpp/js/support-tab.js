// Zakladka "Support BPP" przyklejona do prawej krawedzi ekranu.
//
// Wspolna dla admina (admin/base_site.html) i strony publicznej (base.html).
// Celowo bez jQuery - admin ma grp.jQuery, strona publiczna globalne $.
//
// - Widget Freshworks ladowany LENIWIE: skrypt z data-widget-src wstrzykujemy
//   dopiero po pierwszym kliknieciu. Stub FreshworksWidget (inline w
//   szablonie) kolejkuje wywolania w .q, a skrypt Freshworks po
//   wyrenderowaniu widgetu odtwarza kolejke i podmienia window.FreshworksWidget.
// - Zakladke mozna przeciagnac w gore/dol wzdluz krawedzi; pozycja (jako
//   ulamek wysokosci okna) trafia do localStorage. Przeciagniecie nie otwiera
//   widgetu.
// - Skrot "?" otwiera widget, ale tylko gdy fokus NIE jest w polu do pisania.
(function () {
    "use strict";

    var STORAGE_KEY = "bppSupportTabPosition";
    var LOAD_TIMEOUT_MS = 20000;
    var DRAG_THRESHOLD_PX = 5;
    // Odstep od gornej krawedzi - zeby nie wjezdzac na belke nawigacji.
    var MARGIN_TOP_PX = 90;
    var MARGIN_BOTTOM_PX = 10;
    // Stala dolna stopka Grappelli (przyciski Zapisz/Usun) w adminie.
    var FIXED_FOOTER_SELECTOR = "footer.grp-fixed-footer";

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

        function setLoading() {
            state = "loading";
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

        function loadWidget() {
            setLoading();

            // Wywolania trafiaja do kolejki stuba i zostana wykonane w tej
            // kolejnosci po zaladowaniu widgetu.
            window.FreshworksWidget("hide", "launcher");
            window.FreshworksWidget("prefill", "ticketForm", {
                custom_fields: { cf_adres_url: window.location.href }
            });
            window.FreshworksWidget("identify", "ticketForm", {
                name: button.dataset.userName || "",
                email: button.dataset.userEmail || ""
            });
            window.FreshworksWidget("open");
            widgetOpen = true;

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

        function toggleWidget() {
            if (state === "idle") {
                loadWidget();
            } else if (state === "loading") {
                // Skrypt juz sie laduje - nie wstrzykuj ponownie.
                return;
            } else if (state === "error") {
                window.open(button.dataset.fallbackUrl, "_blank", "noopener");
            } else if (!widgetOpen) {
                window.FreshworksWidget("open");
                widgetOpen = true;
            } else {
                window.FreshworksWidget("close");
                widgetOpen = false;
            }
        }

        // --- Pozycja na krawedzi -------------------------------------------

        function bounds() {
            var half = button.offsetHeight / 2;
            var footer = document.querySelector(FIXED_FOOTER_SELECTOR);
            var bottomReserved = footer ? footer.offsetHeight : 0;
            var min = MARGIN_TOP_PX + half;
            var max = window.innerHeight - bottomReserved
                - MARGIN_BOTTOM_PX - half;
            return { min: min, max: Math.max(min, max) };
        }

        // Ustaw srodek zakladki na wysokosci centerY (px), w granicach okna.
        // Pozycjonujemy przez `top` gornej krawedzi, nie przez transform -
        // motywy admina nadpisuja transform na :hover.
        function placeAt(centerY) {
            var b = bounds();
            var clamped = Math.min(Math.max(centerY, b.min), b.max);
            button.style.top = (clamped - button.offsetHeight / 2) + "px";
        }

        function placeFromFraction(fraction) {
            placeAt((fraction === null ? 0.5 : fraction) * window.innerHeight);
        }

        var position = readStoredPosition();
        placeFromFraction(position);
        window.addEventListener("resize", function () {
            placeFromFraction(position);
        });

        // --- Przeciaganie --------------------------------------------------

        var drag = null;
        var suppressClick = false;

        button.addEventListener("pointerdown", function (e) {
            if (e.button !== 0) {
                return;
            }
            drag = {
                pointerId: e.pointerId,
                startY: e.clientY,
                startTop: button.getBoundingClientRect().top
                    + button.offsetHeight / 2,
                moved: false
            };
        });

        button.addEventListener("pointermove", function (e) {
            if (!drag || e.pointerId !== drag.pointerId) {
                return;
            }
            var dy = e.clientY - drag.startY;
            if (!drag.moved && Math.abs(dy) < DRAG_THRESHOLD_PX) {
                return;
            }
            if (!drag.moved) {
                drag.moved = true;
                button.setPointerCapture(e.pointerId);
                button.classList.add("is-dragging");
            }
            placeAt(drag.startTop + dy);
            e.preventDefault();
        });

        function endDrag(e) {
            if (!drag || e.pointerId !== drag.pointerId) {
                return;
            }
            if (drag.moved) {
                button.classList.remove("is-dragging");
                var rect = button.getBoundingClientRect();
                position = (rect.top + rect.height / 2) / window.innerHeight;
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
