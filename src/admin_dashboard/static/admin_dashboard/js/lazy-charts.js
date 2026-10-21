/*
 * Leniwe wykresy na stronie głównej admina.
 *
 * Każdy element `.lazy-chart[data-chart-url]` pobiera dane i rysuje się
 * dopiero, gdy zbliży się do viewportu. Plotly (~4.5 MB) doładowujemy
 * raz, przy pierwszym widocznym wykresie — zamiast blokować <head>.
 *
 * Atrybuty elementu:
 *   data-chart-url        — endpoint JSON zwracający {data, layout}
 *   data-chart-clickable  — obecny: klik w wycinek z customdata = URL
 *                           przenosi do listy w adminie
 *
 * Kontener `.lazy-chart-wrapper[data-plotly-src][data-plotly-locale-src]`
 * mówi, skąd wziąć Plotly.
 */
(function () {
    "use strict";

    var PLOT_CONFIG = {responsive: true, displaylogo: false, locale: "pl"};
    // Zaczynamy ładować trochę przed wjechaniem wykresu w ekran, żeby
    // przy normalnym przewijaniu dane były już gotowe.
    var ROOT_MARGIN = "300px 0px";
    // Ile żądań o dane naraz — nie zapychamy workerów serwera, gdy
    // ktoś szybko przewinie całą stronę.
    var MAX_CONCURRENT = 3;

    var plotlyPromise = null;
    var active = 0;
    var queue = [];

    function loadScript(src) {
        return new Promise(function (resolve, reject) {
            var s = document.createElement("script");
            s.src = src;
            s.async = false; // locale musi się wykonać PO plotly
            s.onload = resolve;
            s.onerror = function () {
                reject(new Error("Nie udało się wczytać " + src));
            };
            document.head.appendChild(s);
        });
    }

    function ensurePlotly(wrapper) {
        if (window.Plotly) {
            return Promise.resolve(window.Plotly);
        }
        if (!plotlyPromise) {
            plotlyPromise = Promise.all([
                loadScript(wrapper.dataset.plotlySrc),
                loadScript(wrapper.dataset.plotlyLocaleSrc),
            ]).then(function () {
                window.Plotly.setPlotConfig({locale: "pl"});
                return window.Plotly;
            }, function (err) {
                plotlyPromise = null; // pozwól na ponowienie
                throw err;
            });
        }
        return plotlyPromise;
    }

    function schedule(task) {
        queue.push(task);
        pump();
    }

    function pump() {
        while (active < MAX_CONCURRENT && queue.length) {
            active++;
            queue.shift()().then(done, done);
        }
    }

    function done() {
        active--;
        pump();
    }

    function fetchJSON(url) {
        return fetch(url, {
            credentials: "same-origin",
            headers: {"X-Requested-With": "XMLHttpRequest"},
        }).then(function (response) {
            if (!response.ok) {
                throw new Error("HTTP " + response.status);
            }
            return response.json();
        });
    }

    function bindClicks(el) {
        el.on("plotly_hover", function (ev) {
            el.style.cursor = ev.points[0].customdata ? "pointer" : "default";
        });
        el.on("plotly_unhover", function () {
            el.style.cursor = "default";
        });
        el.on("plotly_click", function (ev) {
            var point = ev.points[0];
            if (point.label === "Inne") {
                alert("Te charaktery formalne pokazane są na innym wykresie");
                return;
            }
            if (point.customdata) {
                window.location.href = point.customdata;
            }
        });
    }

    function showError(el, wrapper, err) {
        console.error("Błąd ładowania wykresu", el.dataset.chartUrl, err);
        el.classList.remove("is-loading");
        el.classList.add("is-error");
        el.innerHTML = "";
        var msg = document.createElement("p");
        msg.className = "lazy-chart__error";
        msg.textContent = "Nie udało się wczytać wykresu. ";
        var retry = document.createElement("button");
        retry.type = "button";
        retry.className = "grp-button";
        retry.textContent = "Spróbuj ponownie";
        retry.addEventListener("click", function () {
            el.classList.remove("is-error");
            el.innerHTML = "";
            load(el, wrapper);
        });
        msg.appendChild(retry);
        el.appendChild(msg);
    }

    function load(el, wrapper) {
        el.classList.add("is-loading");
        schedule(function () {
            // Dane i biblioteka pobierają się równolegle.
            return Promise.all([
                fetchJSON(el.dataset.chartUrl),
                ensurePlotly(wrapper),
            ]).then(function (results) {
                var payload = results[0];
                var Plotly = results[1];
                return Plotly.newPlot(
                    el, payload.data, payload.layout, PLOT_CONFIG
                ).then(function () {
                    if (el.hasAttribute("data-chart-clickable")) {
                        bindClicks(el);
                    }
                    el.classList.remove("is-loading");
                    el.classList.add("is-loaded");
                });
            }).catch(function (err) {
                showError(el, wrapper, err);
            });
        });
    }

    function init() {
        var wrapper = document.querySelector(".lazy-chart-wrapper");
        if (!wrapper) {
            return;
        }
        var charts = wrapper.querySelectorAll(".lazy-chart[data-chart-url]");

        if (!("IntersectionObserver" in window)) {
            charts.forEach(function (el) { load(el, wrapper); });
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    observer.unobserve(entry.target);
                    load(entry.target, wrapper);
                }
            });
        }, {rootMargin: ROOT_MARGIN});

        charts.forEach(function (el) { observer.observe(el); });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
