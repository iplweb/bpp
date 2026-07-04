/**
 * Prawy panel „Źródło docelowe" na stronie przemapowania.
 *
 * Po wyborze / zmianie źródła w comboboxie (DAL Select2) doczytuje AJAX-em te
 * same parametry co panel źródłowy (skrót, ISSN, e-ISSN, PBN UID, MNiSW ID,
 * BPP ID, liczba publikacji), podświetla zgodne/rozbieżne wartości i — gdy
 * źródło źródłowe jest ministerialne — ostrzega, że przemapowanie na inne
 * (lub żadne) MNiSW ID zostanie odrzucone.
 *
 * Ostrzeżenie jest wyłącznie podpowiedzią UX. Autorytatywną blokadą jest
 * walidacja formularza po stronie serwera (clean_zrodlo_docelowe) — JS nigdy
 * nie jest źródłem prawdy.
 */
(function () {
    "use strict";

    function ready(fn) {
        if (document.readyState !== "loading") {
            fn();
        } else {
            document.addEventListener("DOMContentLoaded", fn);
        }
    }

    ready(function () {
        var panels = document.getElementById("przemapuj-panels");
        var select = document.getElementById("id_zrodlo_docelowe");
        if (!panels || !select) {
            return;
        }

        var infoUrlBase = panels.dataset.infoUrlBase; // np. /przemapuj-zrodlo/info/0/
        var srcNazwa = panels.dataset.srcNazwa || "";
        // Efektywne MNiSW ID źródła (string) albo null gdy nieministerialne.
        var srcMnisw =
            panels.dataset.srcMniswEffective === ""
                ? null
                : panels.dataset.srcMniswEffective;

        function txt(id) {
            var el = document.getElementById(id);
            return el ? el.textContent.trim() : "";
        }

        var srcIssn = txt("src-issn");
        var srcEissn = txt("src-eissn");

        function el(id) {
            return document.getElementById(id);
        }

        function setRow(rowId, spanId, value) {
            var empty = value === null || value === undefined || value === "";
            var span = el(spanId);
            var row = el(rowId);
            if (span) {
                span.textContent = empty ? "" : value;
            }
            if (row) {
                row.hidden = empty;
            }
        }

        function highlight(spanId, state) {
            // state: true = zgodne (zielony), false = rozbieżne (czerwony),
            // null = bez podświetlenia.
            var span = el(spanId);
            if (!span) {
                return;
            }
            span.classList.remove("przemapuj-match", "przemapuj-mismatch");
            if (state === true) {
                span.classList.add("przemapuj-match");
            } else if (state === false) {
                span.classList.add("przemapuj-mismatch");
            }
        }

        function showPlaceholder() {
            el("dst-placeholder").hidden = false;
            el("dst-content").hidden = true;
            el("dst-mnisw-warning").hidden = true;
        }

        function applyMniswRule(data) {
            var warning = el("dst-mnisw-warning");
            var text = el("dst-mnisw-warning-text");
            var dstMnisw =
                data.mnisw_effective === null || data.mnisw_effective === undefined
                    ? null
                    : String(data.mnisw_effective);

            if (srcMnisw !== null && dstMnisw !== srcMnisw) {
                // Źródło ministerialne → cel bez tego samego MNiSW ID: blokada.
                warning.hidden = false;
                text.textContent =
                    "Źródło źródłowe „" +
                    srcNazwa +
                    "” jest na oficjalnej liście ministerstwa (MNiSW ID: " +
                    srcMnisw +
                    "). Można je przemapować tylko na źródło o TYM SAMYM MNiSW ID " +
                    "— to przemapowanie zostanie odrzucone przy zapisie.";
                highlight("dst-mnisw", false);
            } else {
                warning.hidden = true;
                highlight(
                    "dst-mnisw",
                    srcMnisw !== null && dstMnisw === srcMnisw ? true : null
                );
            }
        }

        function fill(data) {
            el("dst-placeholder").hidden = true;
            el("dst-content").hidden = false;

            el("dst-nazwa").textContent = data.nazwa || "";
            setRow("dst-skrot-row", "dst-skrot", data.skrot);
            setRow("dst-issn-row", "dst-issn", data.issn);
            setRow("dst-eissn-row", "dst-eissn", data.e_issn);
            setRow("dst-mnisw-row", "dst-mnisw", data.mniswId);
            el("dst-bppid").textContent = data.bppid;
            el("dst-liczba").textContent = data.liczba_publikacji;

            var pbnRow = el("dst-pbn-row");
            if (data.pbn_uid_id) {
                var link = el("dst-pbn-link");
                var root = link.getAttribute("data-pbn-root") || "";
                link.href =
                    root + "/core/#/journal/view/" + data.pbn_uid_id + "/current";
                el("dst-pbn").textContent = data.pbn_uid_id;
                pbnRow.hidden = false;
            } else {
                pbnRow.hidden = true;
            }

            // Podświetlenie zgodności ISSN / e-ISSN (zielony gdy identyczne).
            highlight(
                "dst-issn",
                data.issn && srcIssn ? data.issn === srcIssn : null
            );
            highlight(
                "dst-eissn",
                data.e_issn && srcEissn ? data.e_issn === srcEissn : null
            );

            applyMniswRule(data);
        }

        function update(pk) {
            if (!pk) {
                showPlaceholder();
                return;
            }
            var url = infoUrlBase.replace(/0\/$/, pk + "/");
            fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
                .then(function (r) {
                    if (!r.ok) {
                        throw new Error("HTTP " + r.status);
                    }
                    return r.json();
                })
                .then(fill)
                .catch(function (e) {
                    showPlaceholder();
                    if (window.console) {
                        console.error(
                            "Nie udało się pobrać danych źródła docelowego:",
                            e
                        );
                    }
                });
        }

        // Wypełnij od razu, jeśli cel jest wstępnie wybrany (np. z deduplikatora).
        update(select.value);

        // Zmiana wyboru. DAL Select2 emituje jQuery-owe 'change' na <select>,
        // które łapiemy przez jQuery; fallback na natywny listener bez jQuery.
        if (window.jQuery) {
            window.jQuery(select).on("change", function () {
                update(select.value);
            });
        } else {
            select.addEventListener("change", function () {
                update(select.value);
            });
        }
    });
})();
